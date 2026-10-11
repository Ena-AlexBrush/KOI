"""Regression coverage ported to Anu's actual protocol and one LangGraph loop."""
import asyncio
import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import engine, ollama
from app.engine import STORE, FIXTURES, candidate_plans, hard_validation
from app.main import add_evidence, app
from app.models import AgentDraft, AgentResponse, EvidenceUpdate, RunCreate
from app.tools import execute_tool, search_routes


@pytest.fixture
def state():
    result = STORE.create("nyc_recovery", "live")
    result["scenario"]["options"][-1]["discovered"] = True
    return result


def plan_c(state):
    return next(p for p in candidate_plans(state) if p["route_option_id"] == "option-c")


def violations(state):
    return hard_validation(plan_c(state), state)["violations"]


@pytest.mark.parametrize("field,value,expected", [
    ("depart", "2026-10-10T12:29:00-04:00", "transfer_timing"),
    ("minimum_connection_minutes", 46, "transfer_timing"),
    ("from", "Unknown terminal", "transfer_location"),
    ("depart", "2026-10-10T13:15:00", "invalid_supplied_data"),
    ("arrive", "2026-10-10T13:00:00-04:00", "leg_timing"),
])
def test_transfer_validation(state, field, value, expected):
    state["scenario"]["options"][-1]["legs"][1][field] = value
    assert expected in violations(state)


def test_timezone_offsets_and_missing_transfer_minimum(state):
    leg = state["scenario"]["options"][-1]["legs"][1]
    leg["depart"] = "2026-10-10T17:15:00+00:00"
    assert not violations(state)
    leg.pop("minimum_connection_minutes")
    assert "minimum_connection_time" in violations(state)


def test_commitment_fees_are_in_budget_without_truncating_cents(state):
    event = state["scenario"]["itinerary"][0]
    event["allowed_changes"][0]["fee_usd"] = "10.01"
    checked = hard_validation(plan_c(state), state)
    assert checked["cost_usd"] == 300.01
    assert checked["commitment_fees_usd"] == 10.01
    assert "hard_budget" in checked["violations"]
    event["allowed_changes"][0]["fee_usd"] = "10.00"
    assert not violations(state)


@pytest.mark.parametrize("changes,expected", [
    ([{"event_id": "presentation", "change_option_id": "move"}], "mandatory_commitment_change"),
    ([{"event_id": "unknown", "change_option_id": "move"}], "unknown_commitment"),
    ([{"event_id": "hotel-check-in", "change_option_id": "invented"}], "unknown_commitment_change"),
    ([{"event_id": "hotel-check-in", "change_option_id": "after-presentation", "start": "2026-10-10T12:00:00-04:00"}], "commitment_change_mismatch"),
    ([{"event_id": "hotel-check-in", "change_option_id": "after-presentation", "fee_usd": 1}], "commitment_fee_mismatch"),
])
def test_commitment_changes_cannot_invent_permissions(state, changes, expected):
    plan = plan_c(state)
    plan["commitment_changes"] = changes
    assert expected in hard_validation(plan, state)["violations"]


def test_flexible_bounds_overlap_and_all_mandatory_events(state):
    event = state["scenario"]["itinerary"][0]
    event["latest_end"] = "2026-10-10T18:30:00-04:00"
    assert "flexible_scheduling_constraints" in violations(state)
    event["latest_end"] = "2026-10-10T23:00:00-04:00"
    state["scenario"]["itinerary"][1]["end"] = "2026-10-10T18:30:00-04:00"
    assert "commitment_overlap" in violations(state)
    state["scenario"]["itinerary"].append({"id":"second-mandatory", "name":"Extra event", "mandatory":True,
        "flexible":False, "time":"2026-10-10T16:00:00-04:00", "end":"2026-10-10T16:15:00-04:00"})
    assert "mandatory_commitment" in violations(state)


