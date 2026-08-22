const $ = (id) => document.getElementById(id);

let activeSource;
let activePoll;
let activeRun;
let activeEvidence = {claims: [], verdicts: []};
let evidenceContractError = "";
const attemptIds = new Set();
const seenEvents = new Set();

const STAGES = ["reading", "planning", "coding", "running", "verifying", "reported"];
const STATE = {
  queued: {
    label: "QUEUED", progress: 2, kicker: "MISSION ACCEPTED", title: "Securing a cloud worker",
    copy: "Your guardrails are locked. Replicator is preparing the paper reader.",
    next: "The Reader will download the paper and identify measurable claims."
  },
  reading: {
    label: "READING PAPER", progress: 15, kicker: "STEP 1 OF 6", title: "Reading the paper",
    copy: "The Reader is extracting figures, tables, and claims that can be measured.",
    next: "The Planner will select feasible claims and design a bounded test."
  },
  planning: {
    label: "PLANNING TEST", progress: 32, kicker: "STEP 2 OF 6", title: "Designing the experiment",
    copy: "The Planner is choosing a defensible method that fits your time and cost ceilings.",
    next: "If a claim is feasible within your guardrails, the Builder will create the experiment."
  },
  coding: {
    label: "BUILDING", progress: 50, kicker: "STEP 3 OF 6", title: "Building the experiment",
    copy: "The Builder is generating runnable code and validating its sources and dependencies.",
    next: "Validated code will be packaged and dispatched to an isolated cloud sandbox."
  },
  running: {
    label: "EXPERIMENT RUNNING", progress: 68, kicker: "STEP 4 OF 6", title: "Running the experiment",
    copy: "The experiment is executing in an isolated Cloud Run job. Live usage is shown below.",
    next: "The Verifier will compare the measured values with the paper's claims."
  },
  verifying: {
    label: "VERIFYING", progress: 86, kicker: "STEP 5 OF 6", title: "Checking every result",
    copy: "The Verifier is tracing measurements to artifacts and assigning evidence-backed verdicts.",
    next: "The Reporter will sign the evidence trail and publish the final verdict."
  },
  reported: {
    label: "ANALYSIS COMPLETE", progress: 100, kicker: "WORKFLOW FINISHED", title: "Analysis complete",
    copy: "The final outcome and evidence ledger are ready below.",
    next: "Review the outcome, inspect each claim, or open the signed evidence report."
  },
  failed_system: {
    label: "SYSTEM STOPPED", progress: 100, kicker: "MISSION STOPPED", title: "The system could not finish",
    copy: "Replicator stopped safely and preserved the available diagnostic evidence.",
    next: "Open the evidence report for the failure reason before trying again."
  }
};

[
  ["attempts", "attempts-out", (v) => v],
  ["minutes", "minutes-out", (v) => `${v} min`],
  ["cost", "cost-out", (v) => `$${Number(v).toFixed(2)}`]
].forEach(([input, output, format]) => $(input).addEventListener("input", (event) => {
  $(output).value = format(event.target.value);
}));

const updateClock = () => { $("clock").textContent = `${new Date().toISOString().slice(11, 19)}Z`; };
updateClock();
setInterval(updateClock, 1000);

document.querySelectorAll("nav button[data-view]").forEach((button) => button.addEventListener("click", async () => {
  document.querySelectorAll("nav button").forEach((item) => item.classList.remove("nav-active"));
  button.classList.add("nav-active");
  document.querySelectorAll(".view").forEach((view) => view.classList.add("hidden"));
  $(button.dataset.view).classList.remove("hidden");
  if (button.dataset.view === "archive-view") await loadArchive();
  if (button.dataset.view === "memory-view") await loadMemory();
}));

