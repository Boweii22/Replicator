const $ = (id) => document.getElementById(id);
let activeSource;
let activePoll;
const fields = [
  ["attempts", "attempts-out", (v) => v],
  ["minutes", "minutes-out", (v) => `${v} min`],
  ["cost", "cost-out", (v) => `$${Number(v).toFixed(2)}`],
];
fields.forEach(([input, output, format]) => $(input).addEventListener("input", e => $(output).value = format(e.target.value)));
setInterval(() => $("clock").textContent = new Date().toISOString().slice(11, 19) + "Z", 1000);

const sharedRunId = new URLSearchParams(location.search).get("run");
if (sharedRunId) {
  fetch(`/replications/${sharedRunId}`).then(response => response.ok ? response.json() : Promise.reject(new Error("Run not found")))
    .then(run => showExistingRun(run)).catch(error => console.error(error));
}

document.querySelectorAll("nav button[data-view]").forEach(button => button.addEventListener("click", async () => {
  document.querySelectorAll("nav button").forEach(item => item.classList.remove("nav-active"));
  button.classList.add("nav-active");
  document.querySelectorAll(".view").forEach(view => view.classList.add("hidden"));
  $(button.dataset.view).classList.remove("hidden");
  if (button.dataset.view === "archive-view") await loadArchive();
  if (button.dataset.view === "memory-view") await loadMemory();
}));

async function loadArchive() {
  const response = await fetch("/replications");
  if (!response.ok) return;
  const runs = await response.json();
  $("archive-count").textContent = `${runs.length} RUN${runs.length === 1 ? "" : "S"}`;
  $("archive-list").innerHTML = runs.length ? "" : "<p>No missions yet.</p>";
  runs.forEach(run => {
    const row = document.createElement("a"); row.className = "catalog-row"; row.href = `/?run=${run.id}`;
    const title = document.createElement("b"); title.textContent = run.title || run.source_url;
    const status = document.createElement("em"); status.textContent = run.status.toUpperCase();
    const spend = document.createElement("span"); spend.textContent = `$${run.spent.usd.toFixed(2)} / ${run.spent.job_minutes.toFixed(1)} MIN`;
    row.append(title, status, spend); $("archive-list").appendChild(row);
  });
}

async function loadMemory() {
  const response = await fetch("/memory");
  if (!response.ok) return;
  const lessons = await response.json();
  $("memory-count").textContent = `${lessons.length} LESSON${lessons.length === 1 ? "" : "S"}`;
  $("memory-list").innerHTML = lessons.length ? "" : "<p>No autonomous repairs learned yet.</p>";
  lessons.forEach(lesson => {
    const row = document.createElement("div"); row.className = "catalog-row memory";
    const key = document.createElement("b"); key.textContent = lesson.key;
    const text = document.createElement("span"); text.textContent = lesson.lesson;
    const uses = document.createElement("em"); uses.textContent = `REUSED ${lesson.times_used}x`;
    row.append(key, text, uses); $("memory-list").appendChild(row);
  });
}

async function showExistingRun(run) {
  $("mission").classList.remove("hidden");
  $("mission-id").textContent = `RUN / ${run.id.toUpperCase()}`;
  $("open-report").href = `/replications/${run.id}/report`;
  renderRunState(run);
  $("events").innerHTML = "";
  connect(run.id);
  await refreshEvidence(run.id);
  $("mission").scrollIntoView({behavior: "instant"});
}

$("launch-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.submitter;
  button.disabled = true;
  button.querySelector("span").textContent = "INITIALIZING MISSION…";
  const budget = {max_attempts: Number($("attempts").value), max_job_minutes: Number($("minutes").value), max_usd: Number($("cost").value)};
  try {
    const response = await fetch("/replications", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({source_url: $("source").value, budget})});
    if (!response.ok) throw new Error((await response.json()).detail || "Launch rejected");
    const run = await response.json();
    $("mission").classList.remove("hidden");
    $("mission-id").textContent = `RUN / ${run.id.toUpperCase()}`;
    $("cost-out").value = `$${budget.max_usd.toFixed(2)}`;
    $("spend").textContent = `$0.00 / $${budget.max_usd.toFixed(2)}`;
    $("runtime").textContent = `00:00 / ${String(budget.max_job_minutes).padStart(2,"0")}:00`;
    $("attempt-count").textContent = `0 / ${budget.max_attempts}`;
    $("events").innerHTML = "";
    $("open-report").href = `/replications/${run.id}/report`;
    document.querySelector(".stage").classList.add("active");
    document.querySelector(".mission").scrollIntoView({behavior:"smooth"});
    connect(run.id);
    refreshEvidence(run.id);
    history.replaceState(null, "", `?run=${run.id}`);
  } catch (error) {
    alert(error.message);
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "BEGIN AUTONOMOUS RUN";
  }
});