def test_missing_domestic_evidence_never_implies_eligibility(state):
    state["scenario"].pop("visa_eligibility")
    assert "entry_transit_evidence" in violations(state)
    state["scenario"]["visa_eligibility"] = {"status":"not_applicable_domestic"}
    assert "entry_transit_evidence" in violations(state)


def test_sourced_entry_and_transit_evidence_and_traveler_facts(state):
    option = state["scenario"]["options"][-1]
    req = {"id":"transit-x", "country":"X", "kind":"transit", "evidence_complete":False,
           "allowed_traveler_facts":{"transit_document":["valid"]}}
    option["entry_requirements"] = [req]
    assert "requirement_evidence:transit-x" in violations(state)
    assert "traveler_information:transit_document" in violations(state)
    req.update(source_id="fixture-transit", source="https://example.invalid/synthetic-policy", evidence_complete=True)
    state["scenario"]["traveler_information"] = {"transit_document":"invalid"}
    assert "entry_transit_ineligible:transit-x" in violations(state)
    state["scenario"]["traveler_information"]["transit_document"] = "valid"
    assert not violations(state)
    option["entry_requirements_complete"] = False
    assert "entry_transit_coverage" in violations(state)


@pytest.mark.parametrize("mode", ["train", "bus"])
def test_original_method_search_is_supplied_not_flight(state, mode):
    scenario = state["scenario"]
    scenario["original_method"] = mode
    scenario["options"][0]["method"] = mode
    scenario["options"][0]["legs"][0]["mode"] = mode
    assert [o["id"] for o in search_routes(scenario, original_method_only=True, include_alternatives=False)] == ["option-a"]


def test_plan_ids_cover_complete_changes_and_are_stable(state):
    before = plan_c(state)
    assert before == plan_c(state)
    state["scenario"]["options"][-1]["commitment_changes"] = []
    assert plan_c(state)["plan_id"] != before["plan_id"]


def test_tool_permissions_and_schedule_validation(state):
    with pytest.raises(ValueError):
        execute_tool("Travel", {"tool_name":"schedule_change_proposal", "arguments":{}}, state)
    result = execute_tool("Commitments", {"tool_name":"schedule_change_proposal", "arguments":{
        "commitment_changes":[{"event_id":"presentation", "change_option_id":"invented"}]}}, state)
    assert result["valid"] is False
    assert "mandatory_commitment_change" in result["violations"]


def scripted_call(decision="reject", mutate=None, contexts=None):
    async def respond(messages, validator, post_validate=None):
        facts = json.loads(messages[-1]["content"])
        if contexts is not None:
            contexts.append(facts)
        plans = facts["current_plans"]
        draft = {"in_reply_to":[m["message_id"] for m in facts["prior_peer_messages"]],
            "tool_calls":[{"tool_name":"route_search", "arguments":{}}] if "route_search" in facts["allowed_tool_names"] else [],
            "proposed_plan":{k:plans[0][k] for k in ("plan_id","plan_version","route_option_id")} if plans else None,
            "reason":"Scripted protocol test, not live AI", "supporting_facts":[], "objections":[],
            "requested_capabilities":[], "evaluations":[{"plan_id":p["plan_id"], "plan_version":p["plan_version"], "decision":decision, "reason":"test"} for p in plans],
            "missing_information":[], "proposal_changed":False, "change_reason":""}
        if mutate:
            mutate(draft)
        draft = validator.model_validate(draft).model_dump(mode="json")
        if post_validate:
            post_validate(draft)
        return draft, 0
    return respond


