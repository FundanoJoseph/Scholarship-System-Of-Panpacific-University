const FILE_DB_NAME = "sams_files_v2";
const FILE_STORE = "files";

function safeFileName(name) {
  return name.replace(/[^A-Za-z0-9._-]/g, "_");
}

function storagePathFor(userId, appId, requirementKey, fileName) {
  return userId + "/" + appId + "/" + requirementKey + "-" + safeFileName(fileName);
}

function openFileDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(FILE_DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(FILE_STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function uploadStoredFile(path, file) {
  const database = await openFileDb();
  await new Promise((resolve, reject) => {
    const tx = database.transaction(FILE_STORE, "readwrite");
    tx.objectStore(FILE_STORE).put(file, path);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
  database.close();
}

async function downloadStoredFile(path) {
  if (!path) return null;
  try {
    const database = await openFileDb();
    const file = await new Promise((resolve, reject) => {
      const request = database.transaction(FILE_STORE).objectStore(FILE_STORE).get(path);
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error);
    });
    database.close();
    return file;
  } catch (error) {
    return null;
  }
}

async function deleteApplicationFiles(app) {
  const paths = Object.values(app.documents || {})
    .map((doc) => doc && doc.path)
    .filter(Boolean);
  if (!paths.length) return;
  try {
    const database = await openFileDb();
    await new Promise((resolve, reject) => {
      const tx = database.transaction(FILE_STORE, "readwrite");
      paths.forEach((path) => tx.objectStore(FILE_STORE).delete(path));
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
    database.close();
  } catch (error) {
    console.error("Could not remove the saved files:", error);
  }
}

function makeSamplePdf(title) {
  const safe = title.replace(/[^A-Za-z0-9 .,_-]/g, "");
  const content =
    "BT /F1 20 Tf 60 720 Td (" + safe + ") Tj " +
    "0 -34 Td /F1 12 Tf (Sample placeholder for the demo data. This is not a real uploaded file.) Tj ET";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    "<< /Length " + content.length + " >>\nstream\n" + content + "\nendstream",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [];
  objects.forEach((body, i) => {
    offsets.push(pdf.length);
    pdf += (i + 1) + " 0 obj\n" + body + "\nendobj\n";
  });
  const xrefStart = pdf.length;
  pdf += "xref\n0 " + (objects.length + 1) + "\n0000000000 65535 f \n";
  offsets.forEach((offset) => {
    pdf += String(offset).padStart(10, "0") + " 00000 n \n";
  });
  pdf += "trailer\n<< /Size " + (objects.length + 1) + " /Root 1 0 R >>\nstartxref\n" + xrefStart + "\n%%EOF";
  return new Blob([pdf], { type: "application/pdf" });
}

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
  let file = doc.sample
    ? makeSamplePdf(requirement.label + " - " + doc.name)
    : await downloadStoredFile(doc.path);
  if (!file) {
    showToast("This file could not be opened. It may have been removed from this browser.", true);
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
