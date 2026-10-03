let currentUser = null;

runPage(startPage);

async function startPage() {
  currentUser = await requireRole(["student"]);
  if (!currentUser) return;
  initSidebar(currentUser, "overview");
  el("openGuidelines").addEventListener("click", () => openModal("guidelinesModal"));
  el("programGrid").addEventListener("click", (e) => {
    const button = e.target.closest("[data-program]");
    if (button) window.location.href = "scholarships.html?view=" + encodeURIComponent(button.dataset.program);
  });
  await showOverview();
}

function twoDigits(number) {
  return String(number).padStart(2, "0");
}

function pastTermNoteHtml(pastCount) {
  if (pastCount <= 0) return "";
  const appWord = pastCount === 1 ? "application" : "applications";
  const verb = pastCount === 1 ? "is" : "are";
  return `<p class="term-tag-note">Your ${pastCount} ${appWord} from an earlier term ${verb} still saved in My Applications.</p>`;
}

async function showOverview() {
  const applications = await getActiveApplicationsForStudent(currentUser.id);
  const pastCount = (await getApplicationsForStudent(currentUser.id)).length - applications.length;
  const latest = applications[0];
  const termLabel = await getCurrentTermLabel();
  el("welcomeName").textContent = currentUser.fullName.split(" ")[0];
  el("termText").textContent = termLabel;
  el("statPrograms").textContent = twoDigits(SCHOLARSHIP_CATALOG.length);
  el("statApplications").textContent = twoDigits(applications.length);
  if (latest) {
    el("statStatus").innerHTML = statusBadge(latest.status);
    el("statStatusNote").textContent = "Open My Applications for the full history";
  }
  el("latestApplication").innerHTML = latest
    ? applicationCardHtml(latest)
    : `
    <div class="card empty-state">
      <i class="ti ti-clipboard-off icon"></i>
      <p>You have not applied for a scholarship this term yet.</p>
      ${pastTermNoteHtml(pastCount)}
      <a class="btn btn-primary btn-sm" href="scholarships.html">Browse scholarships</a>
    </div>`;
  el("programGrid").innerHTML = SCHOLARSHIP_CATALOG.slice(0, 2).map(programCardHtml).join("");
  el("checklist").innerHTML = SCHOLARSHIP_REQUIREMENTS.map(
    (requirement) => `<li><i class="ti ti-circle-dashed"></i> ${requirement.label}</li>`
  ).join("");
}

function applicationCardHtml(app, termLabel) {
  const decided = app.status === "Approved" || app.status === "Rejected";
  const rejected = app.status === "Rejected";
  const evaluationStep = decided ? "done" : "current";
  const finalStep = rejected ? "rejected" : decided ? "done" : "";
  const finalIcon = rejected ? "ti-x" : decided ? "ti-check" : "";
  const hint =
    app.status === "Under Evaluation"
      ? "Your requirements are being evaluated."
      : app.status === "Submitted"
        ? "Your application was received and is waiting for review."
        : "Current status: " + app.status;
  return `
    <section class="card application-card">
      <div class="application-title">
        <div class="program-icon green"><i class="ti ti-award"></i></div>
        <div>
          <span class="micro">${app.code}</span>
          <h3>${app.scholarshipType}</h3>
          <p>${escapeHtml(app.term || termLabel || "")}</p>
        </div>
      </div>

      <div class="application-meta">
        <span>Submitted ${formatDate(app.dateSubmitted)}</span>
        ${statusBadge(app.status)}
      </div>

      <div class="progress-track">
        <div class="step done"><span><i class="ti ti-check"></i></span>Submitted</div>
        <div class="step-line done"></div>
        <div class="step ${evaluationStep}"><span>${decided ? '<i class="ti ti-check"></i>' : "2"}</span>Evaluation</div>
        <div class="step-line ${decided ? "done" : ""}"></div>
        <div class="step ${finalStep}"><span>${finalIcon ? `<i class="ti ${finalIcon}"></i>` : "3"}</span>${decided ? app.status : "Final decision"}</div>
      </div>

      <div class="application-bottom">
        <span><i class="ti ti-info-circle"></i> ${hint}</span>
        <a class="text-link" href="my-applications.html?view=${app.id}">View details <i class="ti ti-arrow-right"></i></a>
      </div>
    </section>`;
}
