(function () {
  'use strict';

  const SIDEBAR_BREAKPOINT = 1024;

  function updateDateDisplay() {
    const dateEl = document.getElementById('current-date');
    if (!dateEl) return;

    const now = new Date();
    const isCompact = window.innerWidth <= 768;

    dateEl.textContent = now.toLocaleDateString('en-US', isCompact
      ? { month: 'short', day: 'numeric', year: 'numeric' }
      : { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  }

  function isMobileSidebar() {
    return window.innerWidth < SIDEBAR_BREAKPOINT;
  }

  function closeSidebar() {
    document.body.classList.remove('sidebar-open');
    document.body.style.overflow = '';

    const overlay = document.querySelector('.sidebar-overlay');
    const toggle = document.querySelector('.sidebar-toggle');

    if (overlay) overlay.classList.remove('visible');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
  }

  function openSidebar() {
    document.body.classList.add('sidebar-open');
    document.body.style.overflow = 'hidden';

    const overlay = document.querySelector('.sidebar-overlay');
    const toggle = document.querySelector('.sidebar-toggle');

    if (overlay) overlay.classList.add('visible');
    if (toggle) toggle.setAttribute('aria-expanded', 'true');
  }

  function toggleSidebar() {
    if (document.body.classList.contains('sidebar-open')) {
      closeSidebar();
    } else {
      openSidebar();
    }
  }

  function initResponsiveLayout() {
    const layout = document.querySelector('.app-layout');
    if (!layout) return;

    const sidebar = layout.querySelector('.sidebar');
    const main = layout.querySelector('.main-content');
    if (!sidebar || !main) return;

    let overlay = document.querySelector('.sidebar-overlay');
    if (!overlay) {
      overlay = document.createElement('button');
      overlay.type = 'button';
      overlay.className = 'sidebar-overlay';
      overlay.setAttribute('aria-label', 'Close navigation menu');
      layout.insertBefore(overlay, sidebar.nextSibling);
    }

    const topbar = main.querySelector('.topbar');
    if (topbar && !topbar.querySelector('.sidebar-toggle')) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'sidebar-toggle';
      btn.setAttribute('aria-label', 'Toggle navigation menu');
      btn.setAttribute('aria-expanded', 'false');
      btn.innerHTML = '<i class="ti ti-menu-2" aria-hidden="true"></i>';
      topbar.insertBefore(btn, topbar.firstChild);

      btn.addEventListener('click', toggleSidebar);
    }

    overlay.addEventListener('click', closeSidebar);

    sidebar.querySelectorAll('.nav-item, .logout-btn').forEach(function (link) {
      link.addEventListener('click', function () {
        if (isMobileSidebar()) closeSidebar();
      });
    });

    window.addEventListener('resize', function () {
      if (!isMobileSidebar()) closeSidebar();
      updateDateDisplay();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeSidebar();
    });
  }

  function wrapBareTables() {
    document.querySelectorAll('.section-body > table, .card-body > table').forEach(function (table) {
      if (table.parentElement.classList.contains('table-wrap')) return;

      const wrap = document.createElement('div');
      wrap.className = 'table-wrap';
      table.parentElement.insertBefore(wrap, table);
      wrap.appendChild(table);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    updateDateDisplay();
    initResponsiveLayout();
    wrapBareTables();
  });
})();
