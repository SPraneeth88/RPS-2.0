# RPS 2.0 — AI-Agentic Reservation Processing System

A working prototype of an intelligent, conversational reservation system for a
vehicle fleet. You talk to it in plain English ("is an SUV free this weekend?",
"book V-101 for Maria Dec 1 to Dec 4") and an **agentic workflow built on
LangGraph** classifies the intent, dispatches to the right action, runs it
against a transactional data layer, and replies — all visualised live in a
dispatch-console UI.

It runs **fully locally with zero external services** (SQLite + a deterministic
rule-based NLU), and upgrades cleanly to **Claude-backed NLU** and **MySQL** by
setting two environment variables.

---

## Quick start

```bash
# 1. (optional) create a virtualenv
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. install
pip install -r requirements.txt

# 3. run
python run.py
```

Then open **http://127.0.0.1:8000**.

On first launch the database is created and seeded automatically (10 vehicles,
3 reservations). No API keys, no database server, no build step.

### Try these
- `show me the fleet`
- `is an SUV free this weekend?`
- `book V-101 for Maria Dec 1 to Dec 4`
- `show active reservations`
- `cancel R-1001`
- `add a Tesla Model 3, type EV, reg KA01AB1234`

---

## What you're looking at

The single-screen **dispatch console** has three live panels:

| Panel | What it shows |
|-------|---------------|
| **Assistant** | The natural-language conversation. Each reply is tagged with the detected intent and which NLU path produced it (`rules` or `llm`). |
| **Fleet board + Reservations** | Real fleet state with availability lamps (green/amber/red) and the live reservation table. Both refresh after every booking or cancellation. |
| **Agent pipeline + Cross-cutting (AOP)** | The LangGraph nodes lighting up per request (`understand → route → action`), plus the live audit trail and average latency emitted by the AOP layer. |

---

## Architecture

![System architecture](docs/diagrams/01_system_architecture.png)

The agent is the orchestrator; the repository is the only tier that touches the
database; the AOP aspects wrap repository operations so logging, timing, and
security stay out of business logic. Swapping SQLite→MySQL or rules→Claude is a
config change, not a topology change.

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the LangGraph agent topology and a
booking request sequence diagram.

### Layers

- **`rps/agent/`** — the LangGraph workflow. `graph.py` compiles a `StateGraph`
  with a single `understand` entry node, a **conditional edge** that routes on
  the classified intent, and one action node per capability. Adding a capability
  is one new node + one route entry.
- **`rps/nlu.py`** — dual-mode natural-language understanding. With
  `ANTHROPIC_API_KEY` set it asks **Claude** to extract intent + entities as
  JSON; otherwise it uses a deterministic regex/keyword parser. The LLM path
  always falls back to rules on any error, so the demo never breaks.
- **`rps/dateparse.py`** — dependency-free natural-date parser ("next tuesday",
  "this weekend", "Dec 1 to Dec 4", "for 3 days").
- **`rps/repository.py`** — the data-access tier (the JDBC analog). All DB
  access funnels through here; nothing else touches the ORM session. Includes
  the availability engine (half-open interval overlap logic) and an atomic
  re-check inside `create_reservation` to prevent double-booking.
- **`rps/aspects.py`** — the **AOP layer**. `@audit_log` and `@timed`
  decorators wrap repository operations to add logging/auditing and latency
  measurement *without* touching business logic; `require_admin_key` is a
  FastAPI dependency implementing the security concern; `transactional()` gives
  atomic commit/rollback.
- **`rps/database.py` / `rps/models.py`** — SQLAlchemy engine, session,
  `transactional()` context manager, and the `Vehicle` / `Reservation` models.
- **`rps/api.py`** — FastAPI app and REST surface.
- **`rps/static/`** — the dispatch-console UI (vanilla HTML/CSS/JS, no build).

---

