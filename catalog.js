const BENEFIT_TEXT = "Benefits to be confirmed by the CSS Office";
const DEADLINE_TEXT = "To be announced";

const SCHOLARSHIP_CATALOG = [
  {
    key: "Academic Scholarship",
    icon: "ti-school",
    description: "Awarded to students who consistently demonstrate strong academic performance.",
    eligibility: [
      "Currently enrolled Panpacific University student",
      "General weighted average within the academic scholarship bracket",
      "No failing or dropped subjects in the previous term",
    ],
  },
  {
    key: "Entrance Exam Scholarship",
    icon: "ti-clipboard-text",
    description: "Awarded to incoming students based on their performance in the university entrance examination.",
    eligibility: [
      "Qualifying score in the Panpacific University entrance examination",
      "Incoming freshman or transferee student",
      "Complete admission requirements on file",
    ],
  },
  {
    key: "4Ps Scholarship",
    icon: "ti-heart-handshake",
    description: "Support for students from households enrolled in the government's 4Ps program.",
    eligibility: [
      "Household listed under the 4Ps program",
      "Valid 4Ps household ID or certificate",
      "Currently enrolled or incoming Panpacific University student",
    ],
  },
  {
    key: "Urdanetarian Scholarship",
    icon: "ti-building-community",
    description: "For qualified residents of Urdaneta City in recognition of local community ties.",
    eligibility: [
      "Proof of residency in Urdaneta City",
      "Good academic standing",
      "Certificate of residency or barangay clearance",
    ],
  },
  {
    key: "RPSEA Scholarship",
    icon: "ti-award",
    description: "Awarded under the RPSEA scholarship program to qualified applicants.",
    eligibility: [
      "Meets RPSEA program qualification criteria",
      "Complete supporting documentation",
      "Good academic standing",
    ],
  },
  {
    key: "SOC Scholarship",
    icon: "ti-users-group",
    description: "Sponsored scholarship offered under the SOC scholarship program.",
    eligibility: [
      "Meets SOC program qualification criteria",
      "Currently enrolled Panpacific University student",
      "Complete supporting documentation",
    ],
  },
  {
    key: "BSA Scholarship",
    icon: "ti-calculator",
    description: "Awarded to qualified students under the BSA scholarship program.",
    eligibility: [
      "Meets BSA program qualification criteria",
      "Good academic standing",
      "Complete supporting documentation",
    ],
  },
  {
    key: "New Program Scholarship",
    icon: "ti-sparkles",
    description: "Incentive scholarship for students enrolling in newly opened Panpacific University programs.",
    eligibility: [
      "Enrolled in a qualified new academic program",
      "Complete admission requirements",
      "Good academic standing",
    ],
  },
];

const SCHOLARSHIP_REQUIREMENTS = [
  { key: "copyOfGrades", label: "Copy of Grades" },
  { key: "letterOfIntent", label: "Letter of Intent" },
  { key: "notarizedAgreement", label: "Notarized Scholarship Agreement" },
];

const SCHOLARSHIP_AGREEMENT_TEMPLATES = {
  "Academic Scholarship": "assets/documents/academic-entrance-exam-scholarship-agreement.pdf",
  "Entrance Exam Scholarship": "assets/documents/academic-entrance-exam-scholarship-agreement.pdf",
  "4Ps Scholarship": "assets/documents/4ps-urdanetarian-rpsea-soc-bsa-new-program-scholarship-agreement.pdf",
  "Urdanetarian Scholarship": "assets/documents/4ps-urdanetarian-rpsea-soc-bsa-new-program-scholarship-agreement.pdf",
  "RPSEA Scholarship": "assets/documents/4ps-urdanetarian-rpsea-soc-bsa-new-program-scholarship-agreement.pdf",
  "SOC Scholarship": "assets/documents/4ps-urdanetarian-rpsea-soc-bsa-new-program-scholarship-agreement.pdf",
  "BSA Scholarship": "assets/documents/4ps-urdanetarian-rpsea-soc-bsa-new-program-scholarship-agreement.pdf",
  "New Program Scholarship": "assets/documents/4ps-urdanetarian-rpsea-soc-bsa-new-program-scholarship-agreement.pdf",
};

function getScholarshipInfo(key) {
  return SCHOLARSHIP_CATALOG.find((s) => s.key === key) || null;
}

const PROGRAM_COLORS = ["green", "peach", "blue"];

function programCardHtml(scholarship) {
  const color = PROGRAM_COLORS[SCHOLARSHIP_CATALOG.indexOf(scholarship) % PROGRAM_COLORS.length];
  return `
    <article class="card hover-lift program-card">
      <div class="program-card-top">
        <div class="program-icon ${color}"><i class="ti ${scholarship.icon}"></i></div>
        <span class="micro">University program</span>
      </div>
      <h3>${scholarship.key}</h3>
      <p>${scholarship.description}</p>
      <div class="benefit"><i class="ti ti-gift"></i> ${BENEFIT_TEXT}</div>
      <div class="program-bottom">
        <span>Deadline: ${DEADLINE_TEXT}</span>
        <button type="button" class="program-open" data-program="${scholarship.key}" aria-label="View ${scholarship.key}"><i class="ti ti-arrow-up-right"></i></button>
      </div>
    </article>`;
}