def test_live_loop_three_total_rounds_and_initial_storage(monkeypatch):
    contexts = []
    monkeypatch.setattr(engine, "call_json", scripted_call(contexts=contexts))
    async def exercise():
        state = STORE.create("nyc_recovery", "live")
        await engine.live_runner(state["run_id"])
        assert state["status"] == "needs_human"
        assert state["next_round"] == 3
        assert {r["round_number"] for r in state["responses"]} == {0, 1, 2}
        assert len(state["responses"]) == 11  # Three initial, four in each later round.
        assert len({(r["agent_name"], r["round_number"]) for r in state["responses"]}) == 11
        assert all(r["call_status"] == "success" for r in state["responses"])
        assert all(AgentResponse.model_validate(r) for r in state["responses"])
        assert contexts[-1]["validation_results"] and contexts[-1]["new_information"]
        assert contexts[-1]["prior_peer_messages"] and contexts[-1]["prior_agent_messages"]
        updated = await add_evidence(state["run_id"], EvidenceUpdate(action="option_c_unavailable"))
        assert updated["status"] == "needs_human" and len(state["responses"]) == 11
        assert updated["consensus_plan"] is None
    asyncio.run(exercise())


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(in_reply_to=["fabricated-message"]),
    lambda d: d.update(requested_capabilities=["invented"]),
    lambda d: d.update(tool_calls=[{"tool_name":"payment", "arguments":{}}]),
    lambda d: d["proposed_plan"].update(plan_id="invented-plan"),
    lambda d: d.update(objections=[{"challenged_plan_id":"unknown", "challenged_plan_version":1,
                                    "concern":"x", "resolution_needed":"y"}]),
])
def test_invalid_agent_protocol_is_stored(monkeypatch, state, mutation):
    monkeypatch.setattr(engine, "call_json", scripted_call(mutate=mutation))
    asyncio.run(engine._agent_response(state, "Travel", 0, candidate_plans(state)))
    assert len(state["responses"]) == 1
    response = state["responses"][0]
    assert response["call_status"] == "invalid_output"
    assert response["agent_name"] == "Travel" and response["run_id"] == state["run_id"]


def test_explicit_reply_ids_survive_in_agent_response(monkeypatch, state):
    monkeypatch.setattr(engine, "call_json", scripted_call())
    async def exercise():
        await engine._agent_response(state, "Budget", 0, candidate_plans(state))
        peer = state["responses"][0]
        await engine._agent_response(state, "Travel", 1, candidate_plans(state))
        assert state["responses"][-1]["in_reply_to"] == [peer["message_id"]]
        assert state["responses"][-1]["tool_results"]
    asyncio.run(exercise())


def test_mid_call_information_keeps_old_response_evidence_and_one_loop(monkeypatch):
    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()
        delegate = scripted_call()
        async def paused(messages, validator, post_validate=None):
            facts = json.loads(messages[-1]["content"])
            if facts["evidence_version"] == 1:
                entered.set()
                await release.wait()
            return await delegate(messages, validator, post_validate)
        monkeypatch.setattr(engine, "call_json", paused)
        state = STORE.create("nyc_recovery", "live")
        state["_task"] = asyncio.create_task(engine.live_runner(state["run_id"]))
        original_task = state["_task"]
        await entered.wait()
        await add_evidence(state["run_id"], EvidenceUpdate(action="update_information",
            unavailable_option_ids=["option-a"], reason="Supplied option sold out"))
        assert state["_task"] is original_task
        release.set()
        await original_task
        assert all(r["evidence_version"] == 1 for r in state["responses"][:3])
        assert not any(v["evidence_version"] == 1 for v in state["votes"])
        assert state["next_round"] == 3 and state["status"] == "needs_human"
    asyncio.run(exercise())


def test_discovery_cannot_revive_unavailable_route(state):
    state["scenario"]["options"][-1].update(available=False, discovered=False)
    engine.reveal_alternative_option(state, state["run_id"], reason="search")
    assert not state["scenario"]["options"][-1]["available"]
    assert not any(p["route_option_id"] == "option-c" for p in candidate_plans(state))


def test_naive_input_rejected_and_custom_train_scenario_accepted(state):
    scenario = state["scenario"]
    scenario["original_method"] = "train"
    RunCreate.model_validate({"scenario":scenario})
    scenario["options"][0]["legs"][0]["depart"] = "2026-10-10T06:00:00"
    with pytest.raises(ValidationError):
        RunCreate.model_validate({"scenario":scenario})