async function loadArchive() {
  const response = await fetch("/replications", {cache: "no-store"});
  if (!response.ok) return;
  const runs = await response.json();
  $("archive-count").textContent = `${runs.length} RUN${runs.length === 1 ? "" : "S"}`;
  $("archive-list").replaceChildren();
  if (!runs.length) return $("archive-list").append(emptyMessage("No missions yet."));
  const outcomes = await Promise.all(runs.map(async (run) => {
    if (run.status !== "reported") return {label: STATE[run.status]?.label || run.status, tone: "system"};
    const verdictResponse = await fetch(`/replications/${run.id}/verdicts`, {cache: "no-store"});
    if (!verdictResponse.ok) return {label: "REPORT READY", tone: "system"};
    const verdicts = await verdictResponse.json();
    if (verdicts.length && verdicts.every(isExecutionFailureVerdict)) return {label: "EXECUTION FAILED", tone: "failed"};
    if (!verdicts.length || verdicts.every((verdict) => verdict.status === "NOT_ATTEMPTED")) {
      return run.spent.job_minutes > 0
        ? {label: "NO COMPARABLE EVIDENCE", tone: "skipped"}
        : {label: "NOT RUN", tone: "skipped"};
    }
    const reproduced = verdicts.filter((verdict) => verdict.status === "REPRODUCED").length;
    return {label: `${reproduced} OF ${verdicts.length} REPRODUCED`, tone: reproduced ? "reproduced" : "failed"};
  }));
  runs.forEach((run, index) => {
    const row = document.createElement("a");
    row.className = "catalog-row";
    row.href = `/?run=${run.id}`;
    const identity = document.createElement("div"); identity.className = "run-identity";
    const title = document.createElement("b"); title.textContent = run.title || run.source_url;
    const detail = document.createElement("small");
    detail.textContent = `${new Date(run.created_at).toLocaleDateString([], {day: "numeric", month: "short", year: "numeric"})} · RUN ${run.id.slice(0, 8).toUpperCase()}`;
    identity.append(title, detail);
    const status = document.createElement("em");
    status.textContent = outcomes[index].label;
    status.dataset.tone = outcomes[index].tone;
    const spend = document.createElement("span");
    spend.textContent = `$${run.spent.usd.toFixed(2)} accounted · ${run.spent.job_minutes.toFixed(1)} job min`;
    row.append(identity, status, spend);
    $("archive-list").appendChild(row);
  });
}

async function loadMemory() {
  const response = await fetch("/memory", {cache: "no-store"});
  if (!response.ok) return;
  const lessons = await response.json();
  $("memory-count").textContent = `${lessons.length} LESSON${lessons.length === 1 ? "" : "S"}`;
  $("memory-list").replaceChildren();
  if (!lessons.length) return $("memory-list").append(emptyMessage("No autonomous repairs learned yet."));
  lessons.forEach((lesson) => {
    const row = document.createElement("div"); row.className = "catalog-row memory";
    const identity = document.createElement("div"); identity.className = "memory-identity";
    const key = document.createElement("b"); key.textContent = humanMemoryKey(lesson.key);
    const origin = document.createElement("a"); origin.href = `/?run=${lesson.origin_replication_id}`; origin.textContent = `Origin run ${lesson.origin_replication_id.slice(0, 8).toUpperCase()} ↗`;
    identity.append(key, origin);
    const copy = document.createElement("span"); copy.textContent = lesson.lesson;
    const uses = document.createElement("em"); uses.textContent = lesson.times_used ? `REUSED ${lesson.times_used}×` : "NOT REUSED YET";
    uses.dataset.tone = lesson.times_used ? "reproduced" : "skipped";
    row.append(identity, copy, uses);
    $("memory-list").appendChild(row);
  });
}

function humanMemoryKey(key) {
  const signature = key.split(":").slice(1).join(":");
  return signature.replace(/^unclassified-/, "Runtime failure · ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function emptyMessage(text) {
  const element = document.createElement("p");
  element.textContent = text;
  return element;
}

async function showExistingRun(run) {
  activeRun = run;
  attemptIds.clear();
  seenEvents.clear();
  $("mission").classList.remove("hidden");
  $("events").replaceChildren(emptyMessage("Loading the mission timeline…"));
  $("events").firstElementChild.className = "empty";
  $("open-report").href = `/replications/${run.id}/report`;
  renderRunState(run);
  await refreshEvidence(run.id);
  connect(run.id);
  $("mission").scrollIntoView({behavior: "smooth", block: "start"});
}

$("launch-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.submitter;
  const label = button.querySelector("b");
  button.disabled = true;
  label.textContent = "Starting mission…";
  const budget = {
    max_attempts: Number($("attempts").value),
    max_job_minutes: Number($("minutes").value),
    max_usd: Number($("cost").value)
  };
  try {
    const response = await fetch("/replications", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({source_url: $("source").value, budget})
    });
    if (!response.ok) throw new Error((await response.json()).detail || "The mission could not start");
    const run = await response.json();
    history.replaceState(null, "", `?run=${run.id}`);
    await showExistingRun(run);
  } catch (error) {
    window.alert(error.message);
  } finally {
    button.disabled = false;
    label.textContent = "Start autonomous replication";
  }
});

