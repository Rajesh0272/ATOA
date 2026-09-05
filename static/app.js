const STEPS = ["explore", "plan", "coverage", "generate", "execute", "heal", "report"];
const STEP_LABELS = ["Exploring page", "Planning scenarios", "Evaluating coverage", "Generating tests", "Executing tests", "Healing failures", "Building report"];
let currentReport = null;

const fileDrop = document.getElementById("file-drop");
const prdInput = document.getElementById("prd_file");
fileDrop.addEventListener("click", () => prdInput.click());
prdInput.addEventListener("change", () => {
  if (prdInput.files.length) {
    fileDrop.querySelector("span").textContent = "Attached: " + prdInput.files[0].name;
    fileDrop.classList.add("has-file");
  } else {
    fileDrop.querySelector("span").textContent = "Attach a PRD (.txt/.md)";
    fileDrop.classList.remove("has-file");
  }
});

function setStepper(activeIndex, done) {
  document.querySelectorAll(".step").forEach((el, i) => {
    el.classList.remove("active", "done");
    if (done) el.classList.add("done");
    else if (i === activeIndex) el.classList.add("active");
    else if (i < activeIndex) el.classList.add("done");
  });
}

function setRunState(state) {
  const el = document.getElementById("run-state");
  if (!el) return;
  el.textContent = state;
  el.className = "run-state run-state-" + state.toLowerCase();
}

function setHidden(el, hidden) {
  el.classList.toggle("is-hidden", hidden);
}

// Drives both the step labels and a progress bar while the pipeline is
// running. There is no server-sent progress stream, so this uses an
// asymptotic fill (fast at first, slowing as it approaches ~92%) combined
// with an elapsed-time readout, since healing/escalated scenarios can take
// much longer than the earlier pipeline stages and would otherwise look
// stuck on a static "Heal" label with no feedback.
function startProgress() {
  const bar = document.getElementById("progress-bar");
  const text = document.getElementById("progress-text");
  const startedAt = Date.now();
  let stepIndex = 0;
  bar.style.width = "0%";
  bar.classList.remove("indeterminate");
  setRunState("Running");

  const timer = setInterval(() => {
    const elapsedSec = (Date.now() - startedAt) / 1000;
    stepIndex = Math.min(STEPS.length - 2, Math.floor(elapsedSec / 2.5));
    setStepper(stepIndex, false);

    const pct = Math.min(92, 100 * (1 - Math.exp(-elapsedSec / 9)));
    bar.style.width = pct.toFixed(0) + "%";

    let label = STEP_LABELS[stepIndex];
    if (stepIndex === STEPS.indexOf("heal") && elapsedSec > 8) {
      label += " — this can take longer for escalated/failed tests";
    }
    text.textContent = label + " (" + elapsedSec.toFixed(0) + "s elapsed)";
  }, 400);

  return {
    stop(success) {
      clearInterval(timer);
      bar.style.width = success ? "100%" : bar.style.width;
      setStepper(STEPS.length - 1, !!success);
      if (success) {
        setRunState("Complete");
        text.textContent = "Done in " + ((Date.now() - startedAt) / 1000).toFixed(1) + "s";
        setTimeout(() => {
          bar.style.width = "0%";
          text.textContent = "";
          setRunState("Idle");
        }, 1500);
      } else {
        setRunState("Stopped");
        text.textContent = "Stopped after " + ((Date.now() - startedAt) / 1000).toFixed(0) + "s";
      }
    },
  };
}

