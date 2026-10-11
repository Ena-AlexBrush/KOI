"""Run from repo root: python backend/scripts/verify_live.py.

Explicit live check: no demo fallback and no credential values in output.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # Loads the server's backend/.env configuration.
from app.engine import STORE, live_runner


async def main():
    configured = {key: bool(os.getenv(key, "").strip()) for key in ("OLLAMA_API_KEY", "OLLAMA_MODEL")}
    if not all(configured.values()):
        print(json.dumps({"live_verification": "blocked", "configured": configured,
                          "reason": "Set the missing values in backend/.env or the process environment."}))
        return 2
    state = STORE.create("nyc_recovery", "live")
    try:
        await asyncio.wait_for(live_runner(state["run_id"]), timeout=300)
    except asyncio.TimeoutError:
        print(json.dumps({"live_verification": "failed", "reason": "Live check exceeded 300 seconds."}))
        return 1
    responses = state["responses"]
    successful = bool(responses) and all(r["call_status"] == "success" for r in responses)
    print(json.dumps({"live_verification": "passed" if successful else "failed",
        "status": state["status"], "response_count": len(responses),
        "round_numbers": sorted({r["round_number"] for r in responses}),
        "call_statuses": sorted({r["call_status"] for r in responses})}, indent=2))
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
