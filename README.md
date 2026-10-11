# KOI · live travel recovery research

KOI helps a traveler respond to a disrupted flight. The user enters the airline, flight number, route, travel date, budget, arrival deadline, and important plans. Four role-based agents search the web through Ollama for replacement flights and ground transport, review source links and excerpts, and respond to one another in a second round.

Live research uses web search for Google Flights and airline results, lower-cost options, arrival feasibility, and alternatives such as buses, trains, ferries, and nearby airports. Recommendations include cited source links; an exact booking link is shown only when a route- and date-specific result is found. Otherwise, the airline/operator and service number appear prominently with links to the supporting web sources.

Search results are leads, not guaranteed inventory. KOI does not book travel, and fares or availability may change. The traveler should confirm the details on the linked operator page. Entered trip details are sent to Ollama Cloud for web search and agent analysis; the form does not request booking references or passenger personal information.

## Stack

- React and Vite: website and live event display
- Python and FastAPI: run API and server-side web calls
- LangGraph: bounded peer-review rounds
- Ollama Cloud: agent language model, web search, and page fetch
- Pydantic: request and agent response validation
- Server-sent events: stream search and agent progress to the page

## Project layout

```text
backend/
  app/
    engine.py          Web research, agent rounds, and demo playback
    fixtures/          Sample scenarios retained for offline demo playback
    main.py            FastAPI and SSE endpoints
    models.py          Trip input and validated agent response schemas
    ollama.py          Server-side Ollama chat, web search, and web fetch
    tools.py           Bounded sample route tools for demo playback
  .env.example
frontend/
  src/App.jsx          Trip form, progress animation, discussions, and sources
  src/styles.css       Responsive KOI interface
```

## Run locally

Requirements: Python 3.11+, Node.js 20+, and an Ollama account/API key with a Cloud model name.

In Terminal 1:

```bash
cd /Users/anualluri/KOI
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
open -e backend/.env
```

Set `OLLAMA_API_KEY` and `OLLAMA_MODEL` in `backend/.env`, save it, then start the backend:

```bash
uvicorn app.main:app --app-dir backend --reload --port 8000
```

In Terminal 2:

```bash
cd /Users/anualluri/KOI/frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Keep `backend/.env` private; Git ignores it. The frontend receives only whether each key/model value is configured, never the keys themselves. If the backend is already running, restart it after changing `.env`.

## Live research flow

1. The user submits trip details to `POST /api/runs`.
2. Each of the four agents runs a role-specific live query through Ollama web search. Queries include the airline and flight number, prioritize Google Flights for air alternatives, and look for official bus, train, and ferry operators. KOI fetches up to eight HTTPS result pages and keeps their links and excerpts as evidence.
3. Agents receive their search results and a shared source index, then write an initial response. In the next round, each receives the other agents’ messages and can revise its recommendation or raise a concern.
4. FastAPI streams search progress, findings, messages, and citations to the React page. The recommended option shows the airline/operator and service number in its title when a source provides it. A direct booking link is labeled as such only when the agents find a route/date-specific itinerary page; otherwise the page links to the evidence source.

If web search is unavailable or no sources are returned, KOI reports an error. Live mode does not substitute synthetic route data. Scripted fixture playback remains available to the backend for offline development and tests; it is separate from the website’s live research form.

## Environment variables

| Variable | Purpose |
|---|---|
| `OLLAMA_API_KEY` | Server-side bearer credential for Ollama chat, web search, and web fetch |
| `OLLAMA_MODEL` | Ollama Cloud model name available to the account |
| `VITE_API_URL` | Optional frontend API base URL; defaults to `http://localhost:8000` |

Main endpoints: `POST /api/runs`, `GET /api/runs/{run_id}`, `GET /api/runs/{run_id}/events`, `GET /api/runs/{run_id}/responses`, and `GET /api/runs/{run_id}/export`.
