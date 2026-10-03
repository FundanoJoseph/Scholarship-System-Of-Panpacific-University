const STATUSES = ["Submitted", "Under Evaluation", "Approved", "Rejected"];

const TRIMESTERS = ["1st Trimester", "2nd Trimester", "3rd Trimester"];

const SCHOLARSHIP_TYPES = [
  "Academic Scholarship",
  "Entrance Exam Scholarship",
  "4Ps Scholarship",
  "Urdanetarian Scholarship",
  "RPSEA Scholarship",
  "SOC Scholarship",
  "BSA Scholarship",
  "New Program Scholarship",
];

const API_BASE = (function () {
  const configured = window.SAMS_API_BASE;
  if (configured) return String(configured).replace(/\/+$/, "");
  const meta = document.querySelector('meta[name="sams-api-base"]');
  if (meta && meta.content) return meta.content.replace(/\/+$/, "");
  return "/api";
})();

const ACCESS_TOKEN_KEY = "sams_access_token";
const REFRESH_TOKEN_KEY = "sams_refresh_token";
const RESET_TOKEN_KEY = "sams_reset_token";

const LEGACY_STORAGE_KEYS = ["sams_db_v3", "sams_session_v2", "sams_reset_email"];
const LEGACY_DATABASE_NAMES = ["sams_files_v2"];

function clearLegacyBrowserData() {
  LEGACY_STORAGE_KEYS.forEach((key) => {
    try {
      localStorage.removeItem(key);
      sessionStorage.removeItem(key);
    } catch (error) {
      console.error("Could not clear old browser data:", error);
    }
  });
  if (!window.indexedDB || !indexedDB.deleteDatabase) return;
  LEGACY_DATABASE_NAMES.forEach((name) => {
    try {
      indexedDB.deleteDatabase(name);
    } catch (error) {
      console.error("Could not clear old browser files:", error);
    }
  });
}

clearLegacyBrowserData();

function friendlyError(error) {
  const text = error && error.message ? error.message : String(error || "Something went wrong.");
  return text;
}

function authToken() {
  return sessionStorage.getItem(ACCESS_TOKEN_KEY) || "";
}

function loggedIn() {
  return Boolean(authToken() || sessionStorage.getItem(REFRESH_TOKEN_KEY));
}

function storeSession(payload) {
  if (payload.access_token) sessionStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  if (payload.refresh_token) sessionStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
}

function clearSession() {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function errorMessage(response) {
  let detail = "";
  try {
    const data = await response.json();
    if (typeof data.detail === "string") detail = data.detail;
    else if (Array.isArray(data.detail) && data.detail[0] && data.detail[0].msg) detail = data.detail[0].msg;
    else if (typeof data.message === "string") detail = data.message;
  } catch (error) {
    detail = "";
  }
  if (detail) return detail;
  if (response.status === 401) return "Please log in again.";
  if (response.status === 403) return "Your account is not allowed to do this.";
  if (response.status === 404) return "That record could not be found.";
  if (response.status >= 500) return "The server had a problem. Please try again.";
  return "Something went wrong. Please try again.";
}

async function rawRequest(path, options) {
  const settings = options || {};
  const headers = Object.assign({}, settings.headers);
  if (authToken()) headers.Authorization = "Bearer " + authToken();
  let body = settings.body;
  if (settings.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(settings.json);
  }
  let response;
  try {
    response = await fetch(API_BASE + path, {
      method: settings.method || "GET",
      headers: headers,
      body: body,
    });
  } catch (error) {
    throw new ApiError("Cannot reach the server. Please check your connection and try again.", 0);
  }
  return response;
}

let refreshInFlight = null;

function refreshSession() {
  if (refreshInFlight) return refreshInFlight;
  const refreshToken = sessionStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refreshToken) return Promise.resolve(false);
  refreshInFlight = fetch(API_BASE + "/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refreshToken: refreshToken }),
  })
    .then(async (response) => {
      if (!response.ok) {
        clearSession();
        return false;
      }
      storeSession(await response.json());
      return true;
    })
    .catch(() => false)
    .then((result) => {
      refreshInFlight = null;
      return result;
    });
  return refreshInFlight;
}

async function apiRequest(path, options) {
  const settings = Object.assign({}, options);
  let response = await rawRequest(path, settings);
  if (response.status === 401 && !settings.retried) {
    const refreshed = await refreshSession();
    if (refreshed) {
      settings.retried = true;
      response = await rawRequest(path, settings);
    }
  }
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status);
  if (settings.raw) return response;
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

async function getCurrentUser() {
  if (!loggedIn()) return null;
  try {
    const data = await apiRequest("/auth/me");
    return data.user;
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      clearSession();
      return null;
    }
    throw error;
  }
}

async function signIn(email, password) {
  try {
    const data = await apiRequest("/auth/login", { method: "POST", json: { email, password } });
    storeSession(data);
    return { user: data.user };
  } catch (error) {
    if (error.status === 400 || error.status === 401) return { error: error.message };
    throw error;
  }
}

async function signOutUser() {
  try {
    await apiRequest("/auth/logout", { method: "POST" });
  } catch (error) {
    console.error("Sign out could not reach the server:", error.message);
  }
  clearSession();
}

async function signUpStudent(details) {
  try {
    const data = await apiRequest("/auth/register", {
      method: "POST",
      json: {
        fullName: details.fullName,
        studentId: details.studentId,
        email: details.email,
        program: details.program,
        yearLevel: details.yearLevel,
        password: details.password,
      },
    });
    storeSession(data);
    return { user: data.user };
  } catch (error) {
    if (error.status === 400) return { error: error.message };
    throw error;
  }
}

