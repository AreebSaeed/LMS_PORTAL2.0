window.TT = window.TT || {};

TT.Availability = {
  statusClass: function (status) {
    if (status === 'free') return 'is-free';
    if (status === 'class_busy') return 'is-class-busy';
    if (status === 'teacher_busy') return 'is-teacher-busy';
    return 'is-both-busy';
  },

  isSelected: function (app, day, start, end) {
    const key = TT.slotKey({ day_of_week: day, start_time: start, end_time: end });
    return app.selectedSlots.some(function (s) { return TT.slotKey(s) === key; });
  },

  cellTitle: function (cell, editingId) {
    if (cell.status === 'teacher_busy') {
      return 'Teacher busy' + (cell.teacher_class ? ' (' + cell.teacher_class + ')' : '');
    }
    if (cell.status === 'class_busy') {
      return 'Class already has a slot' + (cell.class_slot_teacher ? ' (' + cell.class_slot_teacher + ')' : '');
    }
    if (cell.status === 'both_busy') {
      return 'Class busy'
        + (cell.class_slot_teacher ? ' (' + cell.class_slot_teacher + ')' : '')
        + ' · Teacher busy'
        + (cell.teacher_class ? ' (' + cell.teacher_class + ')' : '');
    }
    return editingId
      ? 'Both free — click to select'
      : 'Both free — click to add or remove from selection';
  },

  renderSelected: function (app) {
    if (!app.els.selectedWrap || !app.els.selectedList) return;
    if (app.editingId || !app.selectedSlots.length) {
      app.els.selectedWrap.hidden = true;
      app.els.selectedList.innerHTML = '';
      if (app.els.selectedLabel) app.els.selectedLabel.textContent = 'Selected slots';
      return;
    }
    app.els.selectedWrap.hidden = false;
    if (app.els.selectedLabel) {
      app.els.selectedLabel.textContent = 'Selected slots (' + app.selectedSlots.length + ')';
    }
    app.els.selectedList.innerHTML = app.selectedSlots.map(function (s) {
      const key = TT.slotKey(s);
      const label = s.label || TT.slotLabel(s.day_of_week, s.start_time, s.end_time);
      return '<span class="tt-selected-chip">' + label
        + '<button type="button" data-key="' + key + '" aria-label="Remove ' + label + '">&times;</button></span>';
    }).join('');
    app.els.selectedList.querySelectorAll('button[data-key]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        TT.Modal.removeSelected(app, btn.dataset.key);
      });
    });
  },

  updateSaveButton: function (app) {
    if (!app.els.saveBtn) return;
    if (app.editingId) {
      app.els.saveBtn.textContent = 'Save Slot';
      return;
    }
    const n = app.selectedSlots.length;
    app.els.saveBtn.textContent = n > 1 ? ('Save ' + n + ' Slots') : 'Save Slot';
  },

  renderPanel: function (app) {
    if (!app.availabilityData || !app.els.availGrid) return;

    const cells = app.availabilityData.cells || [];
    const ranges = [];
    cells.forEach(function (c) {
      if (!ranges.find(function (r) { return r.start === c.start_time && r.end === c.end_time; })) {
        ranges.push({ start: c.start_time, end: c.end_time, label: c.time_label });
      }
    });

    let html = '<div class="tt-avail-corner"></div>';
    TT.DAYS.forEach(function (day) {
      html += '<div class="tt-avail-day-head">' + TT.DAY_SHORT[day] + '</div>';
    });

    ranges.forEach(function (range) {
      html += '<div class="tt-avail-time-label">' + TT.shortTimeLabel(range) + '</div>';
      TT.DAYS.forEach(function (day) {
        const cell = cells.find(function (c) {
          return c.day_of_week === day && c.start_time === range.start && c.end_time === range.end;
        });
        if (!cell) {
          html += '<div class="tt-avail-cell"></div>';
          return;
        }
        const cls = TT.Availability.statusClass(cell.status);
        const isSelected = TT.Availability.isSelected(app, day, range.start, range.end);
        const title = TT.Availability.cellTitle(cell, app.editingId);
        html += '<div class="tt-avail-cell ' + cls + (isSelected ? ' is-selected' : '') + '"'
          + ' data-day="' + day + '" data-start="' + range.start + '" data-end="' + range.end + '"'
          + ' title="' + title + '"></div>';
      });
    });

    app.els.availGrid.innerHTML = html;

    if (app.els.availSummary) {
      const n = app.availabilityData.free_count || 0;
      const sel = app.selectedSlots.length;
      let text = n + ' mutual free slot' + (n === 1 ? '' : 's');
      if (!app.editingId && sel) text += ' · ' + sel + ' selected';
      app.els.availSummary.textContent = text;
    }

    app.els.availGrid.querySelectorAll('.tt-avail-cell.is-free').forEach(function (cell) {
      cell.addEventListener('click', function () {
        TT.Modal.toggleSlot(app, cell.dataset.day, cell.dataset.start, cell.dataset.end, null);
      });
    });

    const freeSlots = app.availabilityData.free_slots || [];
    if (app.els.freeSlotsWrap && app.els.freeSlots) {
      if (freeSlots.length) {
        app.els.freeSlotsWrap.hidden = false;
        app.els.freeSlots.innerHTML = freeSlots.map(function (s) {
          const isSel = TT.Availability.isSelected(app, s.day_of_week, s.start_time, s.end_time);
          return '<button type="button" class="tt-free-slot-btn' + (isSel ? ' is-selected' : '') + '"'
            + ' data-day="' + s.day_of_week + '" data-start="' + s.start_time + '" data-end="' + s.end_time + '"'
            + ' data-label="' + (s.label || '').replace(/"/g, '&quot;') + '">' + s.label + '</button>';
        }).join('');
        app.els.freeSlots.querySelectorAll('.tt-free-slot-btn').forEach(function (btn) {
          btn.addEventListener('click', function () {
            TT.Modal.toggleSlot(app, btn.dataset.day, btn.dataset.start, btn.dataset.end, btn.dataset.label);
          });
        });
      } else {
        app.els.freeSlotsWrap.hidden = true;
        app.els.freeSlots.innerHTML = '';
      }
    }
  },

  scheduleLoad: function (app, clearSelection) {
    clearTimeout(app.availabilityTimer);
    if (clearSelection && !app.editingId) {
      app.selectedSlots = [];
      TT.Availability.renderSelected(app);
      TT.Availability.updateSaveButton(app);
    }
    app.availabilityTimer = setTimeout(function () { TT.Availability.load(app); }, 200);
  },

  load: function (app) {
    if (!app.adminMode || !app.apiAvailability || !app.els.availPanel || !app.els.form) return;
    const teacherId = app.els.form.teacher_id?.value;
    const classId = app.els.form.class_id?.value;
    if (!teacherId || !classId) {
      app.els.availPanel.hidden = true;
      return;
    }

    app.els.availPanel.hidden = false;
    if (app.els.availGrid) app.els.availGrid.innerHTML = '<div class="tt-availability-loading">Loading availability…</div>';
    if (app.els.availSummary) app.els.availSummary.textContent = '';

    let url = app.apiAvailability + '?teacher_id=' + encodeURIComponent(teacherId) + '&class_id=' + encodeURIComponent(classId);
    if (app.editingId) url += '&exclude_slot_id=' + encodeURIComponent(app.editingId);

    TT.Api.loadAvailability(url)
      .then(function (data) {
        if (!data.success) {
          if (app.els.availGrid) app.els.availGrid.innerHTML = '<div class="tt-availability-loading">Could not load availability.</div>';
          return;
        }
        app.availabilityData = data;
        if (!app.editingId && app.selectedSlots.length) {
          const freeKeys = {};
          (data.free_slots || []).forEach(function (s) { freeKeys[TT.slotKey(s)] = true; });
          app.selectedSlots = app.selectedSlots.filter(function (s) { return freeKeys[TT.slotKey(s)]; });
        }
        TT.Availability.renderPanel(app);
        TT.Availability.renderSelected(app);
        TT.Availability.updateSaveButton(app);
      })
      .catch(function () {
        if (app.els.availGrid) app.els.availGrid.innerHTML = '<div class="tt-availability-loading">Could not load availability.</div>';
      });
  },
};