function connect(id) {
  activeSource?.close();
  if (activePoll) clearInterval(activePoll);
  const source = new EventSource(`/replications/${id}/events`);
  activeSource = source;
  const handle = (event) => {
    const item = JSON.parse(event.data);
    if (item.kind === "heartbeat") return;
    if (item.detail?.attempt_id) attemptIds.add(item.detail.attempt_id);
    const key = event.lastEventId || `${item.created_at}-${item.stage}-${item.message}`;
    if (!seenEvents.has(key)) {
      seenEvents.add(key);
      appendEvent(item);
    }
    refreshRunState(id);
  };
  ["status", "agent.decision", "artifact"].forEach((name) => source.addEventListener(name, handle));
  source.onerror = () => refreshRunState(id);
  refreshRunState(id);
  activePoll = setInterval(() => refreshRunState(id), 3000);
}

function appendEvent(item) {
  if ($("events").querySelector(".empty")) $("events").replaceChildren();
  const row = document.createElement("div"); row.className = "event";
  const marker = document.createElement("i");
  const copy = document.createElement("div");
  const head = document.createElement("span");
  const agent = document.createElement("b"); agent.textContent = humanStage(item.stage);
  const time = document.createElement("time"); time.textContent = new Date(item.created_at).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"});
  const message = document.createElement("p"); message.textContent = item.message;
  head.append(agent, time); copy.append(head, message); row.append(marker, copy);
  $("events").prepend(row);
}

async function refreshRunState(id) {
  try {
    const response = await fetch(`/replications/${id}`, {cache: "no-store"});
    if (!response.ok) return;
    activeRun = await response.json();
    await refreshEvidence(id);
    renderRunState(activeRun);
    if (["reported", "failed_system"].includes(activeRun.status)) {
      clearInterval(activePoll); activePoll = undefined;
      activeSource?.close(); activeSource = undefined;
    }
  } catch (error) {
    console.error("Mission status refresh failed", error);
  }
}

