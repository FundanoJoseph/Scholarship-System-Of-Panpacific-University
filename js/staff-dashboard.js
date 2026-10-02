let currentUser = null;

const STATUS_COLORS = {
  Submitted: "#1b4557",
  "Under Evaluation": "#f4b183",
  Approved: "#2e8b46",
  Rejected: "#c0392b",
};

async function showOverview() {
  const applications = await getActiveApplications();
  const count = {};
  STATUSES.forEach((status) => {
    count[status] = applications.filter((app) => app.status === status).length;
  });
  const decided = count["Approved"] + count["Rejected"];
  el("termText").textContent = (await getCurrentTerm()).label;
  el("statTotal").textContent = applications.length;
  el("statTotalNote").textContent = count["Submitted"] + " waiting for evaluation";
  el("statEvaluating").textContent = count["Under Evaluation"];
  el("statApproved").textContent = count["Approved"];
  el("statApprovedNote").textContent = decided
    ? percent(count["Approved"], decided) + " of approved applications"
    : "No decisions yet";
  el("statRejected").textContent = count["Rejected"];
  el("statRejectedNote").textContent = decided
    ? percent(count["Rejected"], decided) + " of rejected applications"
    : "No decisions yet";
  if (typeof Chart === "undefined") return;
  setChartDefaults();
  drawStatusChart(count, applications.length);
  drawTypeChart(applications);
  drawTrendChart(applications);
}

function percent(part, total) {
  return total ? Math.round((part / total) * 100) + "%" : "0%";
}

function setChartDefaults() {
  Chart.defaults.font.family = "Poppins, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = "#6b7a8f";
  Chart.defaults.plugins.tooltip.backgroundColor = "#1b4557";
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.displayColors = false;
  Chart.defaults.plugins.tooltip.titleFont = { weight: "600" };
}

const centerTextPlugin = {
  id: "centerText",
  afterDraw(chart) {
    const area = chart.chartArea;
    const ctx = chart.ctx;
    const x = (area.left + area.right) / 2;
    const y = (area.top + area.bottom) / 2;
    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "#1b4557";
    ctx.font = "700 30px Poppins, sans-serif";
    ctx.fillText(chart.options.centerTotal, x, y - 8);
    ctx.fillStyle = "#6b7a8f";
    ctx.font = "500 11px Poppins, sans-serif";
    ctx.fillText("TOTAL", x, y + 16);
    ctx.restore();
  },
};

function drawStatusChart(count, total) {
  new Chart(el("statusChart"), {
    type: "doughnut",
    data: {
      labels: STATUSES,
      datasets: [
        {
          data: STATUSES.map((status) => count[status]),
          backgroundColor: STATUSES.map((status) => STATUS_COLORS[status]),
          borderColor: "#ffffff",
          borderWidth: 3,
          hoverOffset: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "70%",
      centerTotal: total,
      plugins: { legend: { display: false } },
    },
    plugins: [centerTextPlugin],
  });
  el("statusLegend").innerHTML = STATUSES.map(
    (status) => `
    <li>
      <span class="legend-dot dot-${status.toLowerCase().replace(/\s+/g, "-")}"></span>
      <span class="legend-name">${status}</span>
      <strong>${count[status]}</strong>
      <small>${percent(count[status], total)}</small>
    </li>`
  ).join("");
}

function drawTypeChart(applications) {
  const rows = SCHOLARSHIP_TYPES.map((type) => ({
    name: type.replace(" Scholarship", ""),
    total: applications.filter((app) => app.scholarshipType === type).length,
  }));
  rows.sort((a, b) => b.total - a.total);
  const maxTotal = Math.max(...rows.map((row) => row.total), 1);
  new Chart(el("typeChart"), {
    type: "bar",
    data: {
      labels: rows.map((row) => row.name),
      datasets: [
        {
          label: "Applications",
          data: rows.map((row) => row.total),
          backgroundColor: rows.map((row) => {
            const opacity = 0.2 + 0.8 * (row.total / maxTotal);
            return `rgba(56, 118, 29, ${opacity.toFixed(2)})`;
          }),
          borderRadius: 6,
          borderSkipped: false,
          barThickness: 18,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          beginAtZero: true,
          suggestedMax: 4,
          ticks: { precision: 0 },
          grid: { color: "#eef2ea" },
          border: { display: false },
        },
        y: { grid: { display: false }, border: { display: false } },
      },
    },
  });
}

function drawTrendChart(applications) {
  const days = [];
  for (let i = 13; i >= 0; i--) {
    const day = new Date();
    day.setDate(day.getDate() - i);
    days.push(day);
  }
  const labels = days.map((day) => day.toLocaleDateString("en-US", { month: "short", day: "numeric" }));
  const totals = days.map(
    (day) => applications.filter((app) => new Date(app.dateSubmitted).toDateString() === day.toDateString()).length
  );
  const sum = totals.reduce((a, b) => a + b, 0);
  el("trendChip").textContent = sum + (sum === 1 ? " application" : " applications");
  const canvas = el("trendChart");
  const fade = canvas.getContext("2d").createLinearGradient(0, 0, 0, 260);
  fade.addColorStop(0, "rgba(56, 118, 29, 0.28)");
  fade.addColorStop(1, "rgba(56, 118, 29, 0.02)");
  new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Applications submitted",
          data: totals,
          borderColor: "#38761d",
          backgroundColor: fade,
          borderWidth: 3,
          cubicInterpolationMode: "monotone",
          fill: true,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBackgroundColor: "#ffffff",
          pointBorderColor: "#38761d",
          pointBorderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { display: false } },
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 7 },
        },
        y: {
          beginAtZero: true,
          suggestedMax: 4,
          ticks: { precision: 0 },
          grid: { color: "#eef2ea", borderDash: [4, 4] },
          border: { display: false },
        },
      },
    },
  });
}

