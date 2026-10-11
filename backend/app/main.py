from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .engine import STORE, baseline, candidate_plans, demo_reassess, hard_validation, run_runner
from .models import EvidenceUpdate, RunCreate


load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
app = FastAPI(title="KOI Recovery API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):517\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if key not in {"capabilities", "alternative_requested_by", "_task"}}


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
async def config() -> dict[str, Any]:
    key_ready = bool(os.getenv("OLLAMA_API_KEY", "").strip())
    return {"ollama_key_configured": key_ready, "model_configured": bool(os.getenv("OLLAMA_MODEL", "").strip()), "web_search_configured": key_ready, "data_notice": "KOI researches live web sources. Confirm schedules, fares, and availability with the linked operator before booking."}


@app.post("/api/runs", status_code=202)
async def create_run(request: RunCreate) -> dict[str, Any]:
    if request.mode == "live" and request.trip_details is None:
        raise HTTPException(422, "Enter your flight, route, date, and budget before starting live research.")
    try:
        details = request.trip_details.model_dump(mode="json") if request.trip_details else None
        state = STORE.create(request.scenario_id, request.mode, details)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    state["_task"] = asyncio.create_task(run_runner(state["run_id"]))
    return public_state(state)


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    state = STORE.runs.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    return public_state(state)


@app.get("/api/runs/{run_id}/responses")
async def get_responses(run_id: str) -> list[dict[str, Any]]:
    state = STORE.runs.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    return state["responses"]


@app.get("/api/runs/{run_id}/events")
async def events(request: Request, run_id: str, after: int = Query(0, ge=0)) -> StreamingResponse:
    if run_id not in STORE.runs:
        raise HTTPException(404, "Run not found")
    header_cursor = request.headers.get("last-event-id")
    cursor = max(after, int(header_cursor)) if header_cursor and header_cursor.isdigit() else after

    async def stream():
        nonlocal cursor
        while True:
            if await request.is_disconnected():
                break
            batch = await STORE.wait_for_events(run_id, cursor)
            if not batch:
                state = STORE.runs[run_id]
                if state["status"] != "running":
                    yield ": complete\n\n"
                    break
                yield ": keep-alive\n\n"
                continue
            for event in batch:
                cursor = event["id"]
                yield f"id: {event['id']}\ndata: {json.dumps(event, default=str)}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Connection":"keep-alive"})


@app.post("/api/runs/{run_id}/evidence", status_code=202)
async def add_evidence(run_id: str, update: EvidenceUpdate) -> dict[str, Any]:
    state = STORE.runs.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    option = next((item for item in state["scenario"]["options"] if item["id"] == "option-c"), None)
    if option is None:
        raise HTTPException(409, "This scenario has no Option C")
    if not option["available"]:
        raise HTTPException(409, "Option C is already unavailable")
    current_task = state.get("_task")
    if current_task and not current_task.done():
        current_task.cancel()
    old_votes = state["votes"]
    option["available"] = False
    state["evidence_version"] += 1
    state["votes"] = []
    state["consensus_plan"] = None
    state["status"] = "running"
    state["terminal_status"] = None
    state["plans"] = candidate_plans(state)
    STORE.emit(run_id,"evidence_updated",{"action":update.action,"option_id":"option-c","available":False,"evidence_version":state["evidence_version"],"invalidated_vote_count":len(old_votes),"reason":"New fixture information made Option C unavailable. Votes against older evidence are stale and were cleared."})
    STORE.emit(run_id,"votes_invalidated",{"previous_votes":old_votes,"current_evidence_version":state["evidence_version"]})
    STORE.emit(run_id,"round_started",{"round_number":max((r["round_number"] for r in state["responses"]),default=0)+1,"evidence_version":state["evidence_version"],"active_agents":state["active_agents"],"plans":state["plans"]})
    state["_task"] = asyncio.create_task(_reassess(run_id))
    return public_state(state)


async def _reassess(run_id: str) -> None:
    state = STORE.runs[run_id]
    if state["mode"] == "demo_playback":
        await demo_reassess(run_id)
        return
    round_number = max((r["round_number"] for r in state["responses"]), default=0) + 1
    plans = candidate_plans(state)
    state["plans"] = plans
    from .engine import _agent_response, _resolve_round
    before = len(state["responses"])
    await asyncio.gather(*[_agent_response(state, agent, round_number, plans) for agent in state["active_agents"]])
    failures = [r for r in state["responses"][before:] if r["call_status"] != "success"]
    if failures:
        state["status"] = state["terminal_status"] = "error"
        STORE.emit(run_id,"run_error",{"message":state["error"] or "Agent reassessment failed.","failed_agents":[r["agent_name"] for r in failures]})
    else:
        resolved = _resolve_round(state,plans,round_number)
        if resolved:
            state["status"] = state["terminal_status"] = "needs_human" if state["missing_information"] else "keep_disagreement"
            STORE.emit(run_id,"deliberation_stopped",{"status":state["status"],"dissent":state["dissent"],"missing_information":state["missing_information"],"reason":"New evidence was reassessed. Remaining options violate hard constraints; a person must choose how to proceed."})
    state["baseline"] = baseline(state)
    STORE.emit(run_id,"baseline",state["baseline"])
    STORE.emit(run_id,"run_completed",{"status":state["status"],"elapsed_ms":state.get("elapsed_ms"),"baseline":state["baseline"]})


@app.get("/api/runs/{run_id}/export")
async def export_run(run_id: str) -> dict[str, Any]:
    state = STORE.runs.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    return {"run":public_state(state),"responses":state["responses"],"events":state["events"]}