function renderRunState(run) {
  const state = STATE[run.status] || STATE.queued;
  const noAttempt = !evidenceContractError && isNoAttempt(run, activeEvidence.verdicts);
  const noComparableEvidence = isNoComparableEvidence(run, activeEvidence.verdicts);
  const executionFailure = isExecutionFailure(activeEvidence.verdicts);
  $("mission-paper").textContent = run.title || "Preparing paper…";
  $("mission-id").textContent = `RUN ${run.id.slice(0, 8).toUpperCase()} · ${new URL(run.source_url).hostname}`;
  $("mission-status").textContent = state.label;
  $("mission-status").className = `status-pill ${["reported", "failed_system"].includes(run.status) ? "terminal" : ""}`;
  $("state-kicker").textContent = state.kicker;
  $("state-title").textContent = evidenceContractError ? "Analysis complete — evidence rejected" : executionFailure ? "Execution failed before measurement" : noAttempt ? "Analysis complete — experiment skipped" : noComparableEvidence ? "Analysis complete — no comparable claims" : state.title;
  $("state-copy").textContent = evidenceContractError
    ? "The job ran, but its measurements violated their typed claim contract. Replicator invalidated the result instead of blaming the paper."
    : executionFailure
    ? "Replicator built the experiment and exhausted every repair attempt, but no runnable job produced a measurement. No scientific verdict was assigned."
    : noAttempt
    ? "Replicator extracted the claims, then stopped honestly because it could not dispatch a defensible experiment within the mission constraints."
    : noComparableEvidence
    ? "The cloud experiment completed and produced an artifact, but none of its measurements matched the paper claims' required datasets and protocols."
    : state.copy;
  $("next-action").textContent = evidenceContractError
    ? "Do not use these verdicts. Start a new run; new experiments now receive stricter claim-to-measurement bindings."
    : executionFailure
    ? "Inspect the last error and evidence artifacts below. This is a system result—not evidence against the paper."
    : noAttempt
    ? "Review the reason below. Increase the guardrails or choose a paper with a smaller reproducible experiment before retrying."
    : noComparableEvidence
    ? "The run itself worked. Choose a paper with accessible official datasets, or inspect the ledger to see why each claim was excluded."
    : state.next;
  $("progress-percent").textContent = `${state.progress}%`;
  $("progress-fill").style.width = `${state.progress}%`;
  $("elapsed").textContent = `${formatElapsed(run)} elapsed`;
  $("spend").textContent = run.spent.usd > 0
    ? `$${run.spent.usd.toFixed(2)} used · $${run.budget.max_usd.toFixed(2)} cap`
    : `No spend yet · $${run.budget.max_usd.toFixed(2)} cap`;
  $("runtime").textContent = run.spent.job_minutes > 0
    ? `${run.spent.job_minutes.toFixed(1)} min used · ${run.budget.max_job_minutes.toFixed(0)} min cap`
    : `Job not started · ${run.budget.max_job_minutes.toFixed(0)} min cap`;
  $("attempt-count").textContent = attemptIds.size
    ? `${attemptIds.size} used · ${run.budget.max_attempts} max`
    : `No attempts yet · ${run.budget.max_attempts} max`;
  $("state-icon").className = `state-icon ${run.status === "failed_system" || noAttempt ? "warning" : run.status === "reported" ? "complete" : ""}`;
  renderStages(run.status, noAttempt, executionFailure);
  if (["reported", "failed_system"].includes(run.status)) renderOutcome(run, activeEvidence.verdicts);
}

function renderStages(status, noAttempt, executionFailure) {
  const current = STAGES.indexOf(status);
  document.querySelectorAll(".stage").forEach((stage, index) => {
    let mode = index < current ? "complete" : index === current ? "current" : "waiting";
    if (status === "reported") mode = "complete";
    if (noAttempt && [2, 3, 4].includes(index)) mode = "skipped";
    if (executionFailure && index === 2) mode = "complete";
    if (executionFailure && index === 3) mode = "failed";
    if (executionFailure && index === 4) mode = "skipped";
    stage.className = `stage ${mode}`;
    stage.querySelector("em").textContent = ({complete: "Done", current: "In progress", waiting: "Waiting", skipped: "Skipped", failed: "Failed"})[mode];
  });
}

async function refreshEvidence(id) {
  const [claimsResponse, verdictsResponse] = await Promise.all([
    fetch(`/replications/${id}/claims`, {cache: "no-store"}),
    fetch(`/replications/${id}/verdicts`, {cache: "no-store"})
  ]);
  if (!claimsResponse.ok || !verdictsResponse.ok) return;
  const claims = await claimsResponse.json();
  const verdicts = await verdictsResponse.json();
  evidenceContractError = findEvidenceContractError(claims, verdicts);
  activeEvidence = {claims, verdicts};
  verdicts.forEach((verdict) => { if (verdict.attempt_id) attemptIds.add(verdict.attempt_id); });
  if (!claims.length) return;
  const byClaim = Object.fromEntries(verdicts.map((verdict) => [verdict.claim_id, verdict]));
  $("claim-rows").replaceChildren();
  claims.forEach((claim) => {
    const verdict = byClaim[claim.id];
    const row = document.createElement("div"); row.className = "claim-row";
    const claimCell = document.createElement("span"); claimCell.className = "claim-copy"; claimCell.textContent = claim.text;
    const reported = document.createElement("span"); reported.textContent = formatValue(claim.reported_value, claim.unit);
    const obtained = document.createElement("span"); obtained.textContent = formatValue(verdict?.obtained_value, claim.unit);
    const chip = document.createElement("strong");
    const effectiveStatus = verdict ? effectiveVerdictStatus(verdict) : "PENDING";
    chip.className = `verdict ${effectiveStatus}`;
    chip.textContent = humanVerdict(effectiveStatus);
    const detail = document.createElement("div"); detail.className = "claim-detail";
    const reasoning = document.createElement("p"); reasoning.textContent = verdict?.reasoning || "No completed attempt produced evidence.";
    const artifacts = document.createElement("div"); artifacts.className = "claim-artifacts";
    (verdict?.evidence_links || []).forEach((uri, index) => {
      const link = document.createElement("a");
      link.href = `/replications/${id}/artifact?uri=${encodeURIComponent(uri)}`;
      link.target = "_blank";
      link.textContent = `Evidence ${index + 1} ↗`;
      artifacts.appendChild(link);
    });
    detail.append(reasoning, artifacts);
    row.append(claimCell, reported, obtained, chip, detail);
    $("claim-rows").appendChild(row);
  });
  const attempted = verdicts.filter((verdict) => effectiveVerdictStatus(verdict) !== "NOT_ATTEMPTED").length;
  $("ledger-summary").textContent = attempted ? `${attempted} OF ${claims.length} CLAIMS TESTED` : `${claims.length} CLAIMS FOUND · NONE TESTED`;
  $("evidence").classList.remove("hidden");
}

