# Backend integration

Your original backend is preserved in commit `6ba627e` on local branch
`codex/koi-backend`. This branch starts from Anu's implementation at `7edf1c3`
on `origin/main`. Only `codex/backend-integration` is intended to be pushed.
Neither original implementation is replaced. No AGENTS.md files were present.
All frontend files are unchanged.

## Overlap and resolution

| Area | Overlap | Integrated implementation |
| --- | --- | --- |
| HTTP | Create runs, poll results, introduce facts | Retain Anu's `/api/runs`, `/evidence`, `/responses`, SSE `/events`, `/export`, and auto-start. Do not add the competing `/runs` API. |
| Schemas | Proposals, objections, votes, plan references | Retain `AgentDraft`, `AgentResponse`, `PlanRef`, `Evaluation`, agent names and JSON fields. Add the missing `AgentDraft.in_reply_to`. |
| State | In-memory runs, history, plans, evidence | Keep Anu's `RunStore` and append-only events/responses. Port isolated snapshots and safe new-information handling. |
| Selection | Core agents plus Alternatives | Retain Anu's capabilities and activation reasons. Use the supplied original method and validated complete plans. |
| Validation | Budget, arrival, plan references | Adapt your Decimal cost, transfer, commitment-change, entry/transit, and missing-information checks to Anu's dataset in `app/validation.py`. |
| Tools | Your mock boundary versus Anu's executable tools | Keep Anu's role permissions, typed arguments, tool choices, execution and traces. Strengthen cost/schedule/arrival results. |
| Negotiation | Your Python loop versus Anu's LangGraph rounds | Keep Anu's LangGraph loop and exact plan/version/evidence unanimous voting. Live reassessment uses that same loop. Do not copy your coordinator. |
| Ollama/prompts | Only Anu has real integration | Preserve `ollama.py`, hosted endpoint, model configuration, timeout/error handling and one JSON repair attempt. Retain role prompts and peer instructions with transport/evidence corrections. |
| Offline mode | Your mock versus Anu's playback | Keep only Anu's labeled Demo Playback. It is scripted, not another live negotiation engine. Live errors never fall back to playback. |

## Corrected behavior

- `in_reply_to` is accepted, checked against prior peer IDs, and preserved in
  `AgentResponse`. Identity, round, message, and evidence metadata stay backend-owned.
- Plan IDs hash the route and complete commitment changes. Votes still reference
  `plan_id`, `plan_version`, and `evidence_version`; changed plans cannot reuse an
  earlier acceptance. Unknown plan/objection references and capabilities fail.
- The initial proposal counts: **three total rounds, numbered 0, 1, 2**. Evidence
  updates consume the remaining lifetime allowance. Exhaustion yields
  `needs_human` and retains disagreement; no round 3 is permitted.
- Consensus requires all active agents to accept exactly one complete plan in the
  same current round/evidence version, plus independent validation. Multiple
  accepted plans remain unresolved. Missing information or an objection to the
  same accepted plan prevents that acceptance from counting.
- Discovery is separate from availability: Alternatives can reveal a supplied
  available route marked `discovered: false`, but cannot revive a sold-out route.
- Live updates do not cancel and lose in-flight responses or launch a second
  loop. Old responses keep their original evidence version and cannot create
  current consensus. Compare response/run `evidence_version` to identify staleness.
- Updates immediately clear votes/consensus and refresh plans and Python
  `validations`. Subsequent agent snapshots include peer/own history, complete
  plans, validation results, new information, and activation reasons.

## Supplied evidence and validation

`app/scenario.py` types Anu's dataset keys. Fixtures now explicitly supply event
end times, allowed changes/fees, scheduling windows, transfer minima, cost
completeness, and domestic entry evidence. Existing route costs and intended
feasible/infeasible outcomes remain unchanged. Station aliases and the incorrect
Boston note were corrected in the synthetic data.

Python validates leg durations, transfer locations/minima, earliest departure,
route endpoints, and final venue arrival consistency. Decimal arithmetic sums
all legs, `additional_costs_usd`, and supplied change fees. No integer truncation,
inferred refunds, or automatic budget increase.

Changes must reference supplied flexible events and allowed change IDs. Mandatory
events cannot move. Every future mandatory event must be reachable. Flexible
changes must remain within supplied windows, retain duration, avoid overlap, and
protect unchanged events. Events are modeled at the recovery venue; independent
travel between event locations is outside this prototype.

Entry/transit coverage is explicit. Listed requirements need source metadata,
complete evidence, and allowed traveler facts matching supplied information.
Missing evidence blocks consensus. Empty requirements require complete, sourced
`not_applicable_domestic` evidence; emptiness alone never implies eligibility.
The backend validates supplied evidence but does not fetch/authenticate sources.
Synthetic metadata is not real immigration policy.

## API compatibility and additional inputs

Existing frontend requests remain valid:

```json
{"scenario_id": "nyc_recovery", "mode": "demo_playback"}
```

`POST /api/runs` additionally accepts a typed `scenario` in live mode. Use
`original_method: "train"` or `"bus"` with matching supplied routes and legs.
See `/openapi.json` and `app/fixtures/scenarios.json` for the dataset shape.
Each route supplies one complete `commitment_changes` set; agents evaluate that
catalog instead of inventing additional schedule policies. Custom data cannot
use fixture-specific scripted playback.

The Option C evidence action is retained. Generic updates are also supported:

```json
{
  "action": "update_information",
  "unavailable_option_ids": ["option-a"],
  "traveler_information": {"transit_document": "valid"},
  "reason": "New supplied facts"
}
```

Post to `/api/runs/{run_id}/evidence`; poll GET or consume SSE. New prices, routes,
policy evidence, or scheduling rules require a new supplied run. Updates during
scripted playback return 409; submit them after playback completes.

## Setup and checks

Integration verification: **47 backend tests passed** (12 retained regression
tests and 35 additional cases), Python compilation passed, `pip check` found no
broken requirements, and `git diff --check` passed. Git comparison confirmed no
changes to `frontend/` or `app/ollama.py`.

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
$env:KOI_CORS_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000
```

Use one worker: state is process-local and resets on restart. CORS is configurable.
The root README retains macOS setup and the UI example. No real booking, payment,
message, or cancellation is executed.

For live verification, configure `OLLAMA_API_KEY` and a verified `OLLAMA_MODEL` in
`backend/.env` or the environment, then run:

```powershell
.\.venv\Scripts\python.exe backend/scripts/verify_live.py
```

The probe never prints secret values or falls back to playback. Exit code 2 means
missing configuration. Neither variable nor a root/backend `.env` existed in
this workspace: live Ollama verification is **blocked**. Offline tests exercise
Anu's real loop using scripted responses and mock HTTP timeout/repair behavior;
they are not live AI tests.

## Remaining work

- Run the live probe with Anu's working credentials/model and inspect agent
  behavior; live performance and model quality remain unverified.
- The preserved frontend is flight-fixture-specific. Its evidence button does
  not reconnect the closed SSE stream after a completed run. Frontend owners
  should reconnect SSE or poll after submitting new evidence; the backend
  reassessment path is covered by tests.
- Auth, persistence, multi-worker coordination, real route/policy sourcing, and
  production traveler-data handling remain outside this hackathon backend.
