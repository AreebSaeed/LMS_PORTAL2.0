(function () {
  const cfg = window.ANNOUNCEMENT_BELL;
  if (!cfg) return;

  function buildBell(topbar) {
    if (topbar.querySelector('.announcement-bell-wrap')) return;

    const wrap = document.createElement('div');
    wrap.className = 'announcement-bell-wrap';
    wrap.innerHTML = `
      <button type="button" class="announcement-bell-btn" aria-label="Announcements" aria-expanded="false">
        <i class="ti ti-bell"></i>
        <span class="announcement-bell-badge" hidden>0</span>
      </button>
      <div class="announcement-bell-dropdown" hidden>
        <div class="announcement-bell-dropdown-header">
          <span>Announcements</span>
          <button type="button" class="announcement-bell-mark-all" hidden>Mark all read</button>
        </div>
        <div class="announcement-bell-list"></div>
        <a class="announcement-bell-footer" href="${cfg.listUrl}">View all announcements</a>
      </div>
    `;

    const dateEl = topbar.querySelector('.topbar-date');
    let actions = topbar.querySelector('.topbar-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'topbar-actions';
      if (dateEl) {
        topbar.appendChild(actions);
        actions.appendChild(wrap);
        actions.appendChild(dateEl);
      } else {
        topbar.appendChild(actions);
        actions.appendChild(wrap);
      }
    } else {
      actions.insertBefore(wrap, actions.firstChild);
    }

    const btn = wrap.querySelector('.announcement-bell-btn');
    const dropdown = wrap.querySelector('.announcement-bell-dropdown');
    const badge = wrap.querySelector('.announcement-bell-badge');
    const list = wrap.querySelector('.announcement-bell-list');
    const markAllBtn = wrap.querySelector('.announcement-bell-mark-all');

    let open = false;
    let items = [];

    function setBadge(count) {
      if (count > 0) {
        badge.hidden = false;
        badge.textContent = count > 99 ? '99+' : String(count);
      } else {
        badge.hidden = true;
      }
    }

    function renderList() {
      list.innerHTML = '';
      if (!items.length) {
        list.innerHTML = '<div class="announcement-bell-empty">No unread announcements</div>';
        markAllBtn.hidden = true;
        return;
      }
      markAllBtn.hidden = false;
      items.forEach((item) => {
        const el = document.createElement('button');
        el.type = 'button';
        el.className = 'announcement-bell-item';
        el.innerHTML = `
          <div class="announcement-bell-item-title">${escapeHtml(item.title)}</div>
          <div class="announcement-bell-item-body">${escapeHtml(item.body || '')}</div>
          <div class="announcement-bell-item-meta">
            <span class="badge">${escapeHtml(item.label || 'School')}</span>
            <span>${escapeHtml(item.created_at || '')}</span>
          </div>
        `;
        el.addEventListener('click', () => markReadAndGo(item));
        list.appendChild(el);
      });
    }

    function escapeHtml(text) {
      const d = document.createElement('div');
      d.textContent = text;
      return d.innerHTML;
    }

    function readUrl(item) {
      return cfg.readUrlTemplate
        .replace('__TYPE__', encodeURIComponent(item.type))
        .replace('__ID__', encodeURIComponent(item.id));
    }

    async function fetchUnread() {
      try {
        const res = await fetch(cfg.unreadUrl, { credentials: 'same-origin' });
        if (!res.ok) return;
        const data = await res.json();
        items = (data.items || []).slice().sort((a, b) =>
          (b.created_at || '').localeCompare(a.created_at || '')
        );
        setBadge(data.count || 0);
        if (open) renderList();
      } catch (_) { /* ignore */ }
    }

    async function markReadAndGo(item) {
      try {
        await fetch(readUrl(item), { method: 'POST', credentials: 'same-origin' });
      } catch (_) { /* ignore */ }
      window.location.href = cfg.listUrl;
    }

    markAllBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        await fetch(cfg.readAllUrl, { method: 'POST', credentials: 'same-origin' });
      } catch (_) { /* ignore */ }
      items = [];
      setBadge(0);
      renderList();
    });

    function closeDropdown() {
      open = false;
      dropdown.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
    }

    function toggleDropdown() {
      open = !open;
      dropdown.hidden = !open;
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open) {
        fetchUnread().then(renderList);
      }
    }

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleDropdown();
    });

    document.addEventListener('click', (e) => {
      if (!wrap.contains(e.target)) closeDropdown();
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeDropdown();
    });

    fetchUnread();
    setInterval(fetchUnread, 60000);
  }

  document.querySelectorAll('.topbar').forEach(buildBell);
})();
