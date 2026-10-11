from __future__ import annotations

import asyncio
import copy
import json
from datetime import datetime

from fastapi.testclient import TestClient

from app.engine import (
    FIXTURES, STORE, activate_alternatives, candidate_plans, demo_runner,
    hard_validation, reveal_alternative_option,
)
from app.main import add_evidence
from app.models import AgentDraft, EvidenceUpdate
from app.tools import check_option, option_cost, parse_time, validate_dataset_refs, validate_tool_arguments
from app.main import app


def fresh(scenario_id="nyc_recovery"):
    return STORE.create(scenario_id, "demo_playback")


def test_fixture_leg_costs_and_timezone_are_consistent():
    scenario = copy.deepcopy(FIXTURES["nyc_recovery"])
    option_c = next(item for item in scenario["options"] if item["id"] == "option-c")
    option_c["discovered"] = True
    assert option_cost(option_c) == 290
    assert option_cost(option_c) == option_c["total_cost_usd"]
    times = [parse_time(leg["depart"]) for leg in option_c["legs"]] + [parse_time(option_c["legs"][-1]["arrive"])]
    assert times == sorted(times)
    for option in scenario["options"]:
        leg_times = [parse_time(leg["depart"]) for leg in option["legs"]] + [parse_time(option["legs"][-1]["arrive"])]
        assert leg_times == sorted(leg_times)
        assert parse_time(option["legs"][-1]["arrive"]) == parse_time(option["venue_arrival"])
        assert option_cost(option) == option["total_cost_usd"]
    assert all(datetime.fromisoformat(item["time"]).utcoffset() is not None for item in scenario["itinerary"])
    assert check_option(option_c, scenario)["arrives_before_mandatory_event"] is True


def test_original_flight_options_create_real_budget_commitment_conflict():
    scenario = copy.deepcopy(FIXTURES["nyc_recovery"])
    options = {item["id"]: item for item in scenario["options"]}
    state = {"scenario": scenario}
    assert hard_validation({"route_option_id":"option-a", "commitment_changes":options["option-a"]["commitment_changes"]},state)["violations"] == ["hard_budget"]
    assert hard_validation({"route_option_id":"option-b", "commitment_changes":options["option-b"]["commitment_changes"]},state)["violations"] == ["mandatory_presentation"]
    assert hard_validation({"route_option_id":"option-c"},state)["violations"] == ["route_unavailable"]
    assert options["option-a"]["total_cost_usd"] == 380
    assert options["option-b"]["total_cost_usd"] == 200


def test_alternatives_activation_reveals_c_as_new_evidence():
    state = fresh()
    assert "Alternatives" not in state["active_agents"]
    activate_alternatives(state,"A peer asked for mixed route search.",state["run_id"])
    reveal_alternative_option(state,state["run_id"],reason="Tool search found a route.")
    assert state["active_agents"][-1] == "Alternatives"
    assert state["evidence_version"] == 2
    assert any(plan["route_option_id"] == "option-c" for plan in candidate_plans(state))


def test_infeasible_scenario_never_relaxes_hard_limits():
    state = fresh("infeasible")
    activate_alternatives(state,"Flight options cannot satisfy both hard constraints.",state["run_id"])
    reveal_alternative_option(state,state["run_id"],reason="Alternatives search completed.")
    assert all(not hard_validation(plan,state)["valid"] for plan in candidate_plans(state))


def test_agent_schema_and_dataset_reference_validation():
    scenario = copy.deepcopy(FIXTURES["nyc_recovery"])
    scenario["options"][-1]["available"] = True
    scenario["options"][-1]["discovered"] = True
    draft = AgentDraft.model_validate({
        "proposed_plan":{"plan_id":"plan-option-c","plan_version":1,"route_option_id":"option-c","commitment_changes":[]},
        "reason":"C meets both hard constraints.","supporting_facts":["fixture-option-c"],"objections":[],"requested_capabilities":[],"evaluations":[],"missing_information":[],"proposal_changed":True,"change_reason":"Peer objection changed the plan."
    }).model_dump(mode="json")
    validate_dataset_refs(draft,scenario)
    draft["supporting_facts"]=["invented-route"]
    try:
        validate_dataset_refs(draft,scenario)
        assert False, "unknown source IDs should fail"
    except ValueError as exc:
        assert "unknown supporting fact IDs" in str(exc)


def test_tool_arguments_are_bounded_and_typed():
    assert validate_tool_arguments({"tool_name":"cost_calculator","arguments":{"route_option_id":"option-a"}})=={"route_option_id":"option-a"}
    try:
        validate_tool_arguments({"tool_name":"cost_calculator","arguments":{"route_option_id":"option-a","budget_usd":0}})
        assert False, "extra arguments should fail"
    except Exception:
        pass


