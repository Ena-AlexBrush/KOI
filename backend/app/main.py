from __future__ import annotations

import asyncio
import json
import os
import copy
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .engine import STORE, MAX_ROUNDS, candidate_plans, demo_reassess, live_runner, refresh_validations, run_runner, stop_at_limit
from .models import EvidenceUpdate, RunCreate


load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
@asynccontextmanager
async def lifespan(app):
    yield
    tasks = [s["_task"] for s in STORE.runs.values() if s.get("_task") and not s["_task"].done()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="KOI Recovery API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in os.getenv("KOI_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Last-Event-ID"])


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy({key: value for key, value in state.items() if key not in {"capabilities", "alternative_requested_by", "_task"}})


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
async def config() -> dict[str, Any]:
    return {"ollama_key_configured": bool(os.getenv("OLLAMA_API_KEY", "").strip()), "model_configured": bool(os.getenv("OLLAMA_MODEL", "").strip()), "fixture_notice": "Fixture data is synthetic, not live transportation availability."}


@app.post("/api/runs", status_code=202)
async def create_run(request: RunCreate) -> dict[str, Any]:
    if request.scenario is not None and request.mode == "demo_playback":
        raise HTTPException(422, "Scripted playback supports built-in fixtures only; supplied scenarios require live mode.")
    state = STORE.create(request.scenario_id, request.mode,
                         request.scenario.model_dump(mode="json", by_alias=True) if request.scenario else None)
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
    ids = ["option-c"] if update.action == "option_c_unavailable" else update.unavailable_option_ids
    options = {o["id"]: o for o in state["scenario"]["options"]}
    if set(ids) - options.keys():
        raise HTTPException(422, "Unknown option ID")
    if not ids and not update.traveler_information:
        raise HTTPException(422, "Supply unavailable_option_ids or traveler_information")
    if any(not options[option_id]["available"] for option_id in ids):
        raise HTTPException(409, "Option is already unavailable")
    current_task = state.get("_task")
    if current_task and not current_task.done() and state["mode"] == "demo_playback":
        raise HTTPException(409, "Wait for scripted playback to finish before updating its evidence")
    old_votes = state["votes"]
    for option_id in ids:
        options[option_id]["available"] = False
    state["scenario"].setdefault("traveler_information", {}).update(update.traveler_information)
    state["evidence_version"] += 1
    state["votes"] = []
    state["consensus_plan"] = None
    state["status"] = "running"
    state["terminal_status"] = None
    state["error"] = None
    state["plans"] = candidate_plans(state)
    refresh_validations(state)
    information = {"action": update.action, "option_id": ids[0] if len(ids) == 1 else None,
                   "unavailable_option_ids": ids, "traveler_information": update.traveler_information,
                   "available": False, "evidence_version": state["evidence_version"],
                   "invalidated_vote_count": len(old_votes), "reason": update.reason}
    state["new_information"].append(information)
    STORE.emit(run_id,"evidence_updated",information)
    STORE.emit(run_id,"votes_invalidated",{"previous_votes":old_votes,"current_evidence_version":state["evidence_version"]})
    if not current_task or current_task.done():
        if state["next_round"] >= MAX_ROUNDS:
            stop_at_limit(state)
        else:
            state["_task"] = asyncio.create_task(_reassess(run_id))
    return public_state(state)


async def _reassess(run_id: str) -> None:
    state = STORE.runs[run_id]
    if state["mode"] == "demo_playback":
        await demo_reassess(run_id)
        return
    # Reuse Anu's one LangGraph loop, including its shared lifetime round budget.
    await live_runner(run_id)


@app.get("/api/runs/{run_id}/export")
async def export_run(run_id: str) -> dict[str, Any]:
    state = STORE.runs.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    return {"run":public_state(state),"responses":state["responses"],"events":state["events"]}

