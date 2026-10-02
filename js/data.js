const STATUSES = ["Submitted", "Under Evaluation", "Approved", "Rejected"];

const TRIMESTERS = ["1st Trimester", "2nd Trimester", "3rd Trimester"];
const DEFAULT_TERM = { trimester: "1st Trimester", academicYear: "2026\u20132027" };

function makeTermLabel(term) {
  if (!term || !term.trimester) return "";
  return `${term.trimester}, AY ${term.academicYear}`;
}

function currentTermLabel() {
  return makeTermLabel(loadStore().term);
}

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

const DB_KEY = "sams_db_v3";
const SESSION_KEY = "sams_session_v2";
const RESET_KEY = "sams_reset_email";
const LEGACY_DEMO_EMAILS = [
  "admin@panpacificu.edu.ph",
  "staff@panpacificu.edu.ph",
  "juan.delacruz@panpacificu.edu.ph",
  "maria.santos@panpacificu.edu.ph",
];

function uid(prefix) {
  return prefix + "-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function nowISO() {
  return new Date().toISOString();
}

function daysAgoISO(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString();
}

function appCodeFor(index) {
  return `APP-${new Date().getFullYear()}-${String(index).padStart(4, "0")}`;
}

function friendlyError(error) {
  const text = error && error.message ? error.message : String(error || "Something went wrong.");
  if (/quota|exceeded/i.test(text)) {
    return "The browser storage is full. Remove some data or use smaller files.";
  }
  return text;
}

function buildInitialData() {
  return {
    term: { ...DEFAULT_TERM },
    users: [],
    applications: [],
    notifications: [],
    appCounter: 0,
  };
}

function loadStore() {
  let store = null;
  try {
    store = JSON.parse(localStorage.getItem(DB_KEY));
  } catch (e) {
    store = null;
  }
  if (!store || !Array.isArray(store.users)) {
    store = buildInitialData();
    saveStore(store);
  }
  let changed = false;
  const removedUserIds = store.users
    .filter((u) => LEGACY_DEMO_EMAILS.some((email) => sameEmail(u.email, email)))
    .map((u) => u.id);
  if (removedUserIds.length) {
    const removedAppIds = store.applications
      .filter((app) => removedUserIds.includes(app.studentUserId))
      .map((app) => app.id);
    store.users = store.users.filter((u) => !removedUserIds.includes(u.id));
    store.applications = store.applications.filter((app) => !removedAppIds.includes(app.id));
    store.notifications = (store.notifications || []).filter(
      (n) => !removedUserIds.includes(n.userId) && !removedAppIds.includes(n.appId)
    );
    changed = true;
  }
  if (!store.term || !store.term.trimester) {
    store.term = { ...DEFAULT_TERM };
    changed = true;
  }
  const label = makeTermLabel(store.term);
  store.applications.forEach((app) => {
    if (!app.term) {
      app.term = label;
      changed = true;
    }
    if (app.archived === undefined) {
      app.archived = false;
      changed = true;
    }
    if (app.discountPercent === undefined) {
      app.discountPercent = "";
      changed = true;
    }
  });
  if (changed) saveStore(store);
  return store;
}

function saveStore(store) {
  localStorage.setItem(DB_KEY, JSON.stringify(store));
}

function publicUser(user) {
  const { password, ...safe } = user;
  return safe;
}

function sameEmail(a, b) {
  return String(a).trim().toLowerCase() === String(b).trim().toLowerCase();
}

async function getCurrentUser() {
  const id = sessionStorage.getItem(SESSION_KEY);
  if (!id) return null;
  const user = loadStore().users.find((u) => u.id === id);
  return user ? publicUser(user) : null;
}

async function signIn(email, password) {
  const user = loadStore().users.find((u) => sameEmail(u.email, email));
  if (!user || user.password !== password) return { error: "Incorrect email or password." };
  sessionStorage.setItem(SESSION_KEY, user.id);
  return { user: publicUser(user) };
}

async function signOutUser() {
  sessionStorage.removeItem(SESSION_KEY);
}

async function signUpStudent(details) {
  const store = loadStore();
  if (store.users.some((u) => sameEmail(u.email, details.email))) {
    return { error: "An account with this email already exists." };
  }
  const user = {
    id: uid("usr"),
    role: "student",
    fullName: details.fullName,
    email: details.email.trim(),
    password: details.password,
    studentId: details.studentId,
    program: details.program,
    yearLevel: details.yearLevel,
    createdAt: nowISO(),
  };
  store.users.push(user);
  saveStore(store);
  sessionStorage.setItem(SESSION_KEY, user.id);
  return { user: publicUser(user) };
}

async function sendPasswordReset(email) {
  const user = loadStore().users.find((u) => sameEmail(u.email, email));
  if (!user) return { error: "No account was found with that email." };
  sessionStorage.setItem(RESET_KEY, user.email);
  return {};
}

