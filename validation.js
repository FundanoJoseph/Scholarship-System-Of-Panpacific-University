const UNIVERSITY_EMAIL_DOMAIN = "@panpacificu.edu.ph";

const PASSWORD_MIN_LENGTH = 8;
const PASSWORD_HINT_TEXT =
  "At least 8 characters, with 1 uppercase letter, 1 number, and 1 special character.";

function validatePassword(password) {
  const text = password || "";
  if (text.length < PASSWORD_MIN_LENGTH) {
    return {
      valid: false,
      message: `Password must be at least ${PASSWORD_MIN_LENGTH} characters long.`,
    };
  }
  if (!/[A-Z]/.test(text)) {
    return { valid: false, message: "Password must include at least 1 uppercase letter." };
  }
  if (!/[0-9]/.test(text)) {
    return { valid: false, message: "Password must include at least 1 number." };
  }
  if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?~`]/.test(text)) {
    return { valid: false, message: "Password must include at least 1 special character." };
  }
  return { valid: true, message: "" };
}
function required(value, label) {
  if (value === undefined || value === null || String(value).trim() === "") {
    return { valid: false, message: `${label} is required.` };
  }
  return { valid: true, message: "" };
}
function isUniversityEmail(email) {
  if (!email) return false;
  return email.trim().toLowerCase().endsWith(UNIVERSITY_EMAIL_DOMAIN);
}
const LETTERS_ONLY =
  /^[A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF][A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF .,'&-]*$/;
const STUDENT_ID_LENGTH = 7;
const STUDENT_ID_FORMAT = new RegExp(`^[0-9]{${STUDENT_ID_LENGTH}}$`);
function checkLettersOnly(value, label) {
  const empty = required(value, label);
  if (!empty.valid) return empty;
  if (!LETTERS_ONLY.test(value.trim())) {
    return { valid: false, message: `${label} must contain letters only. Numbers are not allowed.` };
  }
  return { valid: true, message: "" };
}
function checkStudentId(value) {
  const empty = required(value, "Student ID");
  if (!empty.valid) return empty;
  const text = value.trim();
  if (!/^[0-9]*$/.test(text)) {
    return {
      valid: false,
      message: `Student ID must contain numbers only (example: 0000000). Letters, spaces and symbols are not allowed.`,
    };
  }
  if (!STUDENT_ID_FORMAT.test(text)) {
    return {
      valid: false,
      message: `Student ID must be exactly ${STUDENT_ID_LENGTH} digits (example: 0000000). You entered ${text.length}.`,
    };
  }
  return { valid: true, message: "" };
}
const ACADEMIC_YEAR_FORMAT = /^(\d{4})\s*[-\/]\s*(\d{4})$/;
function normalizeAcademicYear(value) {
  const match = ACADEMIC_YEAR_FORMAT.exec(String(value || "").trim());
  if (!match) return String(value || "").trim();
  return `${match[1]}\u2013${match[2]}`;
}
function checkAcademicYear(value) {
  const empty = required(value, "Academic year");
  if (!empty.valid) return empty;
  const text = String(value).trim();
  const match = ACADEMIC_YEAR_FORMAT.exec(text);
  if (!match) {
    return { valid: false, message: "Academic year must be two years like 2026-2027." };
  }
  const start = Number(match[1]);
  const end = Number(match[2]);
  if (end !== start + 1) {
    return {
      valid: false,
      message: `The second year must follow the first (you typed ${start}-${end}; did you mean ${start}-${start + 1}?).`,
    };
  }
  if (start < 2000 || start > 2100) {
    return { valid: false, message: "Please type a realistic academic year (between 2000 and 2100)." };
  }
  return { valid: true, message: "" };
}
const MAX_FILE_SIZE_MB = 5;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const ACCEPTED_FILE_TYPES = [".pdf", ".jpg", ".jpeg", ".png"];
function validateFile(file) {
  if (!file) return { valid: false, message: "No file selected." };
  const lowerName = file.name.toLowerCase();
  const typeOk = ACCEPTED_FILE_TYPES.some((ext) => lowerName.endsWith(ext));
  if (!typeOk) {
    return {
      valid: false,
      message: `Unsupported file type. Accepted: ${ACCEPTED_FILE_TYPES.join(", ")}`,
    };
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return { valid: false, message: `File is too large. Maximum size is ${MAX_FILE_SIZE_MB}MB.` };
  }
  return { valid: true, message: "" };
}
function showFieldError(id, message) {
  const box = document.getElementById(id);
  if (!box) return;
  box.textContent = message;
  box.classList.add("show");
}
function clearFieldError(id) {
  const box = document.getElementById(id);
  if (!box) return;
  box.textContent = "";
  box.classList.remove("show");
}
function clearFieldErrors(ids) {
  ids.forEach(clearFieldError);
}