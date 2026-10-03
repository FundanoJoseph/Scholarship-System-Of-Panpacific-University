let currentUser = null;
let selectedScholarship = null;
let chosenFiles = {};
let chosenFileObjects = {};

runPage(startPage);

async function startPage() {
  currentUser = await requireRole(["student"]);
  if (!currentUser) return;
  initSidebar(currentUser, "scholarships");
  el("programGrid").innerHTML = SCHOLARSHIP_CATALOG.map(programCardHtml).join("");
  el("programGrid").addEventListener("click", (e) => {
    const button = e.target.closest("[data-program]");
    if (button) openProgramModal(button.dataset.program);
  });
  el("startApplicationBtn").addEventListener("click", openApplyModal);
  el("applyForm").addEventListener("submit", handleApplicationSubmit);
  const requested = getQueryParam("view");
  if (requested && getScholarshipInfo(requested)) openProgramModal(requested);
}

function openProgramModal(key) {
  selectedScholarship = getScholarshipInfo(key);
  if (!selectedScholarship) return;
  const noticeText =
    "Program specific eligibility rules are confirmed by the CSS Office. Authorized Staff review your documents manually, " +
    "the system does not grade you or decide eligibility automatically.";
  el("programModalTitle").textContent = selectedScholarship.key;
  el("programModalBody").innerHTML = `
    <span class="micro">University program</span>
    <p class="modal-text modal-text-spaced">${selectedScholarship.description}</p>

    <dl class="detail-list">
      <dt>Benefit</dt><dd>${BENEFIT_TEXT}</dd>
      <dt>Deadline</dt><dd>${DEADLINE_TEXT}</dd>
    </dl>

    <h3 class="modal-subhead">Eligibility</h3>
    <ul class="bullet-list">${selectedScholarship.eligibility.map((item) => `<li>${item}</li>`).join("")}</ul>

    <h3 class="modal-subhead">Requirements</h3>
    <ul class="bullet-list">${SCHOLARSHIP_REQUIREMENTS.map((item) => `<li>${item.label}</li>`).join("")}</ul>

    <div class="notice notice-spaced">
      <i class="ti ti-info-circle"></i>
      <span>${noticeText}</span>
    </div>`;
  openModal("programModal");
}

function openApplyModal() {
  closeModal("programModal");
  chosenFiles = {};
  chosenFileObjects = {};
  el("applyForm").reset();
  hideAlert("applyAlert");
  clearFieldErrors(["applyProgramError", "applyYearError", "applyDocsError", "applyConsentError"]);
  el("applyScholarshipName").textContent = selectedScholarship.key;
  el("applicantInfo").innerHTML = `
    <dt>Full name</dt><dd>${escapeHtml(currentUser.fullName)}</dd>
    <dt>Student ID</dt><dd>${escapeHtml(currentUser.studentId)}</dd>
    <dt>University email</dt><dd>${escapeHtml(currentUser.email)}</dd>`;
  el("applyProgram").value = currentUser.program || "";
  el("applyYearLevel").value = currentUser.yearLevel || "";
  el("documentRows").innerHTML = SCHOLARSHIP_REQUIREMENTS.map((item) => {
    const templatePath =
      item.key === "notarizedAgreement" ? SCHOLARSHIP_AGREEMENT_TEMPLATES[selectedScholarship.key] : null;
    const templateLink = templatePath
      ? `<a class="text-link template-link" href="${templatePath}" download target="_blank" rel="noopener">
          <i class="ti ti-download"></i> Download template
        </a>`
      : "";
    return `
    <div class="document-row">
      <i class="ti ti-file-text"></i>
      <div class="document-info">
        <strong>${item.label}</strong>
        <small id="fileStatus-${item.key}">No file selected &middot; PDF, JPG or PNG, up to ${MAX_FILE_SIZE_MB} MB</small>
        ${templateLink}
      </div>
      <label class="btn btn-outline btn-sm">Choose file
        <input type="file" data-requirement="${item.key}" accept=".pdf,.jpg,.jpeg,.png" hidden />
      </label>
    </div>`;
  }).join("");
  el("documentRows").querySelectorAll("input[type=file]").forEach((input) => {
    input.addEventListener("change", () => handleFileChosen(input));
  });
  openModal("applyModal");
}

function handleFileChosen(input) {
  const key = input.dataset.requirement;
  const status = el("fileStatus-" + key);
  const file = input.files[0];
  if (!file) return;
  const check = validateFile(file);
  if (!check.valid) {
    status.textContent = check.message;
    status.className = "bad";
    delete chosenFiles[key];
    delete chosenFileObjects[key];
    input.value = "";
    return;
  }
  chosenFiles[key] = { name: file.name, uploadedAt: new Date().toISOString() };
  chosenFileObjects[key] = file;
  status.textContent = file.name + " \u00B7 Selected";
  status.className = "ok";
}

async function handleApplicationSubmit(e) {
  e.preventDefault();
  hideAlert("applyAlert");
  clearFieldErrors(["applyProgramError", "applyYearError", "applyDocsError", "applyConsentError"]);
  const program = val("applyProgram");
  const yearLevel = el("applyYearLevel").value;
  let hasError = false;
  const programCheck = checkLettersOnly(program, "Degree program");
  if (!programCheck.valid) {
    showFieldError("applyProgramError", programCheck.message);
    hasError = true;
  }
  if (!yearLevel) {
    showFieldError("applyYearError", "Please select your year level.");
    hasError = true;
  }
  const missing = SCHOLARSHIP_REQUIREMENTS.filter((item) => !chosenFiles[item.key]);
  if (missing.length) {
    showFieldError("applyDocsError", `Missing required document(s): ${missing.map((item) => item.label).join(", ")}.`);
    hasError = true;
  }
  if (!el("applyConsent").checked) {
    showFieldError("applyConsentError", "Please confirm that your information and documents are correct.");
    hasError = true;
  }
  if (hasError) {
    showAlert("applyAlert", "Please fix the items below before submitting.");
    return;
  }
  const button = el("applyForm").querySelector("button[type=submit]");
  button.disabled = true;
  button.innerHTML = '<i class="ti ti-loader-2"></i> Uploading...';
  try {
    const application = await createApplication(
      {
        program,
        yearLevel,
        scholarshipType: selectedScholarship.key,
      },
      chosenFileObjects
    );
    await updateOwnProfile(currentUser.id, { program, yearLevel });
    setFlash(`Application ${application.code} submitted successfully! Your earlier applications were kept.`);
    window.location.href = "my-applications.html";
  } catch (error) {
    console.error(error);
    showAlert("applyAlert", friendlyError(error));
    button.disabled = false;
    button.innerHTML = '<i class="ti ti-send"></i> Submit application';
  }
}
