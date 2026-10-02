let currentUser = null;

runPage(startPage);

async function startPage() {
  currentUser = await requireRole();
  if (!currentUser) return;
  initSidebar(currentUser, "notifications");
  await showNotifications();
  el("markAllReadBtn").addEventListener("click", () =>
    runPage(async () => {
      await markAllNotificationsRead(currentUser.id);
      await showNotifications();
      await refreshSidebarNotifCount(currentUser.id, false);
    })
  );
  el("notifList").addEventListener("click", (e) => {
    const button = e.target.closest("[data-mark-read]");
    if (!button) return;
    runPage(async () => {
      await markNotificationRead(button.dataset.markRead);
      await showNotifications();
      await refreshSidebarNotifCount(currentUser.id, false);
    });
  });
  window.addEventListener("notification-arrived", () => runPage(showNotifications));
}

async function showNotifications() {
  const notifications = await getNotificationsForUser(currentUser.id);
  if (!notifications.length) {
    el("notifList").innerHTML = `
      <div class="empty-state">
        <i class="ti ti-bell-off icon"></i>
        <p>No notifications yet.</p>
      </div>`;
    return;
  }
  el("notifList").innerHTML = notifications
    .map(
      (n) => `
    <div class="list-row notif-row ${n.read ? "read" : "unread"}">
      <div class="list-main">
        <div class="list-title"><i class="ti ${n.type === "admin" ? "ti-file-alert" : "ti-bell-ringing"} icon-muted"></i> ${escapeHtml(n.message)}</div>
        <div class="list-meta">${formatDateTime(n.date)}</div>
      </div>
      ${n.read ? "" : `<button type="button" class="btn btn-outline btn-sm" data-mark-read="${n.id}">Mark as read</button>`}
    </div>`
    )
    .join("");
}