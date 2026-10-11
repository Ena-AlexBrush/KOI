# KOI · disruption recovery

KOI coordinates a recovery when a travel change affects the rest of a person's plans.

> A disaster is one change away. Recovery is one decision away.

This hackathon MVP prioritizes the Level 3 challenge: Travel, Budget, and Commitments make independent proposals; Alternatives joins when a peer asks for a mixed route or the flight evidence cannot meet both hard constraints. Agents exchange round 0 messages, respond to actual peer message IDs, and independently evaluate exact plan versions. Only unanimous acceptance plus deterministic hard-constraint validation produces consensus.

All route and price data is synthetic and for demonstration only. KOI does not check live availability or make bookings. A future booking action must require explicit user approval.

## Project layout

```text
backend/
  app/
    engine.py          LangGraph round scheduler, append-only history, consensus rules
    fixtures/          Synthetic feasible and infeasible travel scenarios
    main.py            FastAPI and SSE endpoints
    models.py          Pydantic request and response schemas
    ollama.py          Server-side Ollama Cloud API and one JSON repair attempt
    tools.py           Bounded, validated route, cost, schedule, and arrival tools
  tests/               Protocol, data, consensus, evidence, and playback checks
  .env.example
frontend/
  src/App.jsx          React interface and SSE event presentation
  src/styles.css       Responsive KOI visual system
```

## Architecture

1. The React client posts a run request to FastAPI. API keys and model calls stay on the server.
2. LangGraph carries the run ID and round number through the bounded deliberation loop. Round participants read one shared evidence snapshot.
3. Each agent has its own goal, prompt, and tool permissions. One schema-validated JSON response per round contains its tool choices, proposal, objections, replies, evidence IDs, and independent votes. The backend validates and executes those tool choices, then attaches the results to the recorded response.
4. The scheduler delivers peer messages and executes validated tool calls. It does not rank plans or choose a winner. Alternatives is activated from an explicit agent request or deterministic evidence that flights cannot satisfy budget and arrival constraints.
5. Votes are tied to plan version and evidence version. New evidence clears stale votes and starts reassessment. Consensus requires every active agent to accept one identical plan version and the deterministic validator to confirm the $300 budget and mandatory presentation.
6. Responses and SSE events are append-only in in-memory run storage. Export includes round 0 and every later response. Restarting the backend clears runs.

`Demo Playback` is an explicit, scripted fixture playback for an offline presentation. It is labeled in the interface and makes no Ollama calls. The live button never falls back to playback after an API or model error.

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer and npm
- An Ollama Cloud API key and a model name confirmed in your Ollama Cloud account/model catalog

The provided sponsor credits note contains vendor credits for other services; it does not contain an Ollama API key or model name. The model field is intentionally blank so nobody has to guess a model. Select a model marked Cloud in the [Ollama model catalog](https://ollama.com/search).

## Setup on macOS

Install Node if the `node` and `npm` commands are not already available:

```bash
brew install node
```

In Terminal 1, set up and start the API:

```bash
cd /Users/anualluri/KOI
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
open -e backend/.env
```

Enter `OLLAMA_API_KEY` and set `OLLAMA_MODEL` to a name available in your Ollama Cloud account. Save the file, then start FastAPI:

```bash
uvicorn app.main:app --app-dir backend --reload --port 8000
```

In Terminal 2, install and start the frontend:

```bash
cd /Users/anualluri/KOI/frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The API health check is [http://localhost:8000/api/health](http://localhost:8000/api/health).

Keep `backend/.env` private. It is ignored by Git, and the frontend receives only whether credentials are configured, never the key or its value.

## Demo script for judges

1. Choose **NYC recovery · $300 budget**. Show the cancelled SFO flight, 3 PM flexible check-in, 5 PM mandatory presentation, and 7:30 PM flexible dinner.
2. Choose **Demo Playback** if live Ollama credentials are not configured. KOI labels this as scripted fixture playback. Otherwise choose **Trigger flight cancellation** for actual Ollama Cloud agent calls.
3. In Round 0, compare Travel and Commitments' on-time Option A with Budget's cheaper Option B. Read the peer objections and evidence/tool details.
4. Watch Alternatives activate and search the PHL connection. Round 1 revises to Option C: synthetic SFO–PHL flight, transfer, Amtrak, and local transfer, totaling $290 with a 4:30 PM venue arrival.
5. Show each agent's vote on the same evidence version, the hard-constraint check, and the baseline's cheaper but late Option B.
6. Click **New information: Option C unavailable**. KOI increases the evidence version, clears stale votes, reassesses the remaining routes, and asks for a human decision because neither remaining option satisfies both constraints.
7. Download the JSON history to show individual responses, including initial proposals and tool traces.

The **Infeasible · $180 budget** scenario demonstrates that KOI keeps disagreement or asks a person instead of relaxing a hard constraint.

## Environment and API

| Variable | Purpose |
|---|---|
| `OLLAMA_API_KEY` | Bearer credential for server-side `https://ollama.com/api/chat` requests |
| `OLLAMA_MODEL` | Ollama Cloud model name verified in the user's account/catalog; no default is guessed |
| `VITE_API_URL` | Optional frontend API base URL; defaults to `http://localhost:8000` |

All model requests use `stream: false` and the backend reads `message.content`, following the [Ollama chat API](https://docs.ollama.com/api/chat). The backend validates it with Pydantic and allows one bounded repair attempt. Invalid output, timeouts, and model errors become explicit error responses; they are not converted to mock agent answers.

Endpoints: `POST /api/runs`, `GET /api/runs/{run_id}`, `GET /api/runs/{run_id}/events`, `GET /api/runs/{run_id}/responses`, `POST /api/runs/{run_id}/evidence`, and `GET /api/runs/{run_id}/export`.

## Checks

```bash
cd /Users/anualluri/KOI
source .venv/bin/activate
PYTHONPATH=backend python -m pytest backend/tests -q
cd frontend
npm run build
```

