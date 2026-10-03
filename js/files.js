let currentFileUrl = null;

function ensureFileModal() {
  if (el("fileModal")) return;
  const wrapper = document.createElement("div");
  wrapper.innerHTML = `
    <div class="modal-overlay" id="fileModal">
      <div class="modal modal-xl">
        <div class="modal-heading">
          <h2 id="fileModalTitle">Document</h2>
          <button type="button" class="close" data-close-modal aria-label="Close dialog"><i class="ti ti-x"></i></button>
        </div>
        <div class="file-viewer" id="fileViewer"></div>
        <div class="modal-actions">
          <a class="btn btn-outline" id="fileOpenLink" target="_blank" rel="noopener"><i class="ti ti-external-link"></i> Open in new tab</a>
          <a class="btn btn-primary" id="fileDownloadLink"><i class="ti ti-download"></i> Download</a>
        </div>
      </div>
    </div>`;
  document.body.appendChild(wrapper.firstElementChild);
}

async function viewStoredDocument(appId, requirementKey) {
  const app = await getApplicationById(appId);
  const doc = app && app.documents[requirementKey];
  if (!doc) return;
  const requirement = SCHOLARSHIP_REQUIREMENTS.find((item) => item.key === requirementKey);
  let file = null;
  try {
    file = await fetchDocumentBlob(appId, requirementKey);
  } catch (error) {
    showToast(friendlyError(error), true);
    return;
  }
  if (!file) {
    showToast("This file could not be opened.", true);
    return;
  }
  ensureFileModal();
  if (currentFileUrl) URL.revokeObjectURL(currentFileUrl);
  currentFileUrl = URL.createObjectURL(file);
  const lowerName = doc.name.toLowerCase();
  const isPdf = file.type === "application/pdf" || lowerName.endsWith(".pdf");
  const isImage = (file.type || "").startsWith("image/") || /\.(jpe?g|png)$/.test(lowerName);
  el("fileModalTitle").textContent = requirement.label;
  if (isPdf) {
    el("fileViewer").innerHTML = `<iframe class="file-frame" title="${escapeHtml(doc.name)}"></iframe>`;
    el("fileViewer").querySelector("iframe").src = currentFileUrl;
  } else if (isImage) {
    el("fileViewer").innerHTML = `<img class="file-image" alt="${escapeHtml(doc.name)}" />`;
    el("fileViewer").querySelector("img").src = currentFileUrl;
  } else {
    el("fileViewer").innerHTML = `<p class="modal-text">This file type cannot be previewed. Use Download.</p>`;
  }
  el("fileOpenLink").href = currentFileUrl;
  el("fileDownloadLink").href = currentFileUrl;
  el("fileDownloadLink").download = doc.name;
  openModal("fileModal");
}