## REST API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/chat` | Conversational entry point — runs the agent. |
| `GET`  | `/api/vehicles` | Fleet list (optional `?vehicle_type=SUV`). |
| `GET`  | `/api/reservations` | Reservations (optional `?active_only=true`). |
| `POST` | `/api/vehicles` | Onboard a vehicle (protected by the security aspect). |
| `GET`  | `/api/summary` | Header counters. |
| `GET`  | `/api/metrics` | AOP observability snapshot (audit trail + latency). |
| `GET`  | `/api/health` | Liveness + active NLU mode + database backend. |

Interactive API docs are available at **http://127.0.0.1:8000/docs**.

---

## Configuration

Everything is environment-driven (see `.env.example`). Copy it to `.env` to
customise; all values have working defaults.

### Enable Claude-backed NLU
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python run.py            # the NLU badge in the header flips to "llm"
```

### Point at MySQL instead of SQLite
```bash
pip install pymysql
export DATABASE_URL="mysql+pymysql://user:password@localhost:3306/rps"
python run.py
```
No code changes — the SQLAlchemy layer is backend-agnostic. The `DB` badge in
the header reflects whichever backend is active.

### Protect admin endpoints
```bash
export RPS_ADMIN_KEY="some-secret"
# POST /api/vehicles now requires header  X-Admin-Key: some-secret
```

---

## Enhancements / roadmap

The prototype is deliberately built with clean seams so each of these is a swap
behind an existing interface, not a rewrite:

- **Parallel action nodes via LangGraph's `Send` API.** Fan-out cases (e.g.
  check availability across multiple vehicle types at once, or score several
  candidate vehicles in parallel) become concurrent node executions instead of
  sequential calls — the orchestration already lives in `graph.py`.
- **Database-level concurrency guarantees.** The in-transaction availability
  re-check that prevents double-booking would be reinforced with a DB exclusion
  constraint / row lock so correctness holds under true parallel load, not just
  the application-level check.
- **Durable observability sink.** The AOP audit trail and latency samples are
  in-memory deques for the demo; in production they'd stream to structured logs
  / OpenTelemetry, with the same `@audit_log` / `@timed` aspects unchanged.
- **Real authn/authz.** The `require_admin_key` security aspect would become
  proper auth with role-based access control — still applied declaratively as an
  aspect, not scattered through handlers.
- **Conversation memory.** Add a short-term context store so multi-turn flows
  ("…actually make that 3 days", "book the first one") resolve against prior
  turns — a natural fit for LangGraph's checkpointer.
- **Multi-channel surface.** The same agent behind `/api/chat` can back a Slack
  bot, a phone/IVR front-end, or staff tooling without touching the workflow.

## Tests

```bash
pip install pytest httpx
pytest -q
```

The suite (17 tests) covers the availability/overlap engine, cancellation, the
NLU intent + entity extraction, the natural-date parser, the compiled LangGraph,
and the FastAPI endpoints end-to-end. Tests run entirely offline (rule-based NLU,
temporary SQLite DB) so they're deterministic and CI-friendly.

---

## Project layout

```
rps2/
├── run.py                 # entry point: seed-if-empty, then serve
├── seed_data.py           # idempotent demo data
├── requirements.txt
├── .env.example
├── README.md
├── ARCHITECTURE.md        # Mermaid diagrams (system · agent · sequence)
├── INTERVIEW_GUIDE.md     # walkthrough + talking points
├── docs/
│   └── diagrams/          # PNG + SVG exports of the diagrams
├── rps/
│   ├── api.py             # FastAPI app + REST surface
│   ├── config.py          # env-driven settings
│   ├── database.py        # engine, session, transactional()
│   ├── models.py          # Vehicle, Reservation
│   ├── repository.py      # data-access tier + availability engine
│   ├── aspects.py         # AOP: audit_log, timed, require_admin_key
│   ├── nlu.py             # dual-mode NLU (Claude or rules)
│   ├── dateparse.py       # natural-language date parsing
│   ├── schemas.py         # Pydantic request/response models
│   ├── agent/
│   │   ├── state.py       # AgentState TypedDict
│   │   ├── nodes.py       # LangGraph node functions
│   │   └── graph.py       # StateGraph assembly
│   └── static/            # dispatch-console UI
└── tests/
```

See **INTERVIEW_GUIDE.md** for a full walkthrough and talking points.
