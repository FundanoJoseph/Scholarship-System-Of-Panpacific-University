let passwordModalUser = null;

function ensureChangePasswordModal() {
  if (el("passwordModal")) return;
  const wrapper = document.createElement("div");
  wrapper.innerHTML = `
    <div class="modal-overlay" id="passwordModal">
      <div class="modal modal-sm">
        <div class="modal-heading">
          <h2><i class="ti ti-key"></i> Change Password</h2>
          <button type="button" class="close" data-close-modal aria-label="Close dialog"><i class="ti ti-x"></i></button>
        </div>

        <form id="changePasswordForm" novalidate>
          <div class="alert alert-error" id="passwordModalAlert"></div>

          <div class="form-group">
            <label for="cpCurrent">Current Password</label>
            <div class="input-wrap"><i class="ti ti-lock"></i><input type="password" id="cpCurrent" autocomplete="current-password" /></div>
            <p class="field-error" id="cpCurrentError"></p>
          </div>

          <div class="form-group">
            <label for="cpNew">New Password</label>
            <div class="input-wrap"><i class="ti ti-lock"></i><input type="password" id="cpNew" autocomplete="new-password" /></div>
            <p class="form-hint">${PASSWORD_HINT_TEXT}</p>
            <p class="field-error" id="cpNewError"></p>
          </div>

          <div class="form-group">
            <label for="cpConfirm">Confirm New Password</label>
            <div class="input-wrap"><i class="ti ti-lock"></i><input type="password" id="cpConfirm" autocomplete="new-password" /></div>
            <p class="field-error" id="cpConfirmError"></p>
          </div>

          <button type="submit" class="btn btn-primary btn-block"><i class="ti ti-device-floppy"></i> Update Password</button>
        </form>
      </div>
    </div>`;
  document.body.appendChild(wrapper.firstElementChild);
  el("changePasswordForm").addEventListener("submit", handleChangePassword);
}

function openChangePasswordModal(user) {
  ensureChangePasswordModal();
  passwordModalUser = user;
  el("changePasswordForm").reset();
  hideAlert("passwordModalAlert");
  clearFieldErrors(["cpCurrentError", "cpNewError", "cpConfirmError"]);
  openModal("passwordModal");
}

async function handleChangePassword(e) {
  e.preventDefault();
  hideAlert("passwordModalAlert");
  clearFieldErrors(["cpCurrentError", "cpNewError", "cpConfirmError"]);
  const currentPassword = el("cpCurrent").value;
  const newPassword = el("cpNew").value;
  const confirmPassword = el("cpConfirm").value;
  let hasError = false;
  if (!currentPassword) {
    showFieldError("cpCurrentError", "Current password is required.");
    hasError = true;
  }
  const passwordCheck = validatePassword(newPassword);
  if (!passwordCheck.valid) {
    showFieldError("cpNewError", passwordCheck.message);
    hasError = true;
  } else if (newPassword === currentPassword) {
    showFieldError("cpNewError", "New password must be different from your current password.");
    hasError = true;
  }
  if (newPassword !== confirmPassword) {
    showFieldError("cpConfirmError", "New password and confirmation do not match.");
    hasError = true;
  }
  if (hasError) return;
  const button = el("changePasswordForm").querySelector("button[type=submit]");
  button.disabled = true;
  const result = await changeOwnPassword(passwordModalUser, currentPassword, newPassword);
  button.disabled = false;
  if (result.error) {
    if (result.error === "Current password is incorrect.") showFieldError("cpCurrentError", result.error);
    else showAlert("passwordModalAlert", result.error);
    return;
  }
  closeModal("passwordModal");
  showToast("Your password has been updated.");
}
