let currentUser = null;
let allApps = [];
let allRows = [];
let activeTab = "All";
let openAppId = null;
let pendingDeleteId = null;
let pendingDecision = null;

runPage(startPage);

async function startPage() {
  currentUser = await requireRole(["staff", "admin"]);
  if (!currentUser) return;
  initSidebar(currentUser, "applications");
  el("termText").textContent = (await getCurrentTerm()).label;
  el("typeFilter").innerHTML += SCHOLARSHIP_TYPES.map((type) => `<option value="${type}">${type}</option>`).join("");
  const requestedStatus = getQueryParam("status");
  const requestedTab = el("statusTabs").querySelector(`[data-status="${requestedStatus}"]`);
  if (requestedTab) {
    el("statusTabs").querySelectorAll(".tab-btn").forEach((t) => t.classList.remove("active"));
    requestedTab.classList.add("active");
    activeTab = requestedTab.dataset.status;
  }
  await reloadData();
  showApplications();
  window.addEventListener("notification-arrived", () =>
    runPage(async () => {
      await reloadData();
      showApplications();
    })
  );
  el("statusTabs").addEventListener("click", (e) => {
    const tab = e.target.closest(".tab-btn");
    if (!tab) return;
    el("statusTabs").querySelectorAll(".tab-btn").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    activeTab = tab.dataset.status;
    runPage(async () => {
      if (activeTab === "History") await reloadData();
      showApplications();
    });
  });
  el("searchBox").addEventListener("input", showApplications);
  el("typeFilter").addEventListener("change", showApplications);
  el("dateFilter").addEventListener("change", showApplications);
  el("clearFiltersBtn").addEventListener("click", () => {
    el("searchBox").value = "";
    el("typeFilter").value = "";
    el("dateFilter").value = "";
    showApplications();
  });
  el("applicationRows").addEventListener("click", (e) => {
    const button = e.target.closest("[data-open-app]");
    if (button) openReview(button.dataset.openApp);
    const deleteButton = e.target.closest("[data-delete-app]");
    if (deleteButton) askToDelete(deleteButton.dataset.deleteApp);
  });
  el("deleteConfirmBtn").addEventListener("click", () => runPage(confirmDelete));
  el("evalArea").addEventListener("click", (e) => {
    const button = e.target.closest("[data-action]");
    if (!button) return;
    if (button.dataset.action === "start") runPage(startEvaluation);
    if (button.dataset.action === "Approved" || button.dataset.action === "Rejected") {
      askToConfirm(button.dataset.action);
    }
  });
  el("confirmActionBtn").addEventListener("click", () => runPage(applyDecision));
}

function rowActionsHtml(appId) {
  return `
    <div class="row-actions">
      <button type="button" class="btn btn-outline btn-sm" data-open-app="${appId}"><i class="ti ti-eye"></i> View</button>
      <button type="button" class="btn btn-danger btn-sm" data-delete-app="${appId}"><i class="ti ti-trash"></i> Delete</button>
    </div>`;
}

async function reloadData() {
  allApps = await getActiveApplications();
  const rows = [];
  const applications = await getAllApplications();
  applications.forEach((app) => {
    for (let i = 1; i < app.history.length; i++) {
      rows.push({
        code: app.code,
        term: app.term || "",
        archived: !!app.archived,
        studentName: app.studentName,
        studentId: app.studentId,
        scholarshipType: app.scholarshipType,
        previousStatus: app.history[i - 1].status,
        newStatus: app.history[i].status,
        date: app.history[i].date,
        remarks: app.history[i].remarks,
      });
    }
  });
  rows.sort((a, b) => new Date(b.date) - new Date(a.date));
  allRows = rows;
}

