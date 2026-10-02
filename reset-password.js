el("resetForm").addEventListener("submit", (e) => runPage(() => handleReset(e)));
el("resetPasswordHint").textContent = PASSWORD_HINT_TEXT;

async function handleReset(e) {
  e.preventDefault();
  clearFieldErrors(["resetNewError", "resetConfirmError"]);
  hideAlert("resetAlert");
  const newPassword = el("resetNew").value;
  const confirmPassword = el("resetConfirm").value;
  let hasError = false;
  const passwordCheck = validatePassword(newPassword);
  if (!passwordCheck.valid) {
    showFieldError("resetNewError", passwordCheck.message);
    hasError = true;
  }
  if (newPassword !== confirmPassword) {
    showFieldError("resetConfirmError", "Passwords do not match.");
    hasError = true;
  }
  if (hasError) return;
  const button = el("resetForm").querySelector("button[type=submit]");
  button.disabled = true;
  const result = await setNewPassword(newPassword);
  if (result.error) {
    showAlert("resetAlert", result.error);
    button.disabled = false;
    return;
  }
  setFlash("Your password has been updated. Log in with your new password.");
  window.location.href = "index.html";
}