def test_unanimous_acceptance_requires_valid_same_plan_and_evidence():
    from app.engine import _resolve_round
    state = fresh()
    state["alternative_active"] = True
    state["active_agents"] = ["Travel","Budget","Commitments"]
    state["scenario"]["options"][-1]["available"] = True
    state["scenario"]["options"][-1]["discovered"] = True
    plan = next(p for p in candidate_plans(state) if p["route_option_id"] == "option-c")
    for agent in state["active_agents"]:
        state["responses"].append({"round_number":0,"call_status":"success","agent_name":agent,"evidence_version":1,"evaluations":[{"plan_id":plan["plan_id"],"plan_version":1,"decision":"accept","reason":"meets constraints"}]})
    assert _resolve_round(state,[plan],0) is False
    assert state["status"] == "consensus"
    assert state["consensus_plan"]["plan_id"] == plan["plan_id"]


def test_new_information_invalidates_old_votes_and_changes_evidence(monkeypatch):
    import app.main as main
    async def skip_reassessment(_run_id):
        return None
    monkeypatch.setattr(main,"_reassess",skip_reassessment)
    async def exercise():
        state = fresh()
        state["scenario"]["options"][-1]["available"] = True
        state["votes"] = [{"agent_name":"Travel","plan_id":"plan-option-c","plan_version":1,"decision":"accept","evidence_version":1}]
        response = await add_evidence(state["run_id"],EvidenceUpdate(action="option_c_unavailable"))
        assert response["evidence_version"] == 2
        assert response["votes"] == []
        assert response["consensus_plan"] is None
        assert any(e["type"]=="votes_invalidated" for e in response["events"])
    asyncio.run(exercise())


def test_demo_playback_preserves_round_zero_and_every_agent_message():
    async def exercise():
        state = fresh()
        await demo_runner(state["run_id"])
        assert state["status"] == "consensus"
        assert len([r for r in state["responses"] if r["round_number"]==0]) == 3
        assert {r["agent_name"] for r in state["responses"] if r["round_number"]==1} == {"Travel","Budget","Commitments","Alternatives"}
        assert all(r["phase"]==("initial_proposal" if r["round_number"]==0 else "negotiation") for r in state["responses"])
        assert state["responses"][0]["message_id"]
    asyncio.run(exercise())


def test_demo_new_information_reassesses_and_escalates_without_relaxing_constraints():
    async def exercise():
        state = fresh()
        await demo_runner(state["run_id"])
        response = await add_evidence(state["run_id"],EvidenceUpdate(action="option_c_unavailable"))
        await state["_task"]
        assert response["evidence_version"] == 3
        assert state["status"] == "needs_human"
        assert state["consensus_plan"] is None
        assert {r["agent_name"] for r in state["responses"] if r["round_number"]==2} == {"Travel","Budget","Commitments","Alternatives"}
        assert any(event["type"]=="votes_invalidated" for event in state["events"])
    asyncio.run(exercise())


def test_live_graph_reports_missing_credentials_without_demo_fallback(monkeypatch):
    from app.engine import live_runner
    monkeypatch.delenv("OLLAMA_API_KEY",raising=False)
    monkeypatch.delenv("OLLAMA_MODEL",raising=False)
    async def exercise():
        state = fresh()
        state["mode"]="live"
        await live_runner(state["run_id"])
        assert state["status"] == "error"
        assert len(state["responses"]) == 3
        assert all(r["call_status"]=="model_error" for r in state["responses"])
        assert not any(event["type"]=="consensus" for event in state["events"])
    asyncio.run(exercise())


def test_api_run_sse_responses_and_export():
    with TestClient(app) as client:
        created=client.post("/api/runs",json={"scenario_id":"nyc_recovery","mode":"demo_playback"})
        assert created.status_code==202
        run_id=created.json()["run_id"]
        received=[]
        with client.stream("GET",f"/api/runs/{run_id}/events?after=0") as stream:
            for line in stream.iter_lines():
                if line.startswith("data: "):
                    event=json.loads(line[6:])
                    received.append(event["type"])
                    if event["type"]=="run_completed":
                        break
        assert "agent_response" in received
        assert "consensus" in received
        current=client.get(f"/api/runs/{run_id}").json()
        history=client.get(f"/api/runs/{run_id}/export").json()
        assert current["status"]=="consensus"
        assert len(client.get(f"/api/runs/{run_id}/responses").json())==7
        assert len(history["responses"])==7
        assert history["responses"][0]["phase"]=="initial_proposal"