function renderOutcome(run, verdicts) {
  const reproduced = verdicts.filter((v) => effectiveVerdictStatus(v) === "REPRODUCED").length;
  const failed = verdicts.filter((v) => ["FAILED", "PARTIAL"].includes(effectiveVerdictStatus(v))).length;
  const skipped = verdicts.filter((v) => effectiveVerdictStatus(v) === "NOT_ATTEMPTED").length;
  const noAttempt = isNoAttempt(run, verdicts);
  const noComparableEvidence = isNoComparableEvidence(run, verdicts);
  const executionFailure = isExecutionFailure(verdicts);
  $("stat-reproduced").textContent = reproduced;
  $("stat-failed").textContent = failed;
  $("stat-skipped").textContent = skipped;
  $("outcome").classList.toggle("warning", noAttempt || noComparableEvidence || run.status === "failed_system");
  if (evidenceContractError) {
    $("outcome-mark").textContent = "!";
    $("outcome-kicker").textContent = "EVIDENCE REJECTED";
    $("outcome-title").textContent = "The measurements could not be trusted.";
    $("outcome-summary").textContent = `${evidenceContractError} Replicator has invalidated the scientific verdicts; this is not evidence against the paper.`;
  } else if (run.status === "failed_system") {
    $("outcome-mark").textContent = "!";
    $("outcome-kicker").textContent = "STOPPED SAFELY";
    $("outcome-title").textContent = "The system could not finish this mission.";
    $("outcome-summary").textContent = run.summary_verdict || "The available diagnostic evidence was preserved. No result has been invented.";
  } else if (executionFailure) {
    const reason = verdicts.find((v) => v.reasoning)?.reasoning;
    $("outcome-mark").textContent = "!";
    $("outcome-kicker").textContent = "SYSTEM RESULT";
    $("outcome-title").textContent = "Execution failed before measurement.";
    $("outcome-summary").textContent = `${reason || "Every autonomous repair attempt failed."} This is not evidence against the paper.`;
  } else if (noAttempt) {
    const reason = verdicts.find((v) => v.reasoning)?.reasoning;
    $("outcome-mark").textContent = "↷";
    $("outcome-kicker").textContent = "COMPLETED SAFELY";
    $("outcome-title").textContent = "The experiment was not run.";
    $("outcome-summary").textContent = `${reason || run.summary_verdict || "No defensible experiment could be dispatched within the mission constraints."} No reproduction verdict was claimed.`;
  } else if (noComparableEvidence) {
    $("outcome-mark").textContent = "?";
    $("outcome-kicker").textContent = "RUN COMPLETED SAFELY";
    $("outcome-title").textContent = "The experiment ran; no paper claims were comparable.";
    $("outcome-summary").textContent = "The cloud job produced evidence, but the Verifier rejected every measurement as unavailable or protocol-mismatched. This is not evidence against the paper.";
  } else {
    $("outcome-mark").textContent = reproduced ? "✓" : "≠";
    $("outcome-kicker").textContent = "MISSION COMPLETE";
    $("outcome-title").textContent = reproduced
      ? `Evidence supports ${reproduced} of ${verdicts.length} tested claims.`
      : "The tested claims did not reproduce.";
    $("outcome-summary").textContent = run.summary_verdict || "Every verdict is linked to measured evidence in the ledger below.";
  }
  $("outcome").classList.remove("hidden");
}