async function setNewPassword(newPassword) {
  const email = sessionStorage.getItem(RESET_KEY);
  if (!email) return { error: 'Please start from "Forgot password?" on the login page.' };
  const store = loadStore();
  const user = store.users.find((u) => sameEmail(u.email, email));
  if (!user) return { error: "Account not found." };
  user.password = newPassword;
  saveStore(store);
  sessionStorage.removeItem(RESET_KEY);
  return {};
}

async function changeOwnPassword(user, currentPassword, newPassword) {
  const store = loadStore();
  const record = store.users.find((u) => u.id === user.id);
  if (!record || record.password !== currentPassword) {
    return { error: "Current password is incorrect." };
  }
  record.password = newPassword;
  saveStore(store);
  return {};
}

async function updateOwnProfile(userId, patch) {
  const store = loadStore();
  const record = store.users.find((u) => u.id === userId);
  if (!record) return;
  record.program = patch.program;
  record.yearLevel = patch.yearLevel;
  saveStore(store);
}

async function allStaffAccounts() {
  return loadStore()
    .users.filter((u) => u.role === "staff" || u.role === "admin")
    .sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt))
    .map(publicUser);
}

async function createStaffAccount(details) {
  const current = await getCurrentUser();
  if (!current || current.role !== "admin") {
    return { error: "Only an Admin can create Staff or Admin accounts." };
  }
  const store = loadStore();
  if (store.users.some((u) => sameEmail(u.email, details.email))) {
    return { error: "An account with this email already exists." };
  }
  store.users.push({
    id: uid("usr"),
    role: details.role,
    fullName: details.fullName,
    email: details.email.trim(),
    password: details.password,
    studentId: "",
    program: "",
    yearLevel: "",
    createdAt: nowISO(),
  });
  saveStore(store);
  return {};
}

async function getCurrentTerm() {
  const term = loadStore().term;
  return { trimester: term.trimester, academicYear: term.academicYear, label: makeTermLabel(term) };
}

async function setCurrentTerm(trimester, academicYear) {
  const user = await getCurrentUser();
  if (!user || (user.role !== "staff" && user.role !== "admin")) {
    return { error: "Only Authorized Staff or Admin can change the term." };
  }
  if (!TRIMESTERS.includes(trimester)) {
    return { error: "Please choose the 1st, 2nd or 3rd Trimester." };
  }
  const yearCheck = checkAcademicYear(academicYear);
  if (!yearCheck.valid) return { error: yearCheck.message };
  const store = loadStore();
  const previousLabel = makeTermLabel(store.term);
  const newTerm = { trimester, academicYear: normalizeAcademicYear(academicYear) };
  const label = makeTermLabel(newTerm);
  if (label === previousLabel) {
    return { error: "The system is already on " + label + ". Nothing was changed." };
  }
  let archived = 0;
  store.applications.forEach((app) => {
    if (!app.archived) {
      app.term = app.term || previousLabel;
      app.archived = true;
      archived++;
    }
  });
  store.term = newTerm;
  saveStore(store);
  return { label, previousLabel, archived };
}

function newestFirst(a, b) {
  return new Date(b.dateSubmitted) - new Date(a.dateSubmitted);
}

async function getAllApplications() {
  return loadStore().applications.slice().sort(newestFirst);
}

async function getActiveApplications() {
  return loadStore()
    .applications.filter((a) => !a.archived && !a.deleted)
    .sort(newestFirst);
}

async function getApplicationsForStudent(studentUserId) {
  return loadStore()
    .applications.filter((a) => a.studentUserId === studentUserId && !a.deleted)
    .sort(newestFirst);
}

async function getActiveApplicationsForStudent(studentUserId) {
  return loadStore()
    .applications.filter((a) => a.studentUserId === studentUserId && !a.archived && !a.deleted)
    .sort(newestFirst);
}

async function getApplicationById(id) {
  return loadStore().applications.find((a) => a.id === id) || null;
}

async function createApplication(app) {
  const store = loadStore();
  const student = store.users.find((u) => u.id === app.studentUserId);
  if (!student || student.role !== "student") {
    throw new Error("Only student accounts can submit applications.");
  }
  store.appCounter = (store.appCounter || 0) + 1;
  const record = {
    id: app.id || uid("app"),
    code: appCodeFor(store.appCounter),
    studentUserId: student.id,
    studentName: student.fullName,
    studentId: student.studentId,
    universityEmail: student.email,
    program: app.program,
    yearLevel: app.yearLevel,
    gwa: app.gwa || "",
    scholarshipType: app.scholarshipType,
    status: "Submitted",
    remarks: "",
    evaluatedBy: "",
    discountPercent: "",
    dateSubmitted: nowISO(),
    documents: app.documents,
    term: makeTermLabel(store.term),
    archived: false,
    deleted: false,
    deletedAt: null,
    history: [{ status: "Submitted", date: nowISO(), by: student.fullName, remarks: "Application submitted." }],
  };
  store.applications.push(record);
  addNotificationTo(
    store, student.id, record.id, "status",
    `Your ${record.scholarshipType} application (${record.code}) was submitted successfully.`
  );
  store.users
    .filter((u) => u.role === "staff" || u.role === "admin")
    .forEach((u) => {
      addNotificationTo(
        store, u.id, record.id, "admin",
        `New application ${record.code} was submitted by ${record.studentName}.`
      );
    });
  saveStore(store);
  return record;
}

