# RPS 2.0 — Architecture

Three views of the system: the **layered architecture**, the **LangGraph agent
topology**, and a **request sequence** for a booking. All diagrams are Mermaid
and render automatically on GitHub.

> Static exports (PNG + SVG) live in [`docs/diagrams/`](docs/diagrams) for use in
> slides, one-pagers, or anywhere Mermaid isn't rendered.

---

## 1. System architecture

How a request flows through the tiers, and where cross-cutting concerns apply.

```mermaid
flowchart TD
    user(["User · natural language"])

    subgraph web["Web / API tier"]
        ui["Dispatch console UI<br/>(static HTML/CSS/JS)"]
        api["FastAPI<br/>POST /api/chat · REST"]
    end

    subgraph agent["Agentic workflow · LangGraph"]
        lg["StateGraph<br/>understand → route → action → END"]
    end

    subgraph nlu["NLU (dual-mode)"]
        llm["Claude<br/>(if API key set)"]
        rules["Deterministic parser<br/>(offline fallback)"]
    end

    subgraph data["Data-access tier"]
        repo["Repository<br/>availability engine · atomic writes"]
        orm["SQLAlchemy"]
        db[("SQLite (local)<br/>MySQL (prod)")]
    end

    subgraph aspects["Cross-cutting · AOP"]
        audit["@audit_log"]
        timed["@timed"]
        sec["require_admin_key"]
        tx["transactional()"]
    end

    user --> ui --> api --> lg
    lg -->|node_understand| nlu
    llm -.fallback on error.-> rules
    lg -->|action nodes| repo --> orm --> db

    aspects -. wraps .-> repo
    api --- sec

    classDef store fill:#1C2536,stroke:#5BD6C0,color:#E6ECF5;
    classDef cross fill:#222D40,stroke:#E8B055,color:#E6ECF5,stroke-dasharray:4 3;
    class db store;
    class audit,timed,sec,tx cross;
```

**Reading it:** the agent is the orchestrator; the repository is the only thing
that touches the database; the AOP aspects wrap repository operations so logging,
timing, and security never leak into business logic. Swapping SQLite for MySQL or
rules for Claude changes a config value, not the topology.

---

## 2. LangGraph agent topology

The compiled `StateGraph` in `rps/agent/graph.py`. One entry node, a single
conditional edge that routes on the classified intent, and one node per
capability — all terminating at `END`.

```mermaid
flowchart LR
    start([START]) --> understand["understand<br/><i>NLU: intent + entities</i>"]
    understand -->|conditional route on intent| router{{route}}

    router -->|check_availability| avail["check_availability"]
    router -->|create_reservation| book["create_reservation"]
    router -->|cancel_reservation| cancel["cancel_reservation"]
    router -->|list_vehicles| lveh["list_vehicles"]
    router -->|list_reservations| lres["list_reservations"]
    router -->|register_vehicle| reg["register_vehicle"]
    router -->|greeting / help| small["smalltalk"]
    router -->|unrecognised| fb["fallback"]

    avail --> done([END])
    book --> done
    cancel --> done
    lveh --> done
    lres --> done
    reg --> done
    small --> done
    fb --> done

    classDef entry fill:#1C2536,stroke:#5BD6C0,color:#E6ECF5;
    classDef action fill:#161D2B,stroke:#2A3547,color:#E6ECF5;
    class understand entry;
    class avail,book,cancel,lveh,lres,reg,small,fb action;
```

**Why a graph:** adding a capability is one new node plus one route entry — the
control flow stays explicit and testable. State (`message`, `intent`,
`entities`, `result`, `reply`, `trace`) flows as partial updates that LangGraph
merges; the `trace` field uses an additive reducer, which is what drives the live
pipeline panel in the UI.

---

## 3. Booking request — sequence

What actually happens on `book V-104 for Maria Dec 1 to Dec 4`, including the
in-transaction re-check that guarantees no double-booking.

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant UI as Console UI
    participant API as FastAPI
    participant G as LangGraph
    participant N as NLU
    participant R as Repository
    participant DB as SQLAlchemy / DB
    participant A as AOP aspects

    U->>UI: "book V-104 for Maria Dec 1 to Dec 4"
    UI->>API: POST /api/chat
    API->>G: invoke(state)
    G->>N: node_understand
    N-->>G: intent=create_reservation,<br/>entities{vehicle, dates, customer}
    Note over G: conditional edge routes<br/>to create_reservation
    G->>R: create_reservation(...)
    activate A
    R->>DB: BEGIN (transactional)
    R->>DB: re-check availability (overlap test)
    alt window is free
        R->>DB: INSERT reservation
        R->>DB: COMMIT
        DB-->>R: reservation R-1004
        R-->>A: audit ok · latency sample
        R-->>G: result confirmed
    else overlap detected
        R->>DB: ROLLBACK
        R-->>A: audit ok · latency sample
        R-->>G: result rejected (integrity)
    end
    deactivate A
    G-->>API: reply + trace
    API-->>UI: JSON
    UI-->>U: chat reply · board refresh · pipeline animation
```

**The integrity guarantee:** the availability re-check happens *inside* the same
transaction immediately before insert, so even if two requests both pass the
initial check, only one commits. The overlap test uses half-open intervals
`[start, end)`, so back-to-back bookings are allowed but any true overlap is
refused.