async function sendPasswordReset(email) {
  try {
    const data = await apiRequest("/auth/password-reset/request", { method: "POST", json: { email } });
    if (data.resetToken) sessionStorage.setItem(RESET_TOKEN_KEY, data.resetToken);
    return data.emailed ? { emailed: true } : {};
  } catch (error) {
    if (error.status === 400) return { error: error.message };
    throw error;
  }
}

async function setNewPassword(newPassword) {
  const params = new URLSearchParams(String(window.location.hash || "").replace(/^#/, ""));
  const token = params.get("access_token") || sessionStorage.getItem(RESET_TOKEN_KEY) || "";
  if (!token) return { error: 'Please start from "Forgot password?" on the login page.' };
  try {
    await apiRequest("/auth/password-reset/confirm", { method: "POST", json: { token, newPassword } });
  } catch (error) {
    return { error: error.message };
  }
  sessionStorage.removeItem(RESET_TOKEN_KEY);
  if (window.location.hash) history.replaceState(null, "", window.location.pathname);
  return {};
}

async function changeOwnPassword(user, currentPassword, newPassword) {
  try {
    await apiRequest("/auth/change-password", {
      method: "POST",
      json: { currentPassword, newPassword },
    });
    return {};
  } catch (error) {
    if (error.status === 400) return { error: error.message };
    throw error;
  }
}

async function updateOwnProfile(userId, patch) {
  await apiRequest("/users/me", { method: "PATCH", json: patch });
}

async function allStaffAccounts() {
  const data = await apiRequest("/users");
  return data.users;
}

async function createStaffAccount(details) {
  try {
    await apiRequest("/users", {
      method: "POST",
      json: {
        role: details.role,
        fullName: details.fullName,
        email: details.email,
        password: details.password,
      },
    });
    return {};
  } catch (error) {
    if (error.status === 400 || error.status === 403) return { error: error.message };
    throw error;
  }
}

let termRequest = null;

function loadTerm() {
  if (!termRequest) {
    termRequest = apiRequest("/term").catch((error) => {
      termRequest = null;
      throw error;
    });
  }
  return termRequest;
}

async function getCurrentTerm() {
  const data = await loadTerm();
  return data.term;
}

async function getCurrentTermLabel() {
  const term = await getCurrentTerm();
  return term.label;
}

async function setCurrentTerm(trimester, academicYear) {
  try {
    termRequest = null;
    const data = await apiRequest("/term", { method: "POST", json: { trimester, academicYear } });
    return data;
  } catch (error) {
    if (error.status === 400 || error.status === 403) return { error: error.message };
    throw error;
  }
}

async function getAllApplications() {
  const data = await apiRequest("/applications?scope=all");
  return data.applications;
}

async function getActiveApplications() {
  const data = await apiRequest("/applications?scope=active");
  return data.applications;
}

async function getApplicationsForStudent(studentUserId) {
  const data = await apiRequest("/applications?scope=mine");
  return data.applications;
}

async function getActiveApplicationsForStudent(studentUserId) {
  const data = await apiRequest("/applications?scope=mine-active");
  return data.applications;
}

async function getApplicationHistoryRows() {
  const data = await apiRequest("/applications/history");
  return data.rows;
}

async function getApplicationById(id) {
  try {
    const data = await apiRequest("/applications/" + encodeURIComponent(id));
    return data.application;
  } catch (error) {
    if (error.status === 404) return null;
    throw error;
  }
}

async function createApplication(application, files) {
  const form = new FormData();
  form.append(
    "payload",
    JSON.stringify({
      program: application.program,
      yearLevel: application.yearLevel,
      scholarshipType: application.scholarshipType,
      gwa: application.gwa || "",
    })
  );
  SCHOLARSHIP_REQUIREMENTS.forEach((item) => {
    const file = files ? files[item.key] : null;
    if (file) form.append(item.key, file, file.name);
  });
  const data = await apiRequest("/applications", { method: "POST", body: form });
  return data.application;
}

async function updateApplicationStatus(appId, status, remarks, discountPercent) {
  const data = await apiRequest("/applications/" + encodeURIComponent(appId) + "/status", {
    method: "POST",
    json: { status: status, remarks: remarks || "", discountPercent: discountPercent || "" },
  });
  return data.application;
}

async function updateApplicationDiscount(appId, discountPercent) {
  const data = await apiRequest("/applications/" + encodeURIComponent(appId) + "/discount", {
    method: "PATCH",
    json: { discountPercent: discountPercent || "" },
  });
  return data.application;
}

async function deleteApplication(appId) {
  const data = await apiRequest("/applications/" + encodeURIComponent(appId), { method: "DELETE" });
  return data.application;
}

async function fetchDocumentBlob(appId, requirementKey) {
  const response = await apiRequest(
    "/applications/" + encodeURIComponent(appId) + "/documents/" + encodeURIComponent(requirementKey),
    { raw: true }
  );
  return response.blob();
}

async function getNotificationsForUser(userId) {
  const data = await apiRequest("/notifications");
  return data.notifications;
}

async function unreadNotificationCount(userId) {
  const data = await apiRequest("/notifications/unread-count");
  return data.count;
}

async function markNotificationRead(id) {
  await apiRequest("/notifications/" + encodeURIComponent(id) + "/read", { method: "POST" });
}

async function markAllNotificationsRead(userId) {
  await apiRequest("/notifications/read-all", { method: "POST" });
}
