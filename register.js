runPage(async () => {
  if (await redirectIfLoggedIn()) return;
  el("regPasswordHint").textContent = PASSWORD_HINT_TEXT;
  el("registerForm").addEventListener("submit", handleRegister);
});

async function handleRegister(e) {
  e.preventDefault();
  clearFieldErrors([
    "regNameError",
    "regStudentIdError",
    "regEmailError",
    "regProgramError",
    "regYearError",
    "regPasswordError",
    "regConfirmError",
  ]);
  hideAlert("registerAlert");
  const fullName = val("regFullName");
  const studentId = val("regStudentId");
  const email = val("regEmail");
  const program = val("regProgram");
  const yearLevel = el("regYearLevel").value;
  const password = el("regPassword").value;
  const confirmPassword = el("regConfirmPassword").value;
  let hasError = false;
  const nameCheck = checkLettersOnly(fullName, "Full name");
  if (!nameCheck.valid) {
    showFieldError("regNameError", nameCheck.message);
    hasError = true;
  }
  const idCheck = checkStudentId(studentId);
  if (!idCheck.valid) {
    showFieldError("regStudentIdError", idCheck.message);
    hasError = true;
  }
  if (!email) {
    showFieldError("regEmailError", "University email is required.");
    hasError = true;
  } else if (!isUniversityEmail(email)) {
    showFieldError("regEmailError", `Only ${UNIVERSITY_EMAIL_DOMAIN} email addresses are accepted.`);
    hasError = true;
  }
  const programCheck = checkLettersOnly(program, "Program/Course");
  if (!programCheck.valid) {
    showFieldError("regProgramError", programCheck.message);
    hasError = true;
  }
  if (!yearLevel) {
    showFieldError("regYearError", "Please select your year level.");
    hasError = true;
  }
  const passwordCheck = validatePassword(password);
  if (!passwordCheck.valid) {
    showFieldError("regPasswordError", passwordCheck.message);
    hasError = true;
  }
  if (password !== confirmPassword) {
    showFieldError("regConfirmError", "Passwords do not match.");
    hasError = true;
  }
  if (hasError) return;
  const button = el("registerForm").querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const result = await signUpStudent({ fullName, studentId, email, password, program, yearLevel });
    if (result.error) {
      showAlert("registerAlert", result.error);
      button.disabled = false;
      return;
    }
    setFlash("Account created! Welcome to the Scholarship Portal.");
    window.location.href = "student-dashboard.html";
  } catch (error) {
    showAlert("registerAlert", friendlyError(error));
    button.disabled = false;
  }
}