def test_http_polling_and_generic_information_validation():
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        state = STORE.create("nyc_recovery", "live")
        path = f'/api/runs/{state["run_id"]}'
        assert client.get(path).json()["run_id"] == state["run_id"]
        assert client.post(path + "/evidence", json={"action":"update_information", "unavailable_option_ids":["unknown"]}).status_code == 422
        assert state["evidence_version"] == 1
        assert client.get("/openapi.json").status_code == 200


def test_ollama_timeout_and_one_repair_attempt(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")
    replies = []
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            replies.append(kwargs["json"])
            return httpx.Response(200, json={"message":{"content":"not json"}})
    monkeypatch.setattr(ollama.httpx, "AsyncClient", Client)
    with pytest.raises(ollama.ModelCallError) as error:
        asyncio.run(ollama.call_json([], AgentDraft))
    assert error.value.status == "invalid_output" and len(replies) == 2
    async def timeout(self, *args, **kwargs):
        raise httpx.ReadTimeout("test timeout")
    monkeypatch.setattr(Client, "post", timeout)
    with pytest.raises(ollama.ModelCallError) as error:
        asyncio.run(ollama.call_json([], AgentDraft))
    assert error.value.status == "timeout"


def test_timeout_is_recorded_once_per_active_agent(monkeypatch):
    async def timeout(*args, **kwargs):
        raise ollama.ModelCallError("timeout", "test timeout")
    monkeypatch.setattr(engine, "call_json", timeout)
    state = STORE.create("nyc_recovery", "live")
    asyncio.run(engine.live_runner(state["run_id"]))
    assert len(state["responses"]) == 3 and state["status"] == "error"
    assert all(r["call_status"] == "timeout" for r in state["responses"])


def test_live_loop_consensus_still_requires_independent_validation(monkeypatch):
    # Agents accept everything; Python must still disqualify A and B.
    monkeypatch.setattr(engine, "call_json", scripted_call(decision="accept"))
    state = STORE.create("nyc_recovery", "live")
    asyncio.run(engine.live_runner(state["run_id"]))
    assert state["status"] == "consensus"
    assert state["consensus_plan"]["route_option_id"] == "option-c"
    assert len(state["responses"]) == 7 and state["next_round"] == 2
    assert len(state["validations"]) == 3
    assert all(v["evidence_version"] == state["evidence_version"] for v in state["validations"])


def test_multiple_valid_accepted_plans_stay_unresolved(monkeypatch, state):
    monkeypatch.setattr(engine, "call_json", scripted_call(decision="accept"))
    state["scenario"]["budget_usd"] = 500
    asyncio.run(engine.live_runner(state["run_id"]))
    assert state["status"] == "needs_human" and state["next_round"] == 3
    assert state["consensus_plan"] is None
    assert "Alternatives" in state["active_agents"]
    assert any(e["type"] == "multiple_acceptable_plans" for e in state["events"])


def test_incomplete_costs_block_acceptance(state):
    state["scenario"]["options"][-1]["costs_complete"] = False
    assert "complete_additional_costs" in violations(state)


def test_anu_plan_selection_attaches_immutable_schedule(monkeypatch, state):
    # Upstream's selection-only draft ignores extra model schedule content;
    # the server attaches the actual shared complete plan, never the invented one.
    monkeypatch.setattr(engine, "call_json", scripted_call(mutate=lambda d:
        d["proposed_plan"].update(commitment_changes=[{"event_id":"presentation", "after":"invented"}])))
    plans = candidate_plans(state)
    asyncio.run(engine._agent_response(state, "Travel", 0, plans))
    response = state["responses"][-1]
    assert response["call_status"] == "success"
    assert response["proposed_plan"]["commitment_changes"] == plans[0]["commitment_changes"]
