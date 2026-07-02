# RPS 2.0 — Interview Walkthrough Guide

This is your prep document. It maps every claim on your résumé to the exact code
that backs it, gives you a tight demo script, arms you with honest ways to talk
about the harder numbers, and lists the questions you're most likely to get with
strong answers ready to go.

Read it once end-to-end, then rehearse the **2-minute pitch** and the **demo
script** out loud until they're natural.

---

## 1. The 2-minute pitch (memorise this)

> "RPS 2.0 is an agentic reservation system for a vehicle fleet. The original
> system was a conventional Java backend where staff booked vehicles through
> forms. I added a conversational layer on top: you talk to it in plain English,
> and an agentic workflow built on **LangGraph** interprets what you want,
> routes to the right action, and runs it against a transactional data layer.
>
> The workflow is a state graph — an `understand` node does intent and entity
> extraction, a conditional edge routes on the intent, and each capability
> (check availability, book, cancel, list, onboard) is its own node. That keeps
> the control flow explicit and makes new capabilities cheap to add.
>
> Cross-cutting concerns — audit logging, timing, security — are handled with an
> **AOP-style aspect layer** so they wrap every data operation without polluting
> business logic. The data layer is SQLAlchemy, so it runs on SQLite locally and
> MySQL in production by changing a connection string. The NLU is dual-mode: it
> uses an LLM when a key is configured, and falls back to a deterministic parser
> so it's reliable offline and in tests.
>
> Net effect: the staff workflow that used to be multi-step form entry becomes a
> single sentence."

That hits every keyword on your résumé — LangGraph, agentic workflow, FastAPI,
natural-language interface, Spring AOP / cross-cutting concerns, MySQL, data
integrity — and it's all true of what you'll have running on screen.

---

## 2. Live demo script (3–4 minutes)

Have the UI open at `http://127.0.0.1:8000` before you share your screen.

**1. Orient them (10 sec).** "Three panels: the assistant on the left, live
fleet and reservations in the middle, and on the right the agent pipeline plus
the cross-cutting audit trail."

**2. Show understanding (type):** `is an SUV free this weekend?`
- Point at the **Agent pipeline** panel lighting up: `understand → route →
  check availability`.
- "Notice it parsed *'this weekend'* into real dates and filtered to SUVs — that
  date parsing is dependency-free, in `dateparse.py`."

**3. Book it (type):** `book V-104 for Maria Dec 1 to Dec 4`
- The reservation table gets a new row; the fleet lamp for that vehicle flips.
- "The booking does an atomic re-check inside the transaction before it commits,
  so two requests can't double-book the same vehicle for overlapping dates."

**4. Prove the integrity claim (type):** `book V-104 for John Dec 2 to Dec 3`
- It's **rejected** — overlapping window.
- "That's the data-integrity guarantee in action — the availability engine uses
  half-open interval logic so adjacent bookings are fine but overlaps are
  refused."

**5. Show the AOP panel.** "Every one of those operations emitted an audit entry
and a latency sample through the aspect layer — that's the logging and security
concern factored out of the business logic, same idea as Spring AOP."

**6. Cancel (type):** `cancel R-1001` — table updates, lamp frees up.

Close with: "And this is all running locally on SQLite with the rule-based
parser — point it at MySQL and Claude with two environment variables and nothing
else changes."

---

## 3. Résumé bullet → code map

Keep this open in case they drill into a specific claim.

| Résumé bullet | Where it lives | What to say |
|---|---|---|
| "intelligent agentic workflow using **LangGraph**, automating complex scheduling" | `rps/agent/graph.py`, `rps/agent/nodes.py` | Real compiled `StateGraph`: entry node → conditional edge → action nodes → END. Show `build_graph()`. |
| "natural language interface with **Python and FastAPI** … conversational AI" | `rps/api.py` (`POST /api/chat`), `rps/nlu.py` | FastAPI endpoint runs the agent; NLU extracts intent + entities. |
| "vehicle availability and registration management" | `repository.find_available`, `repository.register_vehicle` | The availability engine + onboarding flow. |
| "**Spring AOP** to modularize cross-cutting concerns such as logging and security" | `rps/aspects.py` | `@audit_log` / `@timed` decorators + `require_admin_key` dependency. The Python analog of AOP advice around join points. |
| "Configured **JDBC** and managed **MySQL** transactions … 100% data integrity" | `rps/database.py`, `rps/repository.py` | SQLAlchemy = the JDBC analog; `transactional()` = atomic commit/rollback; the booking re-check enforces integrity. MySQL via connection string. |
| "70% reduction in manual scheduling workload" | the whole conversational flow | Multi-step form entry collapses to one sentence; see framing in §4. |

---

## 4. Honest framing for the hard parts

Interviewers respect candidates who are precise about what's real. Never claim
the prototype is the production system. Here's how to be both honest and strong.

**On "100% data integrity":**
> "That refers to the integrity guarantee in the booking path — bookings are
> atomic and the availability engine refuses any overlapping reservation, so you
> can't get a double-booking or a partial write. In the prototype that's
> enforced with a transactional scope and an in-transaction re-check; in the
> production Java system it was JDBC transactions against MySQL."

If pushed on the literal "100%": "It's a way of saying the invariant *no
overlapping bookings, no partial writes* holds for every write path — I can show
you the rejection happen live."

**On "70% reduction in manual workload":**
> "That's an estimate from collapsing a multi-step manual process — checking a
> calendar, finding a free vehicle, entering a record — into a single natural-
> language request the system fulfils. I'd frame it as a directional efficiency
> gain rather than a measured benchmark."

