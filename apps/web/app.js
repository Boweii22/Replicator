const $ = (id) => document.getElementById(id);
const fields = [
  ["attempts", "attempts-out", (v) => v],
  ["minutes", "minutes-out", (v) => `${v} min`],
  ["cost", "cost-out", (v) => `$${Number(v).toFixed(2)}`],
];
fields.forEach(([input, output, format]) => $(input).addEventListener("input", e => $(output).value = format(e.target.value)));
setInterval(() => $("clock").textContent = new Date().toISOString().slice(11, 19) + "Z", 1000);

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
    document.querySelector(".stage").classList.add("active");
    document.querySelector(".mission").scrollIntoView({behavior:"smooth"});
    connect(run.id);
  } catch (error) {
    alert(error.message);
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "BEGIN AUTONOMOUS RUN";
  }
});

function connect(id) {
  const source = new EventSource(`/replications/${id}/events`);
  const handle = (event) => {
    const item = JSON.parse(event.data);
    if (item.kind === "heartbeat") return;
    const row = document.createElement("div");
    row.className = "event";
    const stamp = new Date(item.created_at).toISOString().slice(11, 19);
    row.innerHTML = `<time>${stamp}</time><b>${item.stage.toUpperCase()}</b><span></span>`;
    row.querySelector("span").textContent = item.message;
    $("events").prepend(row);
    $("mission-status").textContent = item.stage === "api" ? "QUEUED" : "READING";
  };
  source.addEventListener("status", handle);
  source.addEventListener("agent.decision", handle);
  source.onerror = () => $("mission-status").textContent = "RECONNECTING";
}
