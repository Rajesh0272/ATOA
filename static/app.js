const STEPS = ["explore", "plan", "coverage", "generate", "execute", "heal", "report"];
const STEP_LABELS = ["Exploring page", "Planning scenarios", "Evaluating coverage", "Generating tests", "Executing tests", "Healing failures", "Building report"];
let currentReport = null;

const fileDrop = document.getElementById("file-drop");
const prdInput = document.getElementById("prd_file");
fileDrop.addEventListener("click", () => prdInput.click());
prdInput.addEventListener("change", () => {
  if (prdInput.files.length) {
    fileDrop.textContent = "Attached: " + prdInput.files[0].name;
    fileDrop.classList.add("has-file");
  } else {
    fileDrop.textContent = "Click to attach a PRD (.txt/.md)";
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
        text.textContent = "Done in " + ((Date.now() - startedAt) / 1000).toFixed(1) + "s";
        setTimeout(() => {
          bar.style.width = "0%";
          text.textContent = "";
        }, 1500);
      } else {
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
  }
});

document.getElementById("run-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("run-btn");
  btn.disabled = true;
  btn.textContent = "Running pipeline...";
  document.getElementById("out-empty").style.display = "none";
  document.getElementById("results").style.display = "none";

  const progress = startProgress();

  const form = new FormData();
  form.append("url", document.getElementById("url").value);
  form.append("description", document.getElementById("description").value);
  form.append("username", document.getElementById("username").value);
  form.append("password", document.getElementById("password").value);
  form.append("parallel", document.getElementById("parallel").checked);
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
    document.getElementById("out-empty").style.display = "block";
    document.getElementById("out-empty").textContent = "Error: " + err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Run AIVAR";
  }
});

function metric(label, value) {
  return '<div class="metric"><div class="num">' + value + '</div><div class="lbl">' + label + '</div></div>';
}

function executionSourceHtml(r) {
  const executorNote = r.cache_hit && !r.website_changed
    ? (r.tests_reexecuted > 0
        ? 'Partial (' + r.tests_reexecuted + ' re-executed, ' + r.tests_reused + ' reused from cache)'
        : 'No (all ' + r.tests_reused + ' cached results reused)')
    : 'Yes (full run, ' + r.total_executed + ' test(s))';
  const rows = [
    ['Cache Hit', r.cache_hit ? 'Yes' : 'No'],
    ['Website Changed', r.website_changed ? 'Yes' : 'No'],
    ['Planner Executed', r.planner_executed ? 'Yes' : 'No'],
    ['Generator Executed', r.generator_executed ? 'Yes' : 'No'],
    ['Executor Executed', executorNote],
    ['LLM Calls Saved', r.llm_calls_saved > 0 ? 'Yes (' + r.llm_calls_saved + ')' : 'No'],
    ['Estimated Credit Saving', r.estimated_credit_saving || '0%'],
  ];
  return rows.map((row) =>
    '<div class="gap-item"><b>' + row[0] + ':</b> ' + row[1] + '</div>'
  ).join("");
}

function renderReport(r) {
  currentReport = r;
  document.getElementById("results").style.display = "block";
  document.getElementById("risk-badge").innerHTML = '<span class="badge ' + r.risk + '">' + r.risk + ' RISK</span>';
  document.getElementById("summary-text").textContent = r.summary;
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

  document.getElementById("execution-source").innerHTML = executionSourceHtml(r);

  const gaps = r.coverage_gaps || [];
  document.getElementById("gaps").innerHTML = gaps.length
    ? gaps.map((g) => '<div class="gap-item"><b>' + g.missing_scenario + '</b> (' + g.category + ') &mdash; <span class="risk ' + g.risk + '">' + g.risk + ' risk</span><br><span style="color:var(--muted)">' + g.reason + '</span></div>').join("")
    : '<span style="color:var(--muted);font-size:13px">No coverage gaps remaining.</span>';

  const actions = r.healer_actions || [];
  document.getElementById("healer-actions").innerHTML = actions.length
    ? actions.map((a) => '<span class="pill">' + a + '</span>').join("")
    : '<span style="color:var(--muted);font-size:13px">No healer actions were required.</span>';

  const results = r.results || [];
  const scenarioNames = {};
  (r.scenarios || []).forEach((s) => { scenarioNames[s.id] = s.name; });
  document.getElementById("results-table").innerHTML = results
    .map((res) => {
      const scenarioId = res.test_id.includes("TC-") ? res.test_id.split("TC-")[1] : res.test_id;
      const caseName = scenarioNames[scenarioId] || "-";
      return '<tr><td>' + res.test_id + '</td><td>' + caseName + '</td><td class="status ' + res.status + '">' + res.status + '</td><td>' + res.duration_ms + ' ms</td><td>' + (res.healing_action || res.error || "-") + '</td></tr>';
    })
    .join("");

  const prd = r.prd_gap;
  const prdCard = document.getElementById("prd-card");
  if (prd && prd.requirements_considered) {
    prdCard.style.display = "block";
    document.getElementById("prd-summary").textContent =
      prd.requirements_covered + "/" + prd.requirements_considered + " PRD requirements matched to a test scenario.";
    document.getElementById("prd-items").innerHTML = prd.items
      .map((i) => '<div class="gap-item">' + (i.covered ? "\u2705" : "\u274c") + ' ' + i.requirement + '</div>')
      .join("");
  } else {
    prdCard.style.display = "none";
  }
}

document.getElementById("pdf-btn").addEventListener("click", () => {
  if (currentReport) window.open("/report/" + currentReport.run_id + "/pdf", "_blank");
});
document.getElementById("json-btn").addEventListener("click", () => {
  if (currentReport) window.open("/report/" + currentReport.run_id + "/json", "_blank");
});
// QR sharing is temporarily disabled server-side; keep the button wired so
// re-enabling app/main.py's /report/{run_id}/qr route lights this back up
// without any frontend changes.
document.getElementById("qr-btn").addEventListener("click", async () => {
  if (!currentReport) return;
  const probe = await fetch("/report/" + currentReport.run_id + "/qr");
  if (!probe.ok) {
    alert("QR sharing is temporarily disabled.");
    return;
  }
  document.getElementById("qr-img").src = "/report/" + currentReport.run_id + "/qr?t=" + Date.now();
  document.getElementById("qr-modal").classList.add("open");
});

async function loadHistory() {
  try {
    const res = await fetch("/reports");
    const items = await res.json();
    const el = document.getElementById("history");
    if (!items.length) {
      el.innerHTML = '<span style="color:var(--muted);font-size:13px">No runs yet.</span>';
      return;
    }
    el.innerHTML = items
      .slice(0, 8)
      .map((i) => {
        const ts = i.created_at ? new Date(i.created_at * 1000).toLocaleString() : "";
        return (
          '<div class="history-item"><span>' + i.application_url + ' <span class="badge ' + i.risk + '">' + i.risk + '</span>' +
          (ts ? '<br><span style="color:var(--muted);font-size:11px">' + ts + '</span>' : '') +
          '</span><a href="/report/' + i.run_id + '" target="_blank">View report &rarr;</a></div>'
        );
      })
      .join("");
  } catch (e) {}
}
loadHistory();