function connect(id) {
  if (activeSource) activeSource.close();
  if (activePoll) clearInterval(activePoll);
  const source = new EventSource(`/replications/${id}/events`);
  activeSource = source;
  const handle = (event) => {
    const item = JSON.parse(event.data);
    if (item.kind === "heartbeat") return;
    const row = document.createElement("div");
    row.className = "event";
    const stamp = new Date(item.created_at).toISOString().slice(11, 19);
    row.innerHTML = `<time>${stamp}</time><b>${item.stage.toUpperCase()}</b><span></span>`;
    row.querySelector("span").textContent = item.message;
    $("events").prepend(row);
    refreshRunState(id);
  };
  source.addEventListener("status", handle);
  source.addEventListener("agent.decision", handle);
  source.addEventListener("artifact", handle);
  source.onerror = () => refreshRunState(id);
  refreshRunState(id);
  activePoll = setInterval(() => refreshRunState(id), 3000);
}

async function refreshRunState(id) {
  try {
    const response = await fetch(`/replications/${id}`, {cache: "no-store"});
    if (!response.ok) return;
    const run = await response.json();
    renderRunState(run);
    await refreshEvidence(id);
    if (run.status === "reported" || run.status === "failed") {
      clearInterval(activePoll);
      activePoll = undefined;
      activeSource?.close();
      activeSource = undefined;
    }
  } catch (error) {
    console.error("Mission status refresh failed", error);
  }
}

function renderRunState(run) {
  $("mission-status").textContent = run.status.toUpperCase();
  $("spend").textContent = `$${run.spent.usd.toFixed(2)} / $${run.budget.max_usd.toFixed(2)}`;
  $("runtime").textContent = `${run.spent.job_minutes.toFixed(1)} / ${run.budget.max_job_minutes.toFixed(0)} MIN`;
  const activeStage = {queued: -1, reading: 0, planning: 1, coding: 2, running: 3, verifying: 4, reported: 5, failed: 5}[run.status] ?? -1;
  document.querySelectorAll(".stage").forEach((stage, index) => {
    stage.classList.toggle("active", index <= activeStage);
  });
}

$("demo-button").addEventListener("click", async () => {
  const button = $("demo-button");
  button.disabled = true; button.textContent = "RUNNING REAL CALIBRATION…";
  try {
    const response = await fetch("/demo/calibration", {method: "POST"});
    if (!response.ok) throw new Error("Calibration failed");
    const run = await response.json();
    $("mission").classList.remove("hidden");
    $("mission-id").textContent = `CALIBRATION / ${run.id.toUpperCase()}`;
    $("mission-status").textContent = run.status.toUpperCase();
    $("open-report").href = `/replications/${run.id}/report`;
    document.querySelectorAll(".stage").forEach(stage => stage.classList.add("active"));
    $("events").innerHTML = "";
    connect(run.id);
    await refreshEvidence(run.id);
    history.replaceState(null, "", `?run=${run.id}`);
    $("mission").scrollIntoView({behavior: "smooth"});
  } catch (error) { alert(error.message); }
  finally { button.disabled = false; button.textContent = "RUN EVIDENCE-BACKED CALIBRATION"; }
});

async function refreshEvidence(id) {
  const [claimsResponse, verdictsResponse] = await Promise.all([fetch(`/replications/${id}/claims`), fetch(`/replications/${id}/verdicts`)]);
  if (!claimsResponse.ok || !verdictsResponse.ok) return;
  const claims = await claimsResponse.json();
  const verdicts = await verdictsResponse.json();
  if (!claims.length) return;
  const byClaim = Object.fromEntries(verdicts.map(v => [v.claim_id, v]));
  $("claim-rows").innerHTML = "";
  claims.forEach(claim => {
    const verdict = byClaim[claim.id];
    const row = document.createElement("div"); row.className = "claim-row";
    [claim.text, claim.reported_value ?? "—", verdict?.obtained_value ?? "—"].forEach(value => { const cell = document.createElement("span"); cell.textContent = value; row.appendChild(cell); });
    const chip = document.createElement("strong"); chip.className = `verdict ${verdict?.status || ""}`; chip.textContent = verdict?.status || "PENDING"; row.appendChild(chip);
    $("claim-rows").appendChild(row);
  });
  $("evidence").classList.remove("hidden");
}
