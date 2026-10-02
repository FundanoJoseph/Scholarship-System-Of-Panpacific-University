function applicationDetailsHtml(app, editable) {
  const discountEditable = editable && app.status === "Approved";
  const documentsHtml = SCHOLARSHIP_REQUIREMENTS.map((requirement) => {
    const doc = app.documents[requirement.key];
    if (doc && doc.name) {
      return `
        <button type="button" class="document-preview" data-file-app="${app.id}" data-file-key="${requirement.key}" title="Click to view this file">
          <i class="ti ti-file-text"></i>
          <span>${requirement.label}<small>${escapeHtml(doc.name)}</small></span>
          <i class="ti ti-eye view-icon"></i>
        </button>`;
    }
    return `
      <div class="document-preview document-missing">
        <i class="ti ti-file-off"></i>
        <span>${requirement.label}<small>Not submitted</small></span>
      </div>`;
  }).join("");
  const historyHtml = app.history
    .map(
      (entry) => `
    <li>
      <strong>${entry.status}</strong>
      <small>${formatDateTime(entry.date)}${entry.by ? " &middot; " + escapeHtml(entry.by) : ""}</small>
      ${entry.remarks ? `<p>${escapeHtml(entry.remarks)}</p>` : ""}
    </li>`
    )
    .join("");
  const termHtml = app.term
    ? `
    <div class="term-tag-row">
      <span class="term-tag ${app.archived ? "term-past" : ""}">
        <i class="ti ti-calendar-event"></i> ${escapeHtml(app.term)}
      </span>
      ${app.archived ? '<span class="term-tag-note">Past term &middot; kept for records, no longer being evaluated</span>' : ""}
    </div>`
    : "";
  return `
    ${termHtml}
    <div class="detail-banner">
      <div>
        <span class="micro">${app.code}</span>
        <h3>${app.scholarshipType}</h3>
      </div>
      ${statusBadge(app.status)}
    </div>

    <dl class="detail-list">
      <dt>Student</dt><dd>${escapeHtml(app.studentName)} (${escapeHtml(app.studentId)})</dd>
      <dt>Email</dt><dd>${escapeHtml(app.universityEmail)}</dd>
      <dt>Program / year</dt><dd>${escapeHtml(app.program)} &middot; ${escapeHtml(app.yearLevel)}</dd>
      <dt>Term</dt><dd>${escapeHtml(app.term || "\u2014")}</dd>
      <dt>Submitted</dt><dd>${formatDate(app.dateSubmitted)}</dd>
      <dt>Tuition fee discount</dt><dd data-discount-cell><span class="discount-value">${app.discountPercent ? escapeHtml(app.discountPercent) + "%" : "\u2014"}</span>${discountEditable ? ' <button type="button" class="icon-btn" data-discount-action="edit" title="Edit discount"><i class="ti ti-pencil"></i></button>' : ""}</dd>
    </dl>

    <h3 class="modal-subhead">Submitted requirements</h3>
    <div class="submitted-documents">${documentsHtml}</div>

    <h3 class="modal-subhead">Status history</h3>
    <ol class="status-history">${historyHtml}</ol>`;
}

function wireDocumentButtons(container) {
  container.querySelectorAll("[data-file-app]").forEach((button) => {
    button.addEventListener("click", () =>
      viewStoredDocument(button.dataset.fileApp, button.dataset.fileKey)
    );
  });
}

function wireDiscountEdit(container, app, onUpdated) {
  const cell = container.querySelector("[data-discount-cell]");
  if (!cell) return;
  function renderView() {
    cell.innerHTML = `<span class="discount-value">${app.discountPercent ? escapeHtml(app.discountPercent) + "%" : "\u2014"}</span> <button type="button" class="icon-btn" data-discount-action="edit" title="Edit discount"><i class="ti ti-pencil"></i></button>`;
  }
  function renderEdit() {
    cell.innerHTML = `
      <input type="number" class="discount-edit-input" min="0" max="100" step="1" value="${escapeHtml(app.discountPercent)}" />
      <button type="button" class="icon-btn" data-discount-action="save" title="Save"><i class="ti ti-check"></i></button>
      <button type="button" class="icon-btn" data-discount-action="cancel" title="Cancel"><i class="ti ti-x"></i></button>`;
    cell.querySelector(".discount-edit-input").focus();
  }
  cell.addEventListener("click", (e) => {
    const action = e.target.closest("[data-discount-action]");
    if (!action) return;
    if (action.dataset.discountAction === "edit") {
      renderEdit();
    } else if (action.dataset.discountAction === "cancel") {
      renderView();
    } else if (action.dataset.discountAction === "save") {
      runPage(async () => {
        const value = cell.querySelector(".discount-edit-input").value.trim();
        const updated = await updateApplicationDiscount(app.id, value);
        app.discountPercent = updated.discountPercent;
        renderView();
        showToast("Tuition fee discount updated.");
        if (onUpdated) onUpdated(updated);
      });
    }
  });
}