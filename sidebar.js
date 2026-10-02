const STUDENT_NAV = [
  { key: "overview", label: "Dashboard", icon: "ti-layout-dashboard", href: "student-dashboard.html" },
  { key: "scholarships", label: "Scholarships", icon: "ti-award", href: "scholarships.html" },
  { key: "applications", label: "My Applications", icon: "ti-clipboard-list", href: "my-applications.html" },
];

const STAFF_NAV = [
  { key: "overview", label: "Dashboard", icon: "ti-layout-dashboard", href: "staff-dashboard.html" },
  { key: "applications", label: "Applications", icon: "ti-clipboard-list", href: "staff-applications.html" },
  { key: "accounts", label: "Account Management", icon: "ti-users-group", href: "staff-accounts.html", adminOnly: true },
];

function initSidebar(user, activePage) {
  const placeholder = el("sidebar-placeholder");
  if (!placeholder) return;
  const isStudent = user.role === "student";
  const links = (isStudent ? STUDENT_NAV : STAFF_NAV).filter(
    (item) => !item.adminOnly || user.role === "admin"
  );
  const brandTitle = "Scholarship Portal";
  const linksHtml = links
    .map(
      (item) => `
    <a class="sidebar-link ${activePage === item.key ? "active" : ""}" href="${item.href}">
      <i class="ti ${item.icon}"></i><span class="nav-label">${item.label}</span>
    </a>`
    )
    .join("");
  placeholder.innerHTML = `
    <nav class="sidebar" id="sidebar">
      <div class="sidebar-top">
        <a href="${homePageFor(user)}" class="sidebar-brand">
          <div class="sidebar-logo"><img src="assets/images/logo.png" alt="Panpacific University" /></div>
          <div class="sidebar-brand-text">
            <div class="sidebar-brand-title">${brandTitle}</div>
            <div class="sidebar-brand-sub">Panpacific University</div>
          </div>
        </a>
      </div>

      <div class="sidebar-nav">${linksHtml}</div>

      <div class="sidebar-bottom">
        <a class="nav-notif-btn ${activePage === "notifications" ? "active" : ""}" href="notifications.html" title="Notifications">
          <i class="ti ti-bell"></i><span class="nav-label">Notifications</span>
          <span class="notif-count" id="sidebarNotifCount" hidden>0</span>
        </a>

        <div class="nav-user" id="navUser">
          <div class="nav-avatar">${getInitials(user.fullName)}</div>
          <span class="nav-user-name">${escapeHtml(user.fullName.split(" ")[0])}</span>
          <i class="ti ti-chevron-down chevron"></i>
          <div class="nav-dropdown" id="navDropdown">
            <button type="button" id="navChangePasswordBtn"><i class="ti ti-key"></i> Change Password</button>
            <button type="button" class="logout-item" id="navLogoutBtn"><i class="ti ti-logout"></i> Logout</button>
          </div>
        </div>
      </div>
    </nav>

    <div class="sidebar-toggle-bar">
      <div class="brand-mini"><img src="assets/images/logo.png" alt="" /> ${brandTitle}</div>
      <button type="button" class="sidebar-toggle" id="sidebarToggle" aria-label="Toggle sidebar"><i class="ti ti-layout-sidebar-left-collapse"></i></button>
    </div>`;
  document.body.classList.add("has-sidebar");
  wireSidebar(user);
  startNotificationWatcher(user);
}

function wireSidebar(user) {
  const sidebar = el("sidebar");
  el("navUser").addEventListener("click", (e) => {
    el("navDropdown").classList.toggle("show");
    e.stopPropagation();
  });
  document.addEventListener("click", () => el("navDropdown").classList.remove("show"));
  el("navLogoutBtn").addEventListener("click", logout);
  el("navChangePasswordBtn").addEventListener("click", (e) => {
    e.stopPropagation();
    el("navDropdown").classList.remove("show");
    openChangePasswordModal(user);
  });
  el("sidebarToggle").addEventListener("click", () => {
    if (window.innerWidth <= 900) {
      sidebar.classList.add("mobile-open");
    } else {
      sidebar.classList.toggle("collapsed");
      document.body.classList.toggle("sidebar-collapsed");
    }
  });
  let wasSmallScreen = window.innerWidth <= 900;
  window.addEventListener("resize", () => {
    const isSmallScreen = window.innerWidth <= 900;
    if (isSmallScreen !== wasSmallScreen) {
      sidebar.classList.remove("collapsed", "mobile-open");
      document.body.classList.remove("sidebar-collapsed");
      wasSmallScreen = isSmallScreen;
    }
  });
}

const NOTIFICATION_CHECK_MS = window.NOTIFICATION_CHECK_MS || 30000;
let lastUnreadCount = null;

async function refreshSidebarNotifCount(userId, announceNew) {
  const badge = el("sidebarNotifCount");
  if (!badge) return;
  let unread = 0;
  try {
    unread = await unreadNotificationCount(userId);
  } catch (error) {
    if (!pageIsLeaving) console.error("Could not count notifications:", error.message);
    return;
  }
  badge.textContent = unread > 9 ? "9+" : unread;
  badge.hidden = unread === 0;
  if (announceNew && lastUnreadCount !== null && unread > lastUnreadCount) {
    showToast("You have a new notification.");
    window.dispatchEvent(new CustomEvent("notification-arrived"));
  }
  lastUnreadCount = unread;
}

function startNotificationWatcher(user) {
  refreshSidebarNotifCount(user.id, false);
  window.addEventListener("storage", (e) => {
    if (e.key !== DB_KEY) return;
    window.dispatchEvent(new CustomEvent("notification-arrived"));
    refreshSidebarNotifCount(user.id, true);
  });
  setInterval(() => refreshSidebarNotifCount(user.id, true), NOTIFICATION_CHECK_MS);
}