function showHistory() {
  const search = el("searchBox").value.trim().toLowerCase();
  const type = el("typeFilter").value;
  const date = el("dateFilter").value;
  const rows = allRows.filter((row) => {
    if (type && row.scholarshipType !== type) return false;
    if (date && localDateStr(row.date) !== date) return false;
    if (search) {
      const haystack = [
        row.code,
        row.term,
        row.studentName,
        row.studentId,
        row.scholarshipType,
        row.previousStatus,
        row.newStatus,
        formatDateTime(row.date),
        row.remarks,
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });
  el("historyRows").innerHTML = rows
    .map(
      (row) => `
    <tr>
      <td data-label="Application ID">${row.code}</td>
      <td data-label="Term">${row.term ? `<span class="term-tag ${row.archived ? "term-past" : ""}">${escapeHtml(row.term)}</span>` : "&mdash;"}</td>
      <td data-label="Student"><div><strong>${escapeHtml(row.studentName)}</strong><small>${escapeHtml(row.studentId)}</small></div></td>
      <td data-label="Scholarship">${row.scholarshipType}</td>
      <td data-label="Previous">${statusBadge(row.previousStatus)}</td>
      <td data-label="New">${statusBadge(row.newStatus)}</td>
      <td data-label="Date / time">${formatDateTime(row.date)}</td>
      <td data-label="Remarks">${row.remarks ? escapeHtml(row.remarks) : "&mdash;"}</td>
    </tr>`
    )
    .join("");
  el("historyEmptyState").classList.toggle("hidden", rows.length > 0);
}

function showApplications() {
  const showingHistory = activeTab === "History";
  el("applicationsWrap").hidden = showingHistory;
  el("historyWrap").hidden = !showingHistory;
  if (showingHistory) {
    el("emptyState").classList.add("hidden");
    showHistory();
    return;
  }
  el("historyEmptyState").classList.add("hidden");
  const search = el("searchBox").value.trim().toLowerCase();
  const type = el("typeFilter").value;
  const date = el("dateFilter").value;
  const applications = allApps.filter((app) => {
    if (activeTab !== "All" && app.status !== activeTab) return false;
    if (type && app.scholarshipType !== type) return false;
    if (date && localDateStr(app.dateSubmitted) !== date) return false;
    if (search) {
      const approval = [...app.history].reverse().find((entry) => entry.status === "Approved");
      const fields = [
        app.code,
        app.studentName,
        app.studentId,
        app.scholarshipType,
        formatDate(app.dateSubmitted),
        app.discountPercent ? app.discountPercent + "%" : "",
        app.status,
      ];
      if (activeTab === "Approved") {
        fields.push(app.program, app.yearLevel, approval ? formatDate(approval.date) : "", approval ? approval.by : "");
      }
      if (!fields.join(" ").toLowerCase().includes(search)) return false;
    }
    return true;
  });
  const showingApproved = activeTab === "Approved";
  document.querySelectorAll(".approved-only").forEach((th) => {
    th.hidden = !showingApproved;
  });
  el("applicationRows").innerHTML = applications
    .map((app) => {
      const approval = [...app.history].reverse().find((entry) => entry.status === "Approved");
      const approvedCells = showingApproved
        ? `
      <td data-label="Program / year">${escapeHtml(app.program)} &middot; ${escapeHtml(app.yearLevel)}</td>
      <td data-label="Approved on">${approval ? formatDate(approval.date) : "&mdash;"}</td>
      <td data-label="Approved by">${approval ? escapeHtml(approval.by) : "&mdash;"}</td>`
        : "";
      return `
    <tr>
      <td data-label="Application ID">${app.code}</td>
      <td data-label="Student"><div><strong>${escapeHtml(app.studentName)}</strong><small>${escapeHtml(app.studentId)}</small></div></td>
      <td data-label="Scholarship">${app.scholarshipType}</td>
      <td data-label="Submitted">${formatDate(app.dateSubmitted)}</td>${approvedCells}
      <td data-label="Discount %">${app.discountPercent ? escapeHtml(app.discountPercent) + "%" : "&mdash;"}</td>
      <td data-label="Status">${statusBadge(app.status)}</td>
      <td data-label="">${rowActionsHtml(app.id)}</td>
    </tr>`;
    })
    .join("");
  el("emptyState").classList.toggle("hidden", applications.length > 0);
}

function openReview(appId) {
  const app = allApps.find((item) => item.id === appId);
  if (!app) return;
  openAppId = appId;
  hideAlert("evalAlert");
  el("reviewBody").innerHTML = applicationDetailsHtml(app, true);
  wireDocumentButtons(el("reviewBody"));
  wireDiscountEdit(el("reviewBody"), app, (updated) => {
    allApps = allApps.map((item) => (item.id === updated.id ? updated : item));
    showApplications();
  });
  showEvaluation(app);
  openModal("reviewModal");
}

function showEvaluation(app) {
  if (app.status === "Submitted") {
    el("evalArea").innerHTML = `
      <p class="modal-text">Check the documents above, then start the evaluation. The student will be notified.</p>
      <button type="button" class="btn btn-primary" data-action="start"><i class="ti ti-hourglass"></i> Start evaluation</button>`;
    return;
  }
  if (app.status === "Under Evaluation") {
    el("evalArea").innerHTML = `
      <div class="form-group">
        <label for="evalDiscount">Tuition fee discount percent (optional)</label>
        <div class="input-wrap"><i class="ti ti-discount-2"></i><input type="number" id="evalDiscount" min="0" max="100" step="1" placeholder="e.g. 100" /></div>
      </div>
      <div class="form-group">
        <label for="evalRemarks">Remarks (required to reject, optional to approve)</label>
        <div class="input-wrap"><i class="ti ti-notes"></i><textarea id="evalRemarks" placeholder="Add evaluation remarks..."></textarea></div>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn btn-primary" data-action="Approved"><i class="ti ti-circle-check"></i> Approve</button>
        <button type="button" class="btn btn-danger" data-action="Rejected"><i class="ti ti-circle-x"></i> Reject</button>
      </div>`;
    return;
  }
  el("evalArea").innerHTML = `
    <div class="alert ${app.status === "Approved" ? "alert-success" : "alert-error"} show">
      <strong>${app.status}</strong>${app.remarks ? ", " + escapeHtml(app.remarks) : ""}
      ${app.evaluatedBy ? `<br><span class="you-note">Evaluated by ${escapeHtml(app.evaluatedBy)}</span>` : ""}
    </div>`;
}

async function saveStatus(status, remarks, discountPercent) {
  try {
    const updated = await updateApplicationStatus(openAppId, status, remarks, discountPercent);
    allApps = allApps.map((app) => (app.id === updated.id ? updated : app));
    return true;
  } catch (error) {
    closeModal("confirmModal");
    showAlert("evalAlert", friendlyError(error));
    return false;
  }
}

async function startEvaluation() {
  if (!(await saveStatus("Under Evaluation", ""))) return;
  showToast("Application moved to Under Evaluation.");
  refreshAfterChange();
}

function askToConfirm(decision) {
  const app = allApps.find((item) => item.id === openAppId);
  const remarks = el("evalRemarks").value.trim();
  const discountPercent = el("evalDiscount").value.trim();
  hideAlert("evalAlert");
  if (decision === "Rejected" && !remarks) {
    showAlert("evalAlert", "Please provide a reason or remarks before rejecting this application.");
    return;
  }
  pendingDecision = { decision, remarks, discountPercent };
  const approving = decision === "Approved";
  el("confirmTitle").textContent = approving ? "Confirm approval" : "Confirm rejection";
  el("confirmText").textContent = approving
    ? `Are you sure you want to approve ${app.code} (${app.studentName})?`
    : `Are you sure you want to reject ${app.code} (${app.studentName})? The student will see your remarks.`;
  el("confirmActionBtn").className = "btn " + (approving ? "btn-primary" : "btn-danger");
  el("confirmActionBtn").textContent = approving ? "Yes, approve" : "Yes, reject";
  openModal("confirmModal");
}

async function applyDecision() {
  const { decision, remarks, discountPercent } = pendingDecision;
  if (!(await saveStatus(decision, remarks, discountPercent))) return;
  closeModal("confirmModal");
  showToast(`Application ${decision.toLowerCase()}.`);
  refreshAfterChange();
}

function askToDelete(appId) {
  const app = allApps.find((item) => item.id === appId);
  if (!app) return;
  pendingDeleteId = appId;
  el("deleteText").textContent = `Are you sure you want to delete ${app.code} (${app.studentName})? This removes the application and its documents and cannot be undone.`;
  openModal("deleteModal");
}

async function confirmDelete() {
  const removed = await deleteApplication(pendingDeleteId);
  await deleteApplicationFiles(removed);
  allApps = allApps.filter((app) => app.id !== removed.id);
  pendingDeleteId = null;
  closeModal("deleteModal");
  showApplications();
  showToast(`Application ${removed.code} deleted.`);
}

function refreshAfterChange() {
  openReview(openAppId);
  showApplications();
}