let chosenTrimester = "";
let pendingTerm = null;

async function openTermEditor() {
  const term = await getCurrentTerm();
  chosenTrimester = term.trimester;
  el("trimesterChoices").innerHTML = TRIMESTERS.map(
    (name) => `
    <button type="button" class="choice ${name === term.trimester ? "selected" : ""}" data-trimester="${name}">
      <i class="ti ti-circle-check"></i> ${name}
    </button>`
  ).join("");
  el("termYear").value = term.academicYear.replace(/\u2013/g, "-");
  hideAlert("termAlert");
  clearFieldErrors(["termTrimesterError", "termYearError"]);
  openModal("termModal");
}

function pickTrimester(name) {
  chosenTrimester = name;
  el("trimesterChoices").querySelectorAll(".choice").forEach((button) => {
    button.classList.toggle("selected", button.dataset.trimester === name);
  });
}

async function handleTermSubmit(e) {
  e.preventDefault();
  hideAlert("termAlert");
  clearFieldErrors(["termTrimesterError", "termYearError"]);
  const academicYear = val("termYear");
  let hasError = false;
  if (!chosenTrimester) {
    showFieldError("termTrimesterError", "Please choose a trimester.");
    hasError = true;
  }
  const yearCheck = checkAcademicYear(academicYear);
  if (!yearCheck.valid) {
    showFieldError("termYearError", yearCheck.message);
    hasError = true;
  }
  if (hasError) return;
  const current = await getCurrentTerm();
  const newLabel = `${chosenTrimester}, AY ${normalizeAcademicYear(academicYear)}`;
  if (newLabel === current.label) {
    showAlert("termAlert", "The system is already on " + current.label + ". Nothing was changed.");
    return;
  }
  const waiting = (await getActiveApplications()).length;
  pendingTerm = { trimester: chosenTrimester, academicYear };
  el("termConfirmText").textContent =
    waiting === 0
      ? `Move the system from ${current.label} to ${newLabel}?`
      : `Move the system from ${current.label} to ${newLabel}? ` +
        `${waiting} application${waiting === 1 ? "" : "s"} will be filed under "${current.label}" and the new term will start empty. ` +
        `Nothing is deleted - the students' details, documents and status history stay available.`;
  openModal("termConfirmModal");
}

async function applyNewTerm() {
  const result = await setCurrentTerm(pendingTerm.trimester, pendingTerm.academicYear);
  if (result.error) {
    closeModal("termConfirmModal");
    showAlert("termAlert", result.error);
    return;
  }
  pendingTerm = null;
  closeModal("termConfirmModal");
  closeModal("termModal");
  setFlash(
    result.archived === 0
      ? `The system is now on ${result.label}.`
      : `The system is now on ${result.label}. ${result.archived} application${result.archived === 1 ? " was" : "s were"} kept and labelled "${result.previousLabel}".`
  );
  window.location.reload();
}

runPage(async () => {
  currentUser = await requireRole(["staff", "admin"]);
  if (!currentUser) return;
  initSidebar(currentUser, "overview");
  await showOverview();
  el("termButton").addEventListener("click", () => runPage(openTermEditor));
  el("trimesterChoices").addEventListener("click", (e) => {
    const button = e.target.closest("[data-trimester]");
    if (button) pickTrimester(button.dataset.trimester);
  });
  el("termForm").addEventListener("submit", (e) => runPage(() => handleTermSubmit(e)));
  el("termConfirmBtn").addEventListener("click", () => runPage(applyNewTerm));
});
