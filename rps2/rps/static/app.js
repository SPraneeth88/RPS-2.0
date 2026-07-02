/* ============================================================
   RPS 2.0 — Dispatch console front-end controller
   Talks to the FastAPI backend, renders the fleet board,
   the reservation table, the live LangGraph pipeline and the
   AOP audit trail. No build step, no framework — just fetch.
   ============================================================ */
"use strict";

const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const API = {
  health:       () => fetch("/api/health").then(j),
  summary:      () => fetch("/api/summary").then(j),
  vehicles:     () => fetch("/api/vehicles").then(j),
  reservations: () => fetch("/api/reservations?active_only=true").then(j),
  metrics:      () => fetch("/api/metrics").then(j),
  chat:         (message) =>
    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    }).then(j),
};

function j(r) {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

/* ---------- Status lamp helper ---------- */
const LAMP = { available: "ok", confirmed: "warn", "on hire": "warn", maintenance: "bad" };
function lampClass(status) {
  return LAMP[status] || "ok";
}

/* ---------- Suggestion chips ---------- */
const SUGGESTIONS = [
  "show me the fleet",
  "is an SUV free this weekend?",
  "book V-101 for Maria Dec 1 to Dec 4",
  "show active reservations",
  "cancel R-1001",
];

/* ============================================================
   Chat
   ============================================================ */
const chatLog = $("#chat-log");

function addBubble(text, who, meta) {
  const b = document.createElement("div");
  b.className = `bubble ${who}`;
  b.textContent = text;
  if (meta) {
    const m = document.createElement("span");
    m.className = "meta";
    m.innerHTML = meta;
    b.appendChild(m);
  }
  chatLog.appendChild(b);
  chatLog.scrollTop = chatLog.scrollHeight;
  return b;
}

function thinkingBubble() {
  const b = document.createElement("div");
  b.className = "bubble bot";
  b.innerHTML = `<span class="dots"><i></i><i></i><i></i></span>`;
  chatLog.appendChild(b);
  chatLog.scrollTop = chatLog.scrollHeight;
  return b;
}

/* ============================================================
   LangGraph pipeline animation
   The static markup has three steps: understand · route · action.
   We light them up in sequence and label the action step with the
   node that actually ran (from the response trace).
   ============================================================ */
const pipelineSteps = () => $$("#pipeline .step");

function resetPipeline() {
  pipelineSteps().forEach((s) => {
    s.classList.remove("active");
    s.classList.add("idle");
  });
}

async function animatePipeline(trace) {
  const steps = pipelineSteps();
  // Derive a friendly action label from the last trace node.
  const actionNode = trace && trace.length ? trace[trace.length - 1].node : "action";
  const actionLabel = actionNode.replace(/_/g, " ");
  const actionSummary = trace && trace.length ? trace[trace.length - 1].summary : "";

  steps[2].querySelector("b").textContent = actionLabel;
  if (actionSummary) steps[2].querySelector("em").textContent = actionSummary;

  for (let i = 0; i < steps.length; i++) {
    steps[i].classList.remove("idle");
    steps[i].classList.add("active");
    await sleep(230);
  }
}

const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

/* ============================================================
   Renderers
   ============================================================ */
function renderCounters(s) {
  $("#c-total").textContent  = s.total_vehicles;
  $("#c-avail").textContent  = s.available;
  $("#c-active").textContent = s.active_reservations;
  $("#c-maint").textContent  = s.maintenance;
}

function renderFleet(vehicles, flashIds = []) {
  const host = $("#fleet");
  host.innerHTML = "";
  if (!vehicles.length) {
    host.innerHTML = `<div class="empty">No vehicles in the fleet.</div>`;
    return;
  }
  for (const v of vehicles) {
    const card = document.createElement("div");
    card.className = "vcard" + (flashIds.includes(v.id) ? " flash" : "");
    card.innerHTML = `
      <div class="vid"><i class="lamp ${lampClass(v.status)}"></i>${v.id}</div>
      <div class="vname">${escapeHtml(v.make)} ${escapeHtml(v.model)}</div>
      <div class="vmeta">${escapeHtml(v.vehicle_type)} · ${escapeHtml(v.location)}</div>
      <div class="vrate">$${Number(v.daily_rate).toFixed(0)}/day · ${v.status}</div>
    `;
    host.appendChild(card);
  }
}

function renderReservations(reservations, newIds = []) {
  const body = $("#res-body");
  $("#res-count").textContent = `${reservations.length} active`;
  body.innerHTML = "";
  if (!reservations.length) {
    body.innerHTML = `<tr><td colspan="5" class="empty">No active reservations.</td></tr>`;
    return;
  }
  for (const r of reservations) {
    const tr = document.createElement("tr");
    if (newIds.includes(r.id)) tr.className = "new";
    tr.innerHTML = `
      <td>${r.id}</td>
      <td>${r.vehicle_id}</td>
      <td>${escapeHtml(r.customer_name)}</td>
      <td>${r.start_date} → ${r.end_date}</td>
      <td>${r.nights}</td>
    `;
    body.appendChild(tr);
  }
}

function renderAudit(metrics) {
  const host = $("#audit");
  const trail = metrics.audit_trail || [];
  $("#latency-tag").textContent = `${metrics.latency.avg_ms} ms avg`;
  host.innerHTML = "";
  if (!trail.length) {
    host.innerHTML = `<div class="empty">No joinpoints recorded yet.</div>`;
    return;
  }
  for (const e of trail.slice(0, 12)) {
    const row = document.createElement("div");
    row.className = "audit-row";
    const t = new Date(e.ts * 1000).toLocaleTimeString([], { hour12: false });
    row.innerHTML = `
      <span class="a-status ${e.status}"></span>
      <span class="a-action">${escapeHtml(e.action)}</span>
      <span class="a-ms">${t}</span>
    `;
    host.appendChild(row);
  }
}

function renderChips() {
  const host = $("#chips");
  host.innerHTML = "";
  for (const text of SUGGESTIONS) {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.textContent = text;
    chip.onclick = () => {
      $("#msg").value = text;
      send();
    };
    host.appendChild(chip);
  }
}

/* ---------- small utils ---------- */
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function diffNewIds(before, after, key = "id") {
  const seen = new Set(before.map((x) => x[key]));
  return after.filter((x) => !seen.has(x[key])).map((x) => x[key]);
}

/* ============================================================
   Data refresh
   ============================================================ */
let lastVehicles = [];
let lastReservations = [];

async function refreshBoard(flashVehicleIds = [], newResIds = []) {
  const [{ vehicles }, { reservations }, summary, metrics] = await Promise.all([
    API.vehicles(),
    API.reservations(),
    API.summary(),
    API.metrics(),
  ]);
  renderFleet(vehicles, flashVehicleIds);
  renderReservations(reservations, newResIds);
  renderCounters(summary);
  renderAudit(metrics);
  lastVehicles = vehicles;
  lastReservations = reservations;
}

/* ============================================================
   Send flow
   ============================================================ */
let busy = false;

async function send() {
  const input = $("#msg");
  const message = input.value.trim();
  if (!message || busy) return;

  busy = true;
  $("#send").disabled = true;
  input.value = "";
  addBubble(message, "user");
  resetPipeline();
  const thinking = thinkingBubble();

  try {
    const beforeRes = lastReservations.slice();
    const beforeVeh = lastVehicles.slice();

    const res = await API.chat(message);

    // Animate the graph while we keep the thinking bubble up briefly.
    await animatePipeline(res.trace);

    thinking.remove();
    const meta =
      `intent <b>${escapeHtml(res.intent)}</b> · nlu <b>${escapeHtml(res.nlu_source)}</b>`;
    addBubble(res.reply, "bot", meta);

    // Refresh the board; flash anything that changed.
    await refreshBoard();
    const newResIds = diffNewIds(beforeRes, lastReservations);
    const newVehIds = diffNewIds(beforeVeh, lastVehicles);
    if (newResIds.length || newVehIds.length) {
      // Re-render once more with flash classes now that we know the diff.
      const touchedVeh = newResIds
        .map((id) => (lastReservations.find((r) => r.id === id) || {}).vehicle_id)
        .filter(Boolean)
        .concat(newVehIds);
      renderFleet(lastVehicles, touchedVeh);
      renderReservations(lastReservations, newResIds);
    }
  } catch (err) {
    thinking.remove();
    addBubble(`Something went wrong: ${err.message}`, "bot");
  } finally {
    busy = false;
    $("#send").disabled = false;
    input.focus();
  }
}

/* ============================================================
   Boot
   ============================================================ */
async function boot() {
  renderChips();

  // Header badges from /health.
  try {
    const h = await API.health();
    $("#nlu-badge").innerHTML = `NLU&nbsp;·&nbsp;<b>${h.nlu}</b>`;
    $("#db-badge").innerHTML  = `DB&nbsp;·&nbsp;<b>${h.database}</b>`;
    $("#footer-note").textContent =
      h.nlu === "llm"
        ? "LLM-backed NLU active (Claude)"
        : "deterministic rule-based NLU (offline mode)";
  } catch {
    $("#footer-note").textContent = "backend unreachable";
  }

  await refreshBoard();

  addBubble(
    "Dispatch online. I can check availability, book and cancel reservations, " +
      "list the fleet, and onboard vehicles. Tap a suggestion below or just ask.",
    "bot"
  );

  $("#send").onclick = send;
  $("#msg").addEventListener("keydown", (e) => {
    if (e.key === "Enter") send();
  });
  $("#msg").focus();
}

document.addEventListener("DOMContentLoaded", boot);
