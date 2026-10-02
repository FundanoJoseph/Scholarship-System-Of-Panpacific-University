let currentUser = null;

runPage(startPage);

async function startPage() {
  currentUser = await requireRole(["admin"]);
  if (!currentUser) return;
  initSidebar(currentUser, "accounts");
  el("newAcctHint").textContent = PASSWORD_HINT_TEXT;
  await showAccounts();
  el("openAddAccountBtn").addEventListener("click", () => {
    el("addAccountForm").reset();
    hideAlert("newAcctAlert");
    clearFieldErrors(["newAcctNameError", "newAcctEmailError", "newAcctPasswordError", "newAcctConfirmError"]);
    openModal("addAccountModal");
  });
  el("addAccountForm").addEventListener("submit", handleCreateAccount);
}

async function showAccounts() {
  const accounts = await allStaffAccounts();
  el("accountRows").innerHTML = accounts
    .map(
      (account) => `
    <tr>
      <td data-label="Full name">${escapeHtml(account.fullName)} ${account.id === currentUser.id ? '<span class="you-badge">You</span>' : ""}</td>
      <td data-label="Email">${escapeHtml(account.email)}</td>
      <td data-label="Role"><span class="badge badge-role-${account.role}">${account.role}</span></td>
      <td data-label="Created">${formatDate(account.createdAt)}</td>
    </tr>`
    )
    .join("");
}

async function handleCreateAccount(e) {
  e.preventDefault();
  clearFieldErrors(["newAcctNameError", "newAcctEmailError", "newAcctPasswordError", "newAcctConfirmError"]);
  hideAlert("newAcctAlert");
  const fullName = val("newAcctName");
  const email = val("newAcctEmail");
  const role = el("newAcctRole").value;
  const password = el("newAcctPassword").value;
  const confirmPassword = el("newAcctConfirm").value;
  let hasError = false;
  const nameCheck = checkLettersOnly(fullName, "Full name");
  if (!nameCheck.valid) {
    showFieldError("newAcctNameError", nameCheck.message);
    hasError = true;
  }
  if (!email) {
    showFieldError("newAcctEmailError", "University email is required.");
    hasError = true;
  } else if (!isUniversityEmail(email)) {
    showFieldError("newAcctEmailError", `Only ${UNIVERSITY_EMAIL_DOMAIN} email addresses are accepted.`);
    hasError = true;
  }
  const passwordCheck = validatePassword(password);
  if (!passwordCheck.valid) {
    showFieldError("newAcctPasswordError", passwordCheck.message);
    hasError = true;
  }
  if (password !== confirmPassword) {
    showFieldError("newAcctConfirmError", "Passwords do not match.");
    hasError = true;
  }
  if (hasError) return;
  const button = el("addAccountForm").querySelector("button[type=submit]");
  button.disabled = true;
  const result = await createStaffAccount({ role, fullName, email, password });
  button.disabled = false;
  if (result.error) {
    showAlert("newAcctAlert", result.error);
    return;
  }
  closeModal("addAccountModal");
  showToast(`${role === "admin" ? "Admin" : "Authorized Staff"} account created for ${fullName}.`);
  await runPage(showAccounts);
}
