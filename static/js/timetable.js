/**
 * Weekly timetable — fixed 8 AM–2 PM grid.
 * - overlap conflict returns replace prompt
 * - no date/check markers and no moving current-time line
 * - subject-driven colors only (no manual color editing)
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

  function todayKey() {
    const d = new Date().getDay();
    return DAYS[d === 0 ? 6 : d - 1] || 'monday';
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
    const apiAdd = root.dataset.apiAdd || '';
    const apiAddBulk = root.dataset.apiAddBulk || '';
    const apiUpdate = root.dataset.apiUpdate || '';
    const apiDelete = root.dataset.apiDelete || '';
    const apiAvailability = root.dataset.apiAvailability || '';

    let selectedClass = adminMode ? selectedClassDefault : '';
    let searchQuery = '';
    let detailsVisible = true;
    let editingId = null;
    let selectedMobileDay = todayKey();
    let availabilityData = null;
    let availabilityTimer = null;
    let selectedSlots = [];

    const els = {
      timeHeader: root.querySelector('.tt-time-header'),
      body: root.querySelector('.tt-body'),
      searchWrap: root.querySelector('.tt-search-wrap'),
      searchInput: root.querySelector('.tt-search-input'),
      modal: root.querySelector('.tt-modal-overlay'),
      form: root.querySelector('.tt-modal-form'),
      mobileTabs: root.querySelector('.tt-mobile-day-tabs'),
      scrollHint: root.querySelector('.tt-scroll-hint'),
      availPanel: root.querySelector('#tt-availability-panel'),
      availGrid: root.querySelector('#tt-availability-grid'),
      availSummary: root.querySelector('#tt-availability-summary'),
      freeSlotsWrap: root.querySelector('#tt-free-slots-wrap'),
      freeSlots: root.querySelector('#tt-free-slots'),
      selectedWrap: root.querySelector('#tt-selected-slots-wrap'),
      selectedList: root.querySelector('#tt-selected-slots'),
      selectedLabel: root.querySelector('#tt-selected-slots-label'),
      clearSelection: root.querySelector('#tt-clear-selection'),
      availHint: root.querySelector('#tt-avail-hint'),
      saveBtn: root.querySelector('#tt-save-btn'),
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

    function renderCard(slot) {
      const clickable = canEdit ? ' tt-card-clickable' : '';
      const c = detailsVisible ? '' : ' compact';
      const roomPart = slot.room
        ? `<span><i class="ti ti-map-pin"></i>Room ${slot.room}</span>`
        : '';
      return `<article class="tt-card${c}${clickable}" data-id="${slot.id || ''}" style="background:${slot.color}" role="gridcell">` +
        `<div class="tt-card-subject">${slot.subject_name}</div>` +
        `<div class="tt-card-teacher">${slot.teacher_name}</div>` +
        `<div class="tt-card-meta">` +
        roomPart +
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
      html += `<div class="tt-mobile-day-title">${DAY_LABELS[selectedMobileDay]}</div>`;

      if (!slots.length) {
        html += `<div class="tt-empty-state"><i class="ti ti-calendar-off"></i><p>No timetable slots yet.${canEdit ? ' Tap + to assign a class.' : ''}</p></div>`;
      } else {
        timeRanges.forEach(function (range) {
          const slot = daySlots.find(function (s) { return slotInRange(s, range); });
          const current = isToday && isCurrentHourColumn(range);
          html += `<div class="tt-mobile-row${current ? ' is-current-hour' : ''}${slot ? ' has-slot' : ''}">`;
          html += `<div class="tt-mobile-time"><span class="tt-mobile-time-label">${range.label}</span></div>`;
          html += `<div class="tt-mobile-cell">`;
          if (slot) html += renderCard(slot);
          else html += `<span class="tt-mobile-free">Free period</span>`;
          html += `</div></div>`;
        });
      }
      html += `</div>`;

      els.body.innerHTML = html;
      bindCardClicks();
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
            bodyHtml += renderCard(slot);
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

    function openModal(id) {
      if (!canEdit || !els.modal) return;
      editingId = id || null;

      const title = root.querySelector('.tt-modal-title');
      const deleteBtn = root.querySelector('.tt-btn-delete');
      if (title) title.textContent = editingId ? 'Edit Slot' : 'Assign Class Slot';
      if (deleteBtn) deleteBtn.style.display = editingId ? 'block' : 'none';

      const slot = editingId ? slots.find(function (s) { return s.id === editingId; }) : null;
      selectedSlots = [];
      if (els.form) {
        if (els.form.teacher_id) els.form.teacher_id.value = slot ? (slot.teacher_id || '') : '';
        els.form.subject_id.value = slot ? (slot.subject_id || '') : '';
        els.form.class_id.value = slot ? (slot.class_id || selectedClassDefault) : selectedClassDefault;
        els.form.room.value = slot ? (slot.room || '') : '';
        els.form.day_of_week.value = slot ? slot.day_of_week : (isMobile() ? selectedMobileDay : 'monday');
        els.form.start_time.value = slot ? slot.start_time : '08:00';
        els.form.end_time.value = slot ? slot.end_time : '09:00';
      }
      if (slot) {
        selectedSlots = [{
          day_of_week: slot.day_of_week,
          start_time: slot.start_time,
          end_time: slot.end_time,
          label: DAY_LABELS[slot.day_of_week] + ' ' + slot.start_time + '–' + slot.end_time,
        }];
      }

      if (els.availHint) els.availHint.hidden = !!editingId;
      updateSaveButton();
      renderSelectedSlots();

      els.modal.classList.add('open');
      scheduleAvailabilityLoad();
    }

    function closeModal() {
      if (els.modal) els.modal.classList.remove('open');
      editingId = null;
      availabilityData = null;
      selectedSlots = [];
    }

    function slotKey(s) {
      return (s.day_of_week || '') + '|' + (s.start_time || '') + '|' + (s.end_time || '');
    }

    function isSlotSelected(day, start, end) {
      const key = slotKey({ day_of_week: day, start_time: start, end_time: end });
      return selectedSlots.some(function (s) { return slotKey(s) === key; });
    }

    function slotLabel(day, start, end, timeLabel) {
      if (timeLabel) return DAY_LABELS[day].slice(0, 3) + ' ' + timeLabel;
      return DAY_LABELS[day].slice(0, 3) + ' ' + start + '–' + end;
    }

    function toggleSlotSelection(day, start, end, timeLabel) {
      if (editingId) {
        applySlotSelection(day, start, end);
        return;
      }
      const key = slotKey({ day_of_week: day, start_time: start, end_time: end });
      const idx = selectedSlots.findIndex(function (s) { return slotKey(s) === key; });
      if (idx >= 0) {
        selectedSlots.splice(idx, 1);
      } else {
        selectedSlots.push({
          day_of_week: day,
          start_time: start,
          end_time: end,
          label: slotLabel(day, start, end, timeLabel),
        });
      }
      if (selectedSlots.length) {
        const last = selectedSlots[selectedSlots.length - 1];
        els.form.day_of_week.value = last.day_of_week;
        els.form.start_time.value = last.start_time;
        els.form.end_time.value = last.end_time;
      }
      renderAvailabilityPanel();
      renderSelectedSlots();
      updateSaveButton();
    }

    function removeSelectedSlot(key) {
      selectedSlots = selectedSlots.filter(function (s) { return slotKey(s) !== key; });
      renderAvailabilityPanel();
      renderSelectedSlots();
      updateSaveButton();
    }

    function clearSelectedSlots() {
      selectedSlots = [];
      renderAvailabilityPanel();
      renderSelectedSlots();
      updateSaveButton();
    }

    function renderSelectedSlots() {
      if (!els.selectedWrap || !els.selectedList) return;
      if (editingId || !selectedSlots.length) {
        els.selectedWrap.hidden = true;
        els.selectedList.innerHTML = '';
        if (els.selectedLabel) els.selectedLabel.textContent = 'Selected slots';
        return;
      }
      els.selectedWrap.hidden = false;
      if (els.selectedLabel) {
        els.selectedLabel.textContent = 'Selected slots (' + selectedSlots.length + ')';
      }
      els.selectedList.innerHTML = selectedSlots.map(function (s) {
        const key = slotKey(s);
        const label = s.label || slotLabel(s.day_of_week, s.start_time, s.end_time);
        return '<span class="tt-selected-chip">' + label
          + '<button type="button" data-key="' + key + '" aria-label="Remove ' + label + '">&times;</button></span>';
      }).join('');
      els.selectedList.querySelectorAll('button[data-key]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          removeSelectedSlot(btn.dataset.key);
        });
      });
    }

    function updateSaveButton() {
      if (!els.saveBtn) return;
      if (editingId) {
        els.saveBtn.textContent = 'Save Slot';
        return;
      }
      const n = selectedSlots.length;
      if (n > 1) els.saveBtn.textContent = 'Save ' + n + ' Slots';
      else els.saveBtn.textContent = 'Save Slot';
    }

    function currentFormSlot() {
      if (!els.form) return null;
      return {
        day_of_week: els.form.day_of_week.value,
        start_time: els.form.start_time.value,
        end_time: els.form.end_time.value,
      };
    }

    function applySlotSelection(day, start, end) {
      if (!els.form) return;
      els.form.day_of_week.value = day;
      els.form.start_time.value = start;
      els.form.end_time.value = end;
      if (editingId) {
        selectedSlots = [{
          day_of_week: day,
          start_time: start,
          end_time: end,
          label: slotLabel(day, start, end),
        }];
      }
      renderAvailabilityPanel();
      renderSelectedSlots();
    }

    function scheduleAvailabilityLoad(clearSelection) {
      clearTimeout(availabilityTimer);
      if (clearSelection && !editingId) {
        selectedSlots = [];
        renderSelectedSlots();
        updateSaveButton();
      }
      availabilityTimer = setTimeout(loadAvailability, 200);
    }

    function loadAvailability() {
      if (!adminMode || !apiAvailability || !els.availPanel || !els.form) return;
      const teacherId = els.form.teacher_id?.value;
      const classId = els.form.class_id?.value;
      if (!teacherId || !classId) {
        els.availPanel.hidden = true;
        return;
      }

      els.availPanel.hidden = false;
      if (els.availGrid) els.availGrid.innerHTML = '<div class="tt-availability-loading">Loading availability…</div>';
      if (els.availSummary) els.availSummary.textContent = '';

      let url = apiAvailability + '?teacher_id=' + encodeURIComponent(teacherId) + '&class_id=' + encodeURIComponent(classId);
      if (editingId) url += '&exclude_slot_id=' + encodeURIComponent(editingId);

      fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.success) {
            if (els.availGrid) els.availGrid.innerHTML = '<div class="tt-availability-loading">Could not load availability.</div>';
            return;
          }
          availabilityData = data;
          if (!editingId && selectedSlots.length) {
            const freeKeys = {};
            (data.free_slots || []).forEach(function (s) {
              freeKeys[slotKey(s)] = true;
            });
            selectedSlots = selectedSlots.filter(function (s) {
              return freeKeys[slotKey(s)];
            });
          }
          renderAvailabilityPanel();
          renderSelectedSlots();
          updateSaveButton();
        })
        .catch(function () {
          if (els.availGrid) els.availGrid.innerHTML = '<div class="tt-availability-loading">Could not load availability.</div>';
        });
    }

    function cellStatusClass(status) {
      if (status === 'free') return 'is-free';
      if (status === 'class_busy') return 'is-class-busy';
      if (status === 'teacher_busy') return 'is-teacher-busy';
      return 'is-both-busy';
    }

    function renderAvailabilityPanel() {
      if (!availabilityData || !els.availGrid) return;

      const cells = availabilityData.cells || [];
      const ranges = [];
      const days = DAYS.slice();

      cells.forEach(function (c) {
        if (!ranges.find(function (r) { return r.start === c.start_time && r.end === c.end_time; })) {
          ranges.push({ start: c.start_time, end: c.end_time, label: c.time_label });
        }
      });

      let html = '<div class="tt-avail-corner"></div>';
      days.forEach(function (day) {
        const label = DAY_SHORT[day];
        html += '<div class="tt-avail-day-head">' + label + '</div>';
      });

      ranges.forEach(function (range) {
        html += '<div class="tt-avail-time-label">' + shortTimeLabel(range) + '</div>';
        days.forEach(function (day) {
          const cell = cells.find(function (c) {
            return c.day_of_week === day && c.start_time === range.start && c.end_time === range.end;
          });
          if (!cell) {
            html += '<div class="tt-avail-cell"></div>';
            return;
          }
          const cls = cellStatusClass(cell.status);
          const isSelected = isSlotSelected(day, range.start, range.end);
          let title = '';
          if (cell.status === 'teacher_busy') {
            title = 'Teacher busy' + (cell.teacher_class ? ' (' + cell.teacher_class + ')' : '');
          } else if (cell.status === 'class_busy') {
            title = 'Class already has a slot'
              + (cell.class_slot_teacher ? ' (' + cell.class_slot_teacher + ')' : '');
          } else if (cell.status === 'both_busy') {
            title = 'Class busy'
              + (cell.class_slot_teacher ? ' (' + cell.class_slot_teacher + ')' : '')
              + ' · Teacher busy'
              + (cell.teacher_class ? ' (' + cell.teacher_class + ')' : '');
          } else {
            title = editingId
              ? 'Both free — click to select'
              : 'Both free — click to add or remove from selection';
          }
          html += '<div class="tt-avail-cell ' + cls + (isSelected ? ' is-selected' : '') + '"'
            + ' data-day="' + day + '" data-start="' + range.start + '" data-end="' + range.end + '"'
            + ' data-free="' + (cell.status === 'free' ? '1' : '0') + '"'
            + ' title="' + title + '"></div>';
        });
      });

      els.availGrid.innerHTML = html;

      if (els.availSummary) {
        const n = availabilityData.free_count || 0;
        const sel = selectedSlots.length;
        let text = n + ' mutual free slot' + (n === 1 ? '' : 's');
        if (!editingId && sel) text += ' · ' + sel + ' selected';
        els.availSummary.textContent = text;
      }

      els.availGrid.querySelectorAll('.tt-avail-cell.is-free').forEach(function (cell) {
        cell.addEventListener('click', function () {
          toggleSlotSelection(cell.dataset.day, cell.dataset.start, cell.dataset.end, null);
        });
      });

      const freeSlots = availabilityData.free_slots || [];
      if (els.freeSlotsWrap && els.freeSlots) {
        if (freeSlots.length) {
          els.freeSlotsWrap.hidden = false;
          els.freeSlots.innerHTML = freeSlots.map(function (s) {
            const isSel = isSlotSelected(s.day_of_week, s.start_time, s.end_time);
            return '<button type="button" class="tt-free-slot-btn' + (isSel ? ' is-selected' : '') + '"'
              + ' data-day="' + s.day_of_week + '" data-start="' + s.start_time + '" data-end="' + s.end_time + '"'
              + ' data-label="' + (s.label || '').replace(/"/g, '&quot;') + '">'
              + s.label + '</button>';
          }).join('');
          els.freeSlots.querySelectorAll('.tt-free-slot-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
              toggleSlotSelection(btn.dataset.day, btn.dataset.start, btn.dataset.end, btn.dataset.label);
            });
          });
        } else {
          els.freeSlotsWrap.hidden = true;
          els.freeSlots.innerHTML = '';
        }
      }
    }

    function submitForm(e) {
      e.preventDefault();
      if (!els.form) return;

      const fd = new FormData(els.form);
      const base = {
        teacher_id: fd.get('teacher_id'),
        subject_id: fd.get('subject_id'),
        class_id: fd.get('class_id'),
        room: fd.get('room'),
      };

      if (editingId) {
        const payload = Object.assign({}, base, {
          day_of_week: fd.get('day_of_week'),
          start_time: fd.get('start_time'),
          end_time: fd.get('end_time'),
        });
        if (parseTime(payload.end_time) <= parseTime(payload.start_time)) {
          alert('End time must be after start time.');
          return;
        }
        saveSingle(payload, apiUpdate.replace('__ID__', editingId));
        return;
      }

      let slotList = selectedSlots.map(function (s) {
        return {
          day_of_week: s.day_of_week,
          start_time: s.start_time,
          end_time: s.end_time,
        };
      });
      if (!slotList.length) {
        slotList = [{
          day_of_week: fd.get('day_of_week'),
          start_time: fd.get('start_time'),
          end_time: fd.get('end_time'),
        }];
      }

      for (let i = 0; i < slotList.length; i++) {
        if (parseTime(slotList[i].end_time) <= parseTime(slotList[i].start_time)) {
          alert('End time must be after start time for all selected slots.');
          return;
        }
      }

      if (slotList.length > 1 && apiAddBulk) {
        fetch(apiAddBulk, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
          body: JSON.stringify(Object.assign({}, base, { slots: slotList })),
        })
          .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
          .then(function (resp) {
            if (resp.body.success) {
              if (resp.body.failed_count > 0) {
                alert(
                  'Created ' + resp.body.created_count + ' slot(s). '
                  + resp.body.failed_count + ' could not be added.'
                );
              }
              window.location.reload();
              return;
            }
            alert(resp.body.error || 'Could not save slots.');
            scheduleAvailabilityLoad();
          })
          .catch(function () { alert('Could not save. Try again.'); });
        return;
      }

      const payload = Object.assign({}, base, slotList[0]);
      saveSingle(payload, apiAdd);
    }

    function saveSingle(payload, url) {
      function doSave(allowReplace) {
        const sendPayload = Object.assign({}, payload);
        if (allowReplace) sendPayload.allow_replace = true;
        fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
          body: JSON.stringify(sendPayload),
        })
          .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
          .then(function (resp) {
            if (resp.body.success) {
              window.location.reload();
              return;
            }
            if (resp.status === 409 && resp.body.conflict && !allowReplace) {
              if (resp.body.conflict_type === 'teacher') {
                alert(resp.body.error || 'This teacher is already booked at that time.');
                scheduleAvailabilityLoad();
                return;
              }
              const ok = confirm('A timetable event already exists in this time slot for this class. Replace existing event?');
              if (ok) doSave(true);
              return;
            }
            alert(resp.body.error || 'Could not save.');
          })
          .catch(function () { alert('Could not save. Try again.'); });
      }
      doSave(false);
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
      }, 120);
    }

    root.querySelector('.tt-search-btn')?.addEventListener('click', function () {
      els.searchWrap?.classList.toggle('open');
      if (els.searchWrap?.classList.contains('open')) els.searchInput?.focus();
    });

    els.searchInput?.addEventListener('input', function () {
      searchQuery = els.searchInput.value.trim();
      renderSchedule();
    });

    root.querySelector('.tt-add-btn')?.addEventListener('click', function () { openModal(null); });

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

    if (els.form?.teacher_id) {
      els.form.teacher_id.addEventListener('change', function () {
        scheduleAvailabilityLoad(true);
      });
    }
    if (els.form?.class_id) {
      els.form.class_id.addEventListener('change', function () {
        scheduleAvailabilityLoad(true);
      });
    }
    els.clearSelection?.addEventListener('click', clearSelectedSlots);
    if (els.form?.day_of_week) {
      els.form.day_of_week.addEventListener('change', renderAvailabilityPanel);
    }
    if (els.form?.start_time) {
      els.form.start_time.addEventListener('change', renderAvailabilityPanel);
    }
    if (els.form?.end_time) {
      els.form.end_time.addEventListener('change', renderAvailabilityPanel);
    }

    if (typeof MOBILE_MQ.addEventListener === 'function') {
      MOBILE_MQ.addEventListener('change', onResize);
    } else if (typeof MOBILE_MQ.addListener === 'function') {
      MOBILE_MQ.addListener(onResize);
    }

    renderSchedule();
    window.addEventListener('resize', onResize);
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.tt-app').forEach(initTimetableApp);
  });
})();
