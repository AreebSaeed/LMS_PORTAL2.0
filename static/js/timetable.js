/**
 * Weekly timetable — fixed 8 AM–2 PM grid; mobile day view + tablet scroll.
 */
(function () {
  'use strict';

  const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
  const DAY_LABELS = {
    monday: 'Monday', tuesday: 'Tuesday', wednesday: 'Wednesday',
    thursday: 'Thursday', friday: 'Friday', saturday: 'Saturday',
  };
  const DAY_SHORT = {
    monday: 'Mon', tuesday: 'Tue', wednesday: 'Wed',
    thursday: 'Thu', friday: 'Fri', saturday: 'Sat',
  };
  const MOBILE_MQ = window.matchMedia('(max-width: 639px)');

  function parseTime(t) {
    if (!t) return 0;
    const p = String(t).split(':');
    return parseInt(p[0], 10) * 60 + parseInt(p[1] || 0, 10);
  }

  function formatNowBadge() {
    const n = new Date();
    let h = n.getHours();
    const m = n.getMinutes();
    const suffix = h < 12 ? 'AM' : 'PM';
    h = h % 12 || 12;
    return m === 0 ? `${h} ${suffix}` : `${h}:${String(m).padStart(2, '0')} ${suffix}`;
  }

  function todayKey() {
    const d = new Date().getDay();
    return DAYS[d === 0 ? 6 : d - 1] || 'monday';
  }

  function todayDateNum() {
    return new Date().getDate();
  }

  function isMobile() {
    return MOBILE_MQ.matches;
  }

  function shortTimeLabel(range) {
    function h12(t) {
      const p = t.split(':');
      const h = parseInt(p[0], 10);
      const suffix = h < 12 ? 'AM' : 'PM';
      return `${h % 12 || 12}${suffix}`;
    }
    return `${h12(range.start)}–${h12(range.end)}`;
  }

  function slotMatchesSearch(slot, q) {
    if (!q) return true;
    const hay = [slot.subject_name, slot.teacher_name, slot.room, slot.class_label].join(' ').toLowerCase();
    return hay.includes(q.toLowerCase());
  }

  function slotPlacement(slot, ranges) {
    const start = parseTime(slot.start_time);
    const end = parseTime(slot.end_time);
    let colStart = -1;
    let colEnd = -1;
    ranges.forEach(function (r, i) {
      const rs = parseTime(r.start);
      const re = parseTime(r.end);
      if (start < re && end > rs) {
        if (colStart === -1) colStart = i;
        colEnd = i;
      }
    });
    if (colStart === -1) return null;
    return { col: colStart, span: colEnd - colStart + 1 };
  }

  function slotInRange(slot, range) {
    const start = parseTime(slot.start_time);
    const end = parseTime(slot.end_time);
    const rs = parseTime(range.start);
    const re = parseTime(range.end);
    return start < re && end > rs;
  }

  function isCurrentHourColumn(range) {
    const nowMins = new Date().getHours() * 60 + new Date().getMinutes();
    return nowMins >= parseTime(range.start) && nowMins < parseTime(range.end);
  }

  function initTimetableApp(root) {
    if (!root) return;

    const slots = JSON.parse(root.dataset.slots || '[]');
    const timeRanges = JSON.parse(root.dataset.timeRanges || '[]');
    const canEdit = root.dataset.canEdit === 'true';
    const adminMode = root.dataset.adminMode === 'true';
    const selectedClassDefault = root.dataset.selectedClass || '';
    const classOptions = JSON.parse(root.dataset.classes || '[]');
    const colors = JSON.parse(root.dataset.colors || '[]');
    const apiAdd = root.dataset.apiAdd || '';
    const apiUpdate = root.dataset.apiUpdate || '';
    const apiDelete = root.dataset.apiDelete || '';

    let selectedClass = adminMode ? selectedClassDefault : '';
    let searchQuery = '';
    let detailsVisible = true;
    let editingId = null;
    let selectedColor = colors[0] ? colors[0].id : 'blue';
    let selectedMobileDay = todayKey();

    const els = {
      schedule: root.querySelector('.tt-schedule'),
      timeHeader: root.querySelector('.tt-time-header'),
      body: root.querySelector('.tt-body'),
      nowLine: root.querySelector('.tt-now-line'),
      legend: root.querySelector('.tt-legend'),
      searchWrap: root.querySelector('.tt-search-wrap'),
      searchInput: root.querySelector('.tt-search-input'),
      modal: root.querySelector('.tt-modal-overlay'),
      form: root.querySelector('.tt-modal-form'),
      mobileTabs: root.querySelector('.tt-mobile-day-tabs'),
      scrollHint: root.querySelector('.tt-scroll-hint'),
      gridWrap: root.querySelector('.tt-grid-wrap'),
    };

    const colCount = timeRanges.length;

    function filteredSlots() {
      return slots.filter(function (s) {
        if (!adminMode && selectedClass && s.class_id !== selectedClass) return false;
        if (!slotMatchesSearch(s, searchQuery)) return false;
        return true;
      });
    }

    function gridColumns() {
      if (isMobile()) return '';
      const dayW = window.innerWidth < 768 ? '64px' : '88px';
      const colW = window.innerWidth < 768 ? 'minmax(72px, 1fr)' : 'minmax(88px, 1fr)';
      return `${dayW} repeat(${colCount}, ${colW})`;
    }

    function renderLegend() {
      if (!els.legend) return;
      const seen = {};
      slots.forEach(function (s) {
        if (!seen[s.subject_name]) seen[s.subject_name] = s.color;
      });
      els.legend.innerHTML = Object.keys(seen).map(function (name) {
        return `<span class="tt-legend-item"><span class="tt-legend-dot" style="background:${seen[name]}"></span>${name}</span>`;
      }).join('');
    }

    function renderCard(slot, compact) {
      const clickable = canEdit ? ' tt-card-clickable' : '';
      const c = compact ? ' compact' : '';
      return `<article class="tt-card${c}${clickable}" data-id="${slot.id || ''}" style="background:${slot.color}" role="gridcell">` +
        `<div class="tt-card-subject">${slot.subject_name}</div>` +
        `<div class="tt-card-teacher">${slot.teacher_name}</div>` +
        `<div class="tt-card-meta">` +
        `<span><i class="ti ti-map-pin"></i>Room ${slot.room || '—'}</span>` +
        `<span class="tt-card-meta-extra"><i class="ti ti-clock"></i>${slot.start_time} – ${slot.end_time}</span>` +
        `<span class="tt-card-meta-extra"><i class="ti ti-school"></i>${slot.class_label}</span>` +
        `</div></article>`;
    }

    function bindCardClicks() {
      els.body.querySelectorAll('.tt-card-clickable').forEach(function (card) {
        card.addEventListener('click', function (e) {
          e.stopPropagation();
          openModal(card.dataset.id);
        });
      });
    }

    function renderMobileDayTabs() {
      if (!els.mobileTabs) return;
      const today = todayKey();
      els.mobileTabs.innerHTML = DAYS.map(function (day) {
        const isToday = day === today;
        const isActive = day === selectedMobileDay;
        return `<button type="button" class="tt-day-tab${isActive ? ' active' : ''}${isToday ? ' is-today' : ''}" data-day="${day}" role="tab" aria-selected="${isActive}">` +
          `<span class="tt-day-tab-name">${DAY_SHORT[day]}</span>` +
          (isToday ? `<span class="tt-day-tab-pill">${todayDateNum()}</span>` : '') +
          `</button>`;
      }).join('');

      els.mobileTabs.querySelectorAll('.tt-day-tab').forEach(function (btn) {
        btn.addEventListener('click', function () {
          selectedMobileDay = btn.dataset.day;
          renderSchedule();
        });
      });
    }

    function renderMobile() {
      root.classList.add('tt-is-mobile');
      if (els.timeHeader) els.timeHeader.innerHTML = '';
      renderMobileDayTabs();

      const list = filteredSlots();
      const daySlots = list.filter(function (s) { return s.day_of_week === selectedMobileDay; });
      const isToday = selectedMobileDay === todayKey();

      let html = `<div class="tt-mobile-day${isToday ? ' is-today' : ''}">`;
      html += `<div class="tt-mobile-day-title">${DAY_LABELS[selectedMobileDay]}`;
      if (isToday) html += ` <span class="tt-day-date-pill">${todayDateNum()}</span>`;
      html += `</div>`;

      if (!slots.length) {
        html += `<div class="tt-empty-state"><i class="ti ti-calendar-off"></i><p>No timetable slots yet.${canEdit ? ' Tap + to assign a class.' : ''}</p></div>`;
      } else {
        timeRanges.forEach(function (range) {
          const slot = daySlots.find(function (s) { return slotInRange(s, range); });
          const current = isToday && isCurrentHourColumn(range);
          html += `<div class="tt-mobile-row${current ? ' is-current-hour' : ''}${slot ? ' has-slot' : ''}">`;
          html += `<div class="tt-mobile-time"><span class="tt-mobile-time-label">${range.label}</span>`;
          if (current) html += `<span class="tt-mobile-now">Now</span>`;
          html += `</div>`;
          html += `<div class="tt-mobile-cell">`;
          if (slot) {
            html += renderCard(slot, !detailsVisible);
          } else {
            html += `<span class="tt-mobile-free">Free period</span>`;
          }
          html += `</div></div>`;
        });
      }
      html += `</div>`;

      els.body.innerHTML = html;
      bindCardClicks();
      if (els.nowLine) els.nowLine.classList.remove('visible');
    }

    function renderDesktopGrid() {
      root.classList.remove('tt-is-mobile');
      if (els.mobileTabs) els.mobileTabs.innerHTML = '';

      const list = filteredSlots();
      const today = todayKey();
      const gridCols = gridColumns();

      let headerHtml = `<div class="tt-corner" role="columnheader"></div>`;
      timeRanges.forEach(function (r) {
        const current = isCurrentHourColumn(r);
        const label = window.innerWidth < 768
          ? `<span class="tt-time-short">${shortTimeLabel(r)}</span><span class="tt-time-full">${r.label}</span>`
          : r.label;
        headerHtml += `<div class="tt-time-col${current ? ' is-current' : ''}" role="columnheader">${label}</div>`;
      });
      els.timeHeader.style.gridTemplateColumns = gridCols;
      els.timeHeader.innerHTML = headerHtml;

      let bodyHtml = '';
      DAYS.forEach(function (day) {
        const isToday = day === today;
        const daySlots = list.filter(function (s) { return s.day_of_week === day; });
        const placed = {};
        const dayLabel = window.innerWidth < 768 ? DAY_SHORT[day] : DAY_LABELS[day];

        bodyHtml += `<div class="tt-day-row${isToday ? ' is-today' : ''}" role="row" data-day="${day}" style="grid-template-columns:${gridCols}">`;
        bodyHtml += `<div class="tt-day-label" role="rowheader">`;
        bodyHtml += `<span class="tt-day-name" title="${DAY_LABELS[day]}">${dayLabel}</span>`;
        if (isToday) {
          bodyHtml += `<span class="tt-day-date-pill">${todayDateNum()}</span>`;
          bodyHtml += `<i class="ti ti-check tt-day-check" aria-hidden="true"></i>`;
        }
        bodyHtml += `</div>`;

        for (let c = 0; c < colCount; c++) {
          const range = timeRanges[c];
          const slot = daySlots.find(function (s) {
            if (placed[s.id]) return false;
            const p = slotPlacement(s, timeRanges);
            return p && p.col === c;
          });

          if (slot) {
            const p = slotPlacement(slot, timeRanges);
            placed[slot.id] = true;
            const span = p.span > 1 ? ` style="grid-column: span ${p.span}"` : '';
            bodyHtml += `<div class="tt-cell tt-cell-filled"${span}>`;
            bodyHtml += renderCard(slot, !detailsVisible);
            bodyHtml += `</div>`;
            c += p.span - 1;
          } else {
            const current = isToday && isCurrentHourColumn(range);
            bodyHtml += `<div class="tt-cell${current ? ' is-current-hour' : ''}"></div>`;
          }
        }
        bodyHtml += `</div>`;
      });

      if (slots.length === 0) {
        bodyHtml = `<div class="tt-empty-state"><i class="ti ti-calendar-off"></i><p>No timetable slots yet.${canEdit ? ' Tap + to assign a class to a teacher.' : ''}</p></div>`;
      }

      els.body.innerHTML = bodyHtml;
      bindCardClicks();
      positionNowLine();
    }

    function renderSchedule() {
      if (isMobile()) renderMobile();
      else renderDesktopGrid();
      updateScrollHint();
    }

    function updateScrollHint() {
      if (!els.scrollHint) return;
      const show = !isMobile() && window.innerWidth < 1024;
      els.scrollHint.style.display = show ? 'flex' : 'none';
    }

    function positionNowLine() {
      if (!els.nowLine || !els.schedule || isMobile()) return;
      const today = todayKey();
      const row = els.body.querySelector(`.tt-day-row[data-day="${today}"]`);
      if (!row) {
        els.nowLine.classList.remove('visible');
        return;
      }

      const nowMins = new Date().getHours() * 60 + new Date().getMinutes();
      const dayStart = parseTime('08:00');
      const dayEnd = parseTime('14:00');

      if (nowMins < dayStart || nowMins >= dayEnd) {
        els.nowLine.classList.remove('visible');
        return;
      }

      const scheduleRect = els.schedule.getBoundingClientRect();
      const rowRect = row.getBoundingClientRect();
      const cells = row.querySelectorAll('.tt-cell');
      if (!cells.length) {
        els.nowLine.classList.remove('visible');
        return;
      }

      const firstCell = cells[0];
      const lastCell = cells[cells.length - 1];
      const trackLeft = firstCell.getBoundingClientRect().left - scheduleRect.left;
      const trackWidth = lastCell.getBoundingClientRect().right - firstCell.getBoundingClientRect().left;
      const pct = (nowMins - dayStart) / (dayEnd - dayStart);
      const left = trackLeft + trackWidth * pct;

      els.nowLine.style.top = `${rowRect.top - scheduleRect.top + rowRect.height / 2}px`;
      els.nowLine.style.left = `${left}px`;
      els.nowLine.innerHTML = `<span class="tt-now-badge">${formatNowBadge()}</span>`;
      els.nowLine.classList.add('visible');
    }

    function openModal(id) {
      if (!canEdit || !els.modal) return;
      editingId = id || null;
      selectedColor = colors[0] ? colors[0].id : 'blue';

      const title = root.querySelector('.tt-modal-title');
      const deleteBtn = root.querySelector('.tt-btn-delete');
      if (title) title.textContent = editingId ? 'Edit Slot' : 'Assign Class Slot';
      if (deleteBtn) deleteBtn.style.display = editingId ? 'block' : 'none';

      const slot = editingId ? slots.find(function (s) { return s.id === editingId; }) : null;
      if (els.form) {
        els.form.teacher_id.value = slot ? (slot.teacher_id || '') : '';
        els.form.subject_id.value = slot ? (slot.subject_id || '') : '';
        els.form.class_id.value = slot ? (slot.class_id || selectedClassDefault) : selectedClassDefault;
        els.form.room.value = slot ? (slot.room || '') : '';
        els.form.day_of_week.value = slot ? slot.day_of_week : (isMobile() ? selectedMobileDay : 'monday');
        els.form.start_time.value = slot ? slot.start_time : '08:00';
        els.form.end_time.value = slot ? slot.end_time : '09:00';
      }

      renderColorSwatches();
      els.modal.classList.add('open');
    }

    function closeModal() {
      if (els.modal) els.modal.classList.remove('open');
      editingId = null;
    }

    function renderColorSwatches() {
      const wrap = root.querySelector('.tt-color-picker');
      if (!wrap) return;
      wrap.innerHTML = colors.map(function (c) {
        return `<button type="button" class="tt-color-swatch${c.id === selectedColor ? ' selected' : ''}" style="background:${c.hex}" data-color="${c.id}" aria-label="${c.label}"></button>`;
      }).join('');
      wrap.querySelectorAll('.tt-color-swatch').forEach(function (sw) {
        sw.addEventListener('click', function () {
          selectedColor = sw.dataset.color;
          renderColorSwatches();
        });
      });
    }

    function submitForm(e) {
      e.preventDefault();
      if (!els.form) return;

      const fd = new FormData(els.form);
      const payload = {
        teacher_id: fd.get('teacher_id'),
        subject_id: fd.get('subject_id'),
        class_id: fd.get('class_id'),
        room: fd.get('room'),
        day_of_week: fd.get('day_of_week'),
        start_time: fd.get('start_time'),
        end_time: fd.get('end_time'),
      };

      if (parseTime(payload.end_time) <= parseTime(payload.start_time)) {
        alert('End time must be after start time.');
        return;
      }

      const url = editingId ? apiUpdate.replace('__ID__', editingId) : apiAdd;
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify(payload),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.success) window.location.reload();
          else alert(data.error || 'Could not save.');
        })
        .catch(function () { alert('Could not save. Try again.'); });
    }

    function deleteSlot() {
      if (!editingId || !apiDelete) return;
      if (!confirm('Remove this slot from the timetable?')) return;
      fetch(apiDelete.replace('__ID__', editingId), {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.success) window.location.reload();
          else alert(data.error || 'Could not delete.');
        });
    }

    let resizeTimer;
    function onResize() {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        renderSchedule();
        positionNowLine();
      }, 150);
    }

    root.querySelector('.tt-menu-btn')?.addEventListener('click', function () {
      document.querySelector('.sidebar-toggle')?.click();
    });

    root.querySelector('.tt-search-btn')?.addEventListener('click', function () {
      els.searchWrap?.classList.toggle('open');
      if (els.searchWrap?.classList.contains('open')) els.searchInput?.focus();
    });

    els.searchInput?.addEventListener('input', function () {
      searchQuery = els.searchInput.value.trim();
      renderSchedule();
    });

    root.querySelector('.tt-add-btn')?.addEventListener('click', function () { openModal(null); });

    root.querySelector('.tt-toggle-details')?.addEventListener('click', function () {
      detailsVisible = !detailsVisible;
      this.classList.toggle('active', detailsVisible);
      renderSchedule();
    });

    const classFilter = root.querySelector('.tt-class-filter');
    if (classFilter) {
      if (classOptions.length <= 1) classFilter.style.display = 'none';
      classFilter.addEventListener('change', function () {
        selectedClass = classFilter.value;
        renderSchedule();
      });
    }

    root.querySelector('.tt-modal-close')?.addEventListener('click', closeModal);
    els.modal?.addEventListener('click', function (e) {
      if (e.target === els.modal) closeModal();
    });
    root.querySelector('.tt-btn-delete')?.addEventListener('click', deleteSlot);
    els.form?.addEventListener('submit', submitForm);

    if (typeof MOBILE_MQ.addEventListener === 'function') {
      MOBILE_MQ.addEventListener('change', onResize);
    } else if (typeof MOBILE_MQ.addListener === 'function') {
      MOBILE_MQ.addListener(onResize);
    }

    renderLegend();
    renderSchedule();
    window.addEventListener('resize', onResize);
    setInterval(positionNowLine, 60000);
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.tt-app').forEach(initTimetableApp);
  });
})();