**On the LLM vs rules NLU:**
> "The NLU is dual-mode by design. With an API key it uses an LLM for intent and
> entity extraction; without one it uses a deterministic parser. The LLM path
> falls back to rules on any error. I did that so the system is reliable offline,
> cheap to test, and never hard-down because of an external dependency."

This is a *strength* — it shows you think about failure modes and cost.

**On SQLite vs MySQL:**
> "It runs on SQLite locally so it's zero-setup, but the data layer is
> SQLAlchemy, so it's the same code against MySQL — you change the connection
> string. The original system was MySQL via JDBC."

**On "Spring AOP" in a Python project:**
> "The original cross-cutting concerns were done with Spring AOP in the Java
> backend. In this Python prototype I implemented the same pattern with
> decorators and a FastAPI dependency — advice wrapping join points — so logging,
> timing, and security stay out of the business logic. Same architectural idea,
> idiomatic to each language."

---

## 5. Architecture talking points (go deeper on request)

**Why LangGraph and not a chain or a plain function?**
> "Because the control flow is a graph, not a line. I wanted explicit routing —
> one classification step, then a conditional edge to exactly one action. That's
> readable, testable, and extensible: a new capability is a node plus a route
> entry. A graph also gives me a natural place to add parallel or multi-step
> flows later without rewriting the orchestration."

**How does state flow through the graph?**
> "There's a typed `AgentState` — the message, the extracted intent and
> entities, the result, the reply, and a `trace`. Nodes return partial state
> updates that LangGraph merges. The `trace` field uses an additive reducer so
> each node appends its step — that's what drives the live pipeline view."

**How do you prevent double-booking under concurrency?**
> "`create_reservation` re-checks availability *inside* the same transaction
> right before insert, so even if two requests pass the initial availability
> check, only one commits. The overlap test is half-open intervals — `[start,
> end)` — so back-to-back bookings don't falsely collide."

**Where would this break at scale, and what next?**
> "Three things: the in-transaction re-check would move to a DB-level constraint
> or row lock for true concurrency; the audit trail is in-memory for the demo and
> would go to a real sink; and I'd add parallel action nodes via LangGraph's
> `Send` API for fan-out cases. None of those change the architecture — they're
> swaps behind the existing seams."

**Why a deterministic fallback instead of just retrying the LLM?**
> "Cost, latency, and determinism. Tests and demos shouldn't depend on a network
> call or a key, and intent classification for a bounded domain like this is very
> tractable with rules. The LLM adds robustness to phrasing, not new capability."

---

## 6. Likely questions, with answers ready

**Q: Is this the actual production system or a rebuild?**
> "It's a faithful prototype I built to demonstrate the architecture and the
> agentic layer end-to-end. The production system was the Java/Spring backend;
> this re-creates the design — the workflow, the AOP concerns, the transactional
> data layer — in a form I can run and walk through."

**Q: Did you use LangGraph in production or just here?**
> Answer truthfully based on your experience. If it was a prototype/enhancement:
> "The agentic LangGraph layer was the enhancement I designed on top of the
> existing system; this is where I can show it running." Don't claim a
> production deployment you didn't ship.

**Q: Walk me through what happens when I type a booking.**
> "FastAPI receives it at `/api/chat` and invokes the compiled graph. The
> `understand` node runs NLU and writes intent + entities into state. The
> conditional edge routes to `create_reservation`. That node parses the dates,
> resolves the vehicle, and calls the repository, which opens a transaction,
> re-checks availability, inserts, and commits — emitting audit and timing
> entries through the aspects. The final state's reply and trace come back as
> JSON, and the UI renders the bubble, refreshes the board, and animates the
> pipeline."

**Q: How is this tested?**
> "17 tests covering the overlap engine, cancellation, NLU intent and entity
> extraction, the date parser, the compiled graph, and the FastAPI endpoints
> through TestClient. They run fully offline against a temp SQLite DB with the
> rule-based parser, so they're deterministic."

**Q: How would you add a new capability, like extending a reservation?**
> "Add a `node_extend_reservation` in `nodes.py`, register it in `graph.py`'s
> action map and route table, and add an `extend_reservation` repository method
> with the same transactional + aspect wrapping. That's it — the seams are
> already there."

**Q: What was the hardest part?**
> Pick something real. A good honest answer: "Getting the availability semantics
> right — half-open intervals so adjacencies don't false-collide — and making the
> NLU degrade gracefully so a demo never depends on an external service."

**Q: Security?**
> "Mutating admin endpoints are guarded by an API-key dependency — the security
> cross-cutting concern. In production that'd be real auth/RBAC; the point here is
> that it's an aspect, applied declaratively, not scattered through handlers."

---

## 7. Pre-interview checklist

- [ ] `pip install -r requirements.txt` in a clean environment — confirm it runs.
- [ ] `python run.py`, open the UI, run the **entire demo script** once.
- [ ] `pytest -q` — confirm 17 passing, so you can say "and it's tested" honestly.
- [ ] Open `rps/agent/graph.py`, `rps/aspects.py`, `rps/repository.py` in tabs —
      these are the three files they're most likely to ask to see.
- [ ] Re-read §4 (honest framing). If you internalise nothing else, internalise
      how you'll talk about the "100%" and "70%" numbers.
- [ ] Know your own boundary: what you designed/built vs. what the original
      system did. State it the same way every time.

You built something real that runs and is tested. Walk in and show it.