function isNoAttempt(run, verdicts) {
  return run.status === "reported"
    && run.spent.job_minutes === 0
    && attemptIds.size === 0
    && verdicts.length > 0
    && verdicts.every((verdict) => effectiveVerdictStatus(verdict) === "NOT_ATTEMPTED");
}

function isNoComparableEvidence(run, verdicts) {
  return run.status === "reported"
    && (run.spent.job_minutes > 0 || attemptIds.size > 0)
    && verdicts.length > 0
    && verdicts.every((verdict) => effectiveVerdictStatus(verdict) === "NOT_ATTEMPTED");
}

function isExecutionFailureVerdict(verdict) {
  return verdict.obtained_value === null && /(?:all \d+ attempts failed|execution failed before measurement)/i.test(verdict.reasoning || "");
}

function isExecutionFailure(verdicts) {
  return verdicts.length > 0 && verdicts.every(isExecutionFailureVerdict);
}

function effectiveVerdictStatus(verdict) {
  const missingFigure = /did not produce the required claim figure|no faithful reproduced figure/i.test(verdict.reasoning || "");
  return evidenceContractError || isExecutionFailureVerdict(verdict) || missingFigure ? "NOT_ATTEMPTED" : verdict.status;
}

function findEvidenceContractError(claims, verdicts) {
  const byClaim = Object.fromEntries(claims.map((claim) => [claim.id, claim]));
  for (const verdict of verdicts) {
    const claim = byClaim[verdict.claim_id];
    if (!claim || verdict.obtained_value === null || verdict.obtained_value === undefined) continue;
    const label = `${claim.metric_name || ""} ${claim.text}`.toLowerCase();
    const bounded = ["accuracy", "precision", "recall", "f1", "auc", "proportion"].some((word) => label.includes(word));
    if (bounded && claim.unit !== "%" && claim.reported_value >= 0 && claim.reported_value <= 1 && (verdict.obtained_value < 0 || verdict.obtained_value > 1)) {
      return `A bounded metric received ${verdict.obtained_value}, outside its valid 0–1 range. This indicates values were attached to the wrong claims.`;
    }
  }
  return "";
}

function formatElapsed(run) {
  const start = new Date(run.created_at).getTime();
  const terminal = ["reported", "failed_system"].includes(run.status);
  const end = terminal ? new Date(run.updated_at).getTime() : Date.now();
  const seconds = Math.max(0, Math.floor((end - start) / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function formatValue(value, unit) {
  return value === null || value === undefined ? "—" : `${value}${unit ? ` ${unit}` : ""}`;
}

function humanStage(stage) {
  return ({api: "System", reader: "Reader", planner: "Planner", coder: "Builder", executor: "Runner", verifier: "Verifier", reporter: "Reporter"})[stage] || stage;
}

function humanVerdict(status) {
  return ({REPRODUCED: "Reproduced", PARTIAL: "Partial", FAILED: "Not reproduced", NOT_ATTEMPTED: "Not attempted"})[status] || "Pending";
}

$("copy-link").addEventListener("click", async () => {
  const button = $("copy-link");
  try {
    await navigator.clipboard.writeText(location.href);
    button.textContent = "Link copied";
  } catch {
    button.textContent = "Copy unavailable";
  }
  setTimeout(() => { button.textContent = "Copy share link"; }, 1800);
});

const sharedRunId = new URLSearchParams(location.search).get("run");
if (sharedRunId) {
  fetch(`/replications/${sharedRunId}`, {cache: "no-store"})
    .then((response) => response.ok ? response.json() : Promise.reject(new Error("Run not found")))
    .then(showExistingRun)
    .catch((error) => console.error(error));
}