document.getElementById("clear-cache-btn").addEventListener("click", async () => {
  const statusEl = document.getElementById("cache-status");
  const btn = document.getElementById("clear-cache-btn");
  const url = document.getElementById("url").value.trim();
  btn.disabled = true;
  btn.classList.add("is-loading");
  statusEl.textContent = "Clearing cache...";
  try {
    const form = new FormData();
    if (url) form.append("url", url);
    const res = await fetch("/cache/clear", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to clear cache");
    statusEl.textContent = data.count
      ? "Cache cleared" + (url ? " for this URL." : ` for ${data.count} URL(s).`)
      : "No cache found" + (url ? " for this URL." : ".");
  } catch (err) {
    statusEl.textContent = "Error: " + err.message;
  } finally {
    btn.disabled = false;
    btn.classList.remove("is-loading");
  }
});

document.getElementById("run-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("run-btn");
  btn.disabled = true;
  btn.classList.add("is-loading");
  btn.querySelector("span").textContent = "Running pipeline...";
  setHidden(document.getElementById("out-empty"), true);
  setHidden(document.getElementById("results"), true);

  const progress = startProgress();

  const form = new FormData();
  form.append("url", document.getElementById("url").value);
  form.append("description", document.getElementById("description").value);
  form.append("username", document.getElementById("username").value);
  form.append("password", document.getElementById("password").value);
  if (prdInput.files.length) form.append("prd_file", prdInput.files[0]);

  try {
    const res = await fetch("/run", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Run failed");
    progress.stop(true);
    renderReport(data);
    loadHistory();
  } catch (err) {
    progress.stop(false);
    setHidden(document.getElementById("out-empty"), false);
    document.getElementById("out-empty").innerHTML =
      '<div class="radar-glyph radar-glyph-error" aria-hidden="true"><span></span><span></span><span></span></div><h2>Run stopped.</h2><p>' + escapeHtml(err.message) + '</p>';
  } finally {
    btn.disabled = false;
    btn.classList.remove("is-loading");
    btn.querySelector("span").textContent = "Run ATOA";
    if (window.lucide) window.lucide.createIcons();
  }
});

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function metric(label, value) {
  const key = label.toLowerCase();
  return '<div class="metric metric-' + key + '"><div class="num">' + escapeHtml(value) + '</div><div class="lbl">' + escapeHtml(label) + '</div></div>';
}

function renderReport(r) {
  currentReport = r;
  setHidden(document.getElementById("results"), false);
  document.getElementById("risk-badge").innerHTML = '<span class="badge ' + r.risk + '">' + r.risk + ' RISK</span>';
  document.getElementById("metrics").innerHTML = [
    metric("Planned", r.total_planned),
    metric("Generated", r.total_generated),
    metric("Executed", r.total_executed),
    metric("Passed", r.passed),
    metric("Healed", r.healed),
    metric("Failed", r.failed),
    metric("Escalated", r.escalated),
    metric("Blocked", r.blocked),
  ].join("");

  const gaps = r.coverage_gaps || [];
  document.getElementById("gaps").innerHTML = gaps.length
    ? gaps.map((g) => '<div class="gap-item"><b>' + escapeHtml(g.missing_scenario) + '</b> (' + escapeHtml(g.category) + ') - <span class="risk ' + g.risk + '">' + escapeHtml(g.risk) + ' risk</span><br><span class="muted-copy">' + escapeHtml(g.reason) + '</span></div>').join("")
    : '<span class="empty-copy">No coverage gaps remaining.</span>';

  const actions = r.healer_actions || [];
  document.getElementById("healer-actions").innerHTML = actions.length
    ? actions.map((a) => '<span class="pill">' + escapeHtml(a) + '</span>').join("")
    : '<span class="empty-copy">No healer actions were required.</span>';

  const results = r.results || [];
  const scenarioNames = {};
  (r.scenarios || []).forEach((s) => { scenarioNames[s.id] = s.name; });
  const SCREENSHOT_STATUSES = new Set(["FAILED", "HEALED", "ESCALATED"]);
  document.getElementById("results-table").innerHTML = results
    .map((res) => {
      const scenarioId = res.test_id.includes("TC-") ? res.test_id.split("TC-")[1] : res.test_id;
      const caseName = scenarioNames[scenarioId] || "-";
      const shotUrl = "/report/" + r.run_id + "/screenshot/" + res.test_id;
      const shotCell = SCREENSHOT_STATUSES.has(res.status) && res.screenshot_path
        ? '<a href="' + shotUrl + '" target="_blank"><img class="thumb" src="' + shotUrl + '" alt="screenshot" /></a>'
        : '<span class="empty-copy">-</span>';
      return '<tr><td>' + escapeHtml(res.test_id) + '</td><td>' + escapeHtml(caseName) + '</td><td><span class="status ' + res.status + '">' + escapeHtml(res.status) + '</span></td><td>' + escapeHtml(res.duration_ms) + ' ms</td><td>' + escapeHtml(res.healing_action || res.error || "-") + '</td><td>' + shotCell + '</td></tr>';
    })
    .join("");

  const prd = r.prd_gap;
  const prdCard = document.getElementById("prd-card");
  if (prd && prd.requirements_considered) {
    setHidden(prdCard, false);
    document.getElementById("prd-summary").textContent =
      prd.requirements_covered + "/" + prd.requirements_considered + " PRD requirements matched to a test scenario.";
    document.getElementById("prd-items").innerHTML = prd.items
      .map((i) => '<div class="gap-item"><span class="status ' + (i.covered ? "PASSED" : "FAILED") + '">' + (i.covered ? "COVERED" : "GAP") + '</span> ' + escapeHtml(i.requirement) + '</div>')
      .join("");
  } else {
    setHidden(prdCard, true);
  }
  if (window.lucide) window.lucide.createIcons();
}

document.getElementById("pdf-btn").addEventListener("click", () => {
  if (currentReport) window.open("/report/" + currentReport.run_id + "/pdf", "_blank");
});
document.getElementById("json-btn").addEventListener("click", () => {
  if (currentReport) window.open("/report/" + currentReport.run_id + "/json", "_blank");
});

async function loadHistory() {
  try {
    const res = await fetch("/reports");
    const items = await res.json();
    const el = document.getElementById("history");
    if (!items.length) {
      el.innerHTML = '<span class="empty-copy">No runs yet.</span>';
      return;
    }
    el.innerHTML = items
      .slice(0, 8)
      .map((i) => {
        const ts = i.created_at ? new Date(i.created_at * 1000).toLocaleString() : "";
        return (
          '<div class="history-item"><span><strong>' + escapeHtml(i.application_url) + '</strong> <span class="badge ' + i.risk + '">' + escapeHtml(i.risk) + '</span>' +
          (ts ? '<br><span class="history-time">' + escapeHtml(ts) + '</span>' : '') +
          '</span><a href="/report/' + escapeHtml(i.run_id) + '" target="_blank">View report</a></div>'
        );
      })
      .join("");
    if (window.lucide) window.lucide.createIcons();
  } catch (e) {}
}
loadHistory();
if (window.lucide) window.lucide.createIcons();
