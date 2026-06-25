window.TT = window.TT || {};

TT.Modal = {
  open: function (app, id) {
    if (!app.canEdit || !app.els.modal) return;
    app.editingId = id || null;

    const title = app.root.querySelector('.tt-modal-title');
    const deleteBtn = app.root.querySelector('.tt-btn-delete');
    if (title) title.textContent = app.editingId ? 'Edit Slot' : 'Assign Class Slot';
    if (deleteBtn) deleteBtn.style.display = app.editingId ? 'block' : 'none';

    const slot = app.editingId ? app.slots.find(function (s) { return s.id === app.editingId; }) : null;
    app.selectedSlots = [];
    if (app.els.form) {
      if (app.els.form.teacher_id) app.els.form.teacher_id.value = slot ? (slot.teacher_id || '') : '';
      app.els.form.subject_id.value = slot ? (slot.subject_id || '') : '';
      app.els.form.class_id.value = slot ? (slot.class_id || app.selectedClassDefault) : app.selectedClassDefault;
      app.els.form.room.value = slot ? (slot.room || '') : '';
      app.els.form.day_of_week.value = slot ? slot.day_of_week : (TT.isMobile() ? app.selectedMobileDay : 'monday');
      app.els.form.start_time.value = slot ? slot.start_time : '08:00';
      app.els.form.end_time.value = slot ? slot.end_time : '09:00';
    }
    if (slot) {
      app.selectedSlots = [{
        day_of_week: slot.day_of_week,
        start_time: slot.start_time,
        end_time: slot.end_time,
        label: TT.DAY_LABELS[slot.day_of_week] + ' ' + slot.start_time + '–' + slot.end_time,
      }];
    }

    if (app.els.availHint) app.els.availHint.hidden = !!app.editingId;
    TT.Availability.updateSaveButton(app);
    TT.Availability.renderSelected(app);
    app.els.modal.classList.add('open');
    TT.Availability.scheduleLoad(app);
  },

  close: function (app) {
    if (app.els.modal) app.els.modal.classList.remove('open');
    app.editingId = null;
    app.availabilityData = null;
    app.selectedSlots = [];
  },

  toggleSlot: function (app, day, start, end, timeLabel) {
    if (app.editingId) {
      TT.Modal.applySlot(app, day, start, end);
      return;
    }
    const key = TT.slotKey({ day_of_week: day, start_time: start, end_time: end });
    const idx = app.selectedSlots.findIndex(function (s) { return TT.slotKey(s) === key; });
    if (idx >= 0) app.selectedSlots.splice(idx, 1);
    else {
      app.selectedSlots.push({
        day_of_week: day,
        start_time: start,
        end_time: end,
        label: TT.slotLabel(day, start, end, timeLabel),
      });
    }
    if (app.selectedSlots.length) {
      const last = app.selectedSlots[app.selectedSlots.length - 1];
      app.els.form.day_of_week.value = last.day_of_week;
      app.els.form.start_time.value = last.start_time;
      app.els.form.end_time.value = last.end_time;
    }
    TT.Availability.renderPanel(app);
    TT.Availability.renderSelected(app);
    TT.Availability.updateSaveButton(app);
  },

  removeSelected: function (app, key) {
    app.selectedSlots = app.selectedSlots.filter(function (s) { return TT.slotKey(s) !== key; });
    TT.Availability.renderPanel(app);
    TT.Availability.renderSelected(app);
    TT.Availability.updateSaveButton(app);
  },

  clearSelected: function (app) {
    app.selectedSlots = [];
    TT.Availability.renderPanel(app);
    TT.Availability.renderSelected(app);
    TT.Availability.updateSaveButton(app);
  },

  applySlot: function (app, day, start, end) {
    if (!app.els.form) return;
    app.els.form.day_of_week.value = day;
    app.els.form.start_time.value = start;
    app.els.form.end_time.value = end;
    if (app.editingId) {
      app.selectedSlots = [{
        day_of_week: day,
        start_time: start,
        end_time: end,
        label: TT.slotLabel(day, start, end),
      }];
    }
    TT.Availability.renderPanel(app);
    TT.Availability.renderSelected(app);
  },

  submit: function (app, e) {
    e.preventDefault();
    if (!app.els.form) return;

    const fd = new FormData(app.els.form);
    const base = {
      teacher_id: fd.get('teacher_id'),
      subject_id: fd.get('subject_id'),
      class_id: fd.get('class_id'),
      room: fd.get('room'),
    };

    if (app.editingId) {
      const payload = Object.assign({}, base, {
        day_of_week: fd.get('day_of_week'),
        start_time: fd.get('start_time'),
        end_time: fd.get('end_time'),
      });
      if (TT.parseTime(payload.end_time) <= TT.parseTime(payload.start_time)) {
        alert('End time must be after start time.');
        return;
      }
      TT.Api.saveSingle(payload, app.apiUpdate.replace('__ID__', app.editingId), function () {
        TT.Availability.scheduleLoad(app);
      });
      return;
    }

    let slotList = app.selectedSlots.map(function (s) {
      return { day_of_week: s.day_of_week, start_time: s.start_time, end_time: s.end_time };
    });
    if (!slotList.length) {
      slotList = [{
        day_of_week: fd.get('day_of_week'),
        start_time: fd.get('start_time'),
        end_time: fd.get('end_time'),
      }];
    }

    for (let i = 0; i < slotList.length; i++) {
      if (TT.parseTime(slotList[i].end_time) <= TT.parseTime(slotList[i].start_time)) {
        alert('End time must be after start time for all selected slots.');
        return;
      }
    }

    if (slotList.length > 1 && app.apiAddBulk) {
      TT.Api.saveBulk(base, slotList, app.apiAddBulk, function () {
        TT.Availability.scheduleLoad(app);
      });
      return;
    }

    TT.Api.saveSingle(Object.assign({}, base, slotList[0]), app.apiAdd, function () {
      TT.Availability.scheduleLoad(app);
    });
  },

  delete: function (app) {
    if (!app.editingId || !app.apiDelete) return;
    if (!confirm('Remove this slot from the timetable?')) return;
    TT.Api.deleteSlot(app.apiDelete.replace('__ID__', app.editingId));
  },
};