async function updateApplicationStatus(appId, status, remarks, discountPercent) {
  const staff = await getCurrentUser();
  if (!staff || (staff.role !== "staff" && staff.role !== "admin")) {
    throw new Error("Only Authorized Staff or Admin can evaluate applications.");
  }
  const store = loadStore();
  const app = store.applications.find((a) => a.id === appId);
  if (!app) throw new Error("Application not found.");
  if (app.archived) {
    throw new Error(`This application belongs to ${app.term} and can no longer be evaluated. It is kept for records only.`);
  }
  const allowed =
    (app.status === "Submitted" && status === "Under Evaluation") ||
    (app.status === "Under Evaluation" && (status === "Approved" || status === "Rejected"));
  if (!allowed) throw new Error(`An application cannot move from ${app.status} to ${status}.`);
  const note = (remarks || "").trim();
  if (status === "Rejected" && note === "") throw new Error("Remarks are required to reject an application.");
  if (status === "Approved") {
    const discount = String(discountPercent || "").trim();
    if (discount !== "") {
      const discountNumber = Number(discount);
      if (Number.isNaN(discountNumber) || discountNumber < 0 || discountNumber > 100) {
        throw new Error("Discount percentage must be a number between 0 and 100.");
      }
      app.discountPercent = String(discountNumber);
    }
  }
  app.status = status;
  app.remarks = note;
  app.evaluatedBy = staff.fullName;
  app.history.push({ status, date: nowISO(), by: staff.fullName, remarks: note });
  let message = `Your ${app.scholarshipType} application (${app.code})`;
  if (status === "Under Evaluation") {
    message += " moved to Under Evaluation.";
  } else if (status === "Approved") {
    message += " was Approved." + (note ? ` Remarks: ${note}` : "") + " Please proceed to the CSS Office for the next steps.";
  } else {
    message += ` was Rejected. Reason: ${note} You may visit the CSS Office if you need clarification.`;
  }
  addNotificationTo(store, app.studentUserId, app.id, "status", message);
  saveStore(store);
  return app;
}

async function updateApplicationDiscount(appId, discountPercent) {
  const staff = await getCurrentUser();
  if (!staff || (staff.role !== "staff" && staff.role !== "admin")) {
    throw new Error("Only Authorized Staff or Admin can edit the tuition fee discount.");
  }
  const store = loadStore();
  const app = store.applications.find((a) => a.id === appId);
  if (!app) throw new Error("Application not found.");
  if (app.status !== "Approved") {
    throw new Error("Only approved applications have a tuition fee discount to edit.");
  }
  const discount = String(discountPercent || "").trim();
  if (discount !== "") {
    const discountNumber = Number(discount);
    if (Number.isNaN(discountNumber) || discountNumber < 0 || discountNumber > 100) {
      throw new Error("Discount percentage must be a number between 0 and 100.");
    }
    app.discountPercent = String(discountNumber);
  } else {
    app.discountPercent = "";
  }
  saveStore(store);
  return app;
}

async function deleteApplication(appId) {
  const staff = await getCurrentUser();
  if (!staff || (staff.role !== "staff" && staff.role !== "admin")) {
    throw new Error("Only Authorized Staff or Admin can delete applications.");
  }
  const store = loadStore();
  const app = store.applications.find((a) => a.id === appId);
  if (!app) throw new Error("Application not found.");
  app.deleted = true;
  app.deletedAt = nowISO();
  store.notifications = store.notifications.filter((n) => n.appId !== appId);
  saveStore(store);
  return app;
}

function addNotificationTo(store, userId, appId, type, message) {
  store.notifications.push({ id: uid("ntf"), userId, appId, type, message, date: nowISO(), read: false });
}

async function getNotificationsForUser(userId) {
  return loadStore()
    .notifications.filter((n) => n.userId === userId)
    .sort((a, b) => new Date(b.date) - new Date(a.date))
    .slice(0, 100);
}

async function unreadNotificationCount(userId) {
  return loadStore().notifications.filter((n) => n.userId === userId && !n.read).length;
}

async function markNotificationRead(id) {
  const store = loadStore();
  const note = store.notifications.find((n) => n.id === id);
  if (note) {
    note.read = true;
    saveStore(store);
  }
}

async function markAllNotificationsRead(userId) {
  const store = loadStore();
  store.notifications.forEach((n) => {
    if (n.userId === userId) n.read = true;
  });
  saveStore(store);
}