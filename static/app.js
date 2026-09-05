const STEPS = ["explore", "plan", "coverage", "generate", "execute", "heal", "report"];
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

async function animateStepper() {
  for (let i = 0; i < STEPS.length - 1; i++) {
    setStepper(i, false);
    await new Promise((r) => setTimeout(r, 900));
  }
}

document.getElementById("run-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("run-btn");
  btn.disabled = true;
  btn.textContent = "Running pipeline...";
  document.getElementById("out-empty").style.display = "none";
  document.getElementById("results").style.display = "none";

  const stepPromise = animateStepper();

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
    await stepPromise;
    setStepper(STEPS.length - 1, true);
    if (!res.ok) throw new Error(data.detail || "Run failed");
    renderReport(data);
    loadHistory();
  } catch (err) {
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

  const gaps = r.coverage_gaps || [];
  document.getElementById("gaps").innerHTML = gaps.length
    ? gaps.map((g) => '<div class="gap-item"><b>' + g.missing_scenario + '</b> (' + g.category + ') &mdash; <span class="risk ' + g.risk + '">' + g.risk + ' risk</span><br><span style="color:var(--muted)">' + g.reason + '</span></div>').join("")
    : '<span style="color:var(--muted);font-size:13px">No coverage gaps remaining.</span>';

  const actions = r.healer_actions || [];
  document.getElementById("healer-actions").innerHTML = actions.length
    ? actions.map((a) => '<span class="pill">' + a + '</span>').join("")
    : '<span style="color:var(--muted);font-size:13px">No healer actions were required.</span>';

  const results = r.results || [];
  document.getElementById("results-table").innerHTML = results
    .map((res) => '<tr><td>' + res.test_id + '</td><td class="status ' + res.status + '">' + res.status + '</td><td>' + res.duration_ms + ' ms</td><td>' + (res.healing_action || res.error || "-") + '</td></tr>')
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
      .map(
        (i) =>
          '<div class="history-item"><span>' + i.application_url + ' <span class="badge ' + i.risk + '">' + i.risk + '</span></span><a href="/report/' + i.run_id + '" target="_blank">View report &rarr;</a></div>'
      )
      .join("");
  } catch (e) {}
}
loadHistory();
