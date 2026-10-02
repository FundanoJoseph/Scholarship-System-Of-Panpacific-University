function el(id) {
  return document.getElementById(id);
}

function val(id) {
  return el(id).value.trim();
}

const HTML_ESCAPES = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

function escapeHtml(text) {
  if (!text) return "";
  return String(text).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}
function getInitials(name) {
  if (!name) return "?";
  const parts = name.trim().split(" ");
  return (parts[0][0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
}
function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
function formatDateTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
function localDateStr(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function statusBadgeClass(status) {
  return "badge-" + status.toLowerCase().replace(/\s+/g, "-");
}
function statusBadge(status) {
  return `<span class="badge ${statusBadgeClass(status)}">${status}</span>`;
}
function showAlert(id, message) {
  const box = el(id);
  box.textContent = message;
  box.classList.add("show");
}
function hideAlert(id) {
  const box = el(id);
  if (box) box.classList.remove("show");
}
function showToast(message, isError) {
  let toast = el("appToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "appToast";
    toast.className = "toast";
    toast.innerHTML = `
      <i class="ti ti-circle-check"></i>
      <span id="appToastText"></span>
      <button type="button" class="toast-close" id="appToastClose" aria-label="Close message"><i class="ti ti-x"></i></button>`;
    document.body.appendChild(toast);
    el("appToastClose").addEventListener("click", () => toast.classList.remove("show"));
  }
  toast.classList.toggle("toast-error", !!isError);
  toast.querySelector("i").className = isError ? "ti ti-alert-circle" : "ti ti-circle-check";
  el("appToastText").textContent = message;
  toast.classList.add("show");
  clearTimeout(toast.hideTimer);
  toast.hideTimer = setTimeout(() => toast.classList.remove("show"), 4000);
}
function setFlash(message) {
  sessionStorage.setItem("sams_flash", message);
}
function showFlashIfAny() {
  const message = sessionStorage.getItem("sams_flash");
  if (!message) return;
  sessionStorage.removeItem("sams_flash");
  showToast(message);
}
function openModal(id) {
  el(id).classList.add("show");
  document.body.classList.add("modal-open");
}
function closeModal(id) {
  el(id).classList.remove("show");
  if (!document.querySelector(".modal-overlay.show")) document.body.classList.remove("modal-open");
}
function closeAllModals() {
  document.querySelectorAll(".modal-overlay.show").forEach((box) => closeModal(box.id));
}
document.addEventListener("click", (e) => {
  const closeButton = e.target.closest("[data-close-modal]");
  if (closeButton) {
    closeModal(closeButton.closest(".modal-overlay").id);
    return;
  }
  if (e.target.classList.contains("modal-overlay")) closeModal(e.target.id);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeAllModals();
});
function homePageFor(user) {
  return user.role === "student" ? "student-dashboard.html" : "staff-dashboard.html";
}
async function requireRole(allowedRoles) {
  const user = await getCurrentUser();
  if (!user) {
    window.location.href = "index.html";
    return null;
  }
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    window.location.href = homePageFor(user);
    return null;
  }
  return user;
}
async function redirectIfLoggedIn() {
  const user = await getCurrentUser();
  if (!user) return false;
  window.location.href = homePageFor(user);
  return true;
}
async function logout() {
  await signOutUser();
  window.location.href = "index.html";
}
let pageIsLeaving = false;
window.addEventListener("pagehide", () => {
  pageIsLeaving = true;
});
function runPage(work) {
  return work().catch((error) => {
    if (pageIsLeaving) return;
    console.error(error);
    showToast(friendlyError(error), true);
  });
}
function newId() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}
function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}
showFlashIfAny();