window.TT = window.TT || {};

TT.Grid = {
  filteredSlots: function (app) {
    return app.slots.filter(function (s) {
      if (!app.adminMode && app.selectedClass && s.class_id !== app.selectedClass) return false;
      if (!TT.slotMatchesSearch(s, app.searchQuery)) return false;
      return true;
    });
  },

  columns: function (app) {
    if (TT.isMobile()) return '';
    const dayW = window.innerWidth < 768 ? '64px' : '88px';
    const colW = window.innerWidth < 768 ? 'minmax(72px, 1fr)' : 'minmax(88px, 1fr)';
    return `${dayW} repeat(${app.colCount}, ${colW})`;
  },

  cardHtml: function (slot, canEdit, detailsVisible) {
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
  },

  bindCardClicks: function (app) {
    app.els.body.querySelectorAll('.tt-card-clickable').forEach(function (card) {
      card.addEventListener('click', function (e) {
        e.stopPropagation();
        TT.Modal.open(app, card.dataset.id);
      });
    });
  },

  renderMobileTabs: function (app) {
    if (!app.els.mobileTabs) return;
    const today = TT.todayKey();
    app.els.mobileTabs.innerHTML = TT.DAYS.map(function (day) {
      const isActive = day === app.selectedMobileDay;
      return `<button type="button" class="tt-day-tab${isActive ? ' active' : ''}${day === today ? ' is-today' : ''}" data-day="${day}" role="tab" aria-selected="${isActive}">` +
        `<span class="tt-day-tab-name">${TT.DAY_SHORT[day]}</span></button>`;
    }).join('');

    app.els.mobileTabs.querySelectorAll('.tt-day-tab').forEach(function (btn) {
      btn.addEventListener('click', function () {
        app.selectedMobileDay = btn.dataset.day;
        TT.Grid.render(app);
      });
    });
  },

  renderMobile: function (app) {
    app.root.classList.add('tt-is-mobile');
    if (app.els.timeHeader) app.els.timeHeader.innerHTML = '';
    TT.Grid.renderMobileTabs(app);

    const list = TT.Grid.filteredSlots(app);
    const daySlots = list.filter(function (s) { return s.day_of_week === app.selectedMobileDay; });
    const isToday = app.selectedMobileDay === TT.todayKey();

    let html = `<div class="tt-mobile-day${isToday ? ' is-today' : ''}">`;
    html += `<div class="tt-mobile-day-title">${TT.DAY_LABELS[app.selectedMobileDay]}</div>`;

    if (!app.slots.length) {
      html += `<div class="tt-empty-state"><i class="ti ti-calendar-off"></i><p>No timetable slots yet.${app.canEdit ? ' Tap + to assign a class.' : ''}</p></div>`;
    } else {
      app.timeRanges.forEach(function (range) {
        const slot = daySlots.find(function (s) { return TT.slotInRange(s, range); });
        const current = isToday && TT.isCurrentHourColumn(range);
        html += `<div class="tt-mobile-row${current ? ' is-current-hour' : ''}${slot ? ' has-slot' : ''}">`;
        html += `<div class="tt-mobile-time"><span class="tt-mobile-time-label">${range.label}</span></div>`;
        html += `<div class="tt-mobile-cell">`;
        html += slot ? TT.Grid.cardHtml(slot, app.canEdit, app.detailsVisible) : '<span class="tt-mobile-free">Free period</span>';
        html += `</div></div>`;
      });
    }
    html += '</div>';

    app.els.body.innerHTML = html;
    TT.Grid.bindCardClicks(app);
  },

  renderDesktop: function (app) {
    app.root.classList.remove('tt-is-mobile');
    if (app.els.mobileTabs) app.els.mobileTabs.innerHTML = '';

    const list = TT.Grid.filteredSlots(app);
    const today = TT.todayKey();
    const gridCols = TT.Grid.columns(app);

    let headerHtml = '<div class="tt-corner" role="columnheader"></div>';
    app.timeRanges.forEach(function (r) {
      const current = TT.isCurrentHourColumn(r);
      const label = window.innerWidth < 768
        ? `<span class="tt-time-short">${TT.shortTimeLabel(r)}</span><span class="tt-time-full">${r.label}</span>`
        : r.label;
      headerHtml += `<div class="tt-time-col${current ? ' is-current' : ''}" role="columnheader">${label}</div>`;
    });
    app.els.timeHeader.style.gridTemplateColumns = gridCols;
    app.els.timeHeader.innerHTML = headerHtml;

    let bodyHtml = '';
    TT.DAYS.forEach(function (day) {
      const isToday = day === today;
      const daySlots = list.filter(function (s) { return s.day_of_week === day; });
      const placed = {};
      const dayLabel = window.innerWidth < 768 ? TT.DAY_SHORT[day] : TT.DAY_LABELS[day];

      bodyHtml += `<div class="tt-day-row${isToday ? ' is-today' : ''}" role="row" data-day="${day}" style="grid-template-columns:${gridCols}">`;
      bodyHtml += `<div class="tt-day-label" role="rowheader"><span class="tt-day-name" title="${TT.DAY_LABELS[day]}">${dayLabel}</span></div>`;

      for (let c = 0; c < app.colCount; c++) {
        const range = app.timeRanges[c];
        const slot = daySlots.find(function (s) {
          if (placed[s.id]) return false;
          const p = TT.slotPlacement(s, app.timeRanges);
          return p && p.col === c;
        });

        if (slot) {
          const p = TT.slotPlacement(slot, app.timeRanges);
          placed[slot.id] = true;
          const span = p.span > 1 ? ` style="grid-column: span ${p.span}"` : '';
          bodyHtml += `<div class="tt-cell tt-cell-filled"${span}>${TT.Grid.cardHtml(slot, app.canEdit, app.detailsVisible)}</div>`;
          c += p.span - 1;
        } else {
          const current = isToday && TT.isCurrentHourColumn(range);
          bodyHtml += `<div class="tt-cell${current ? ' is-current-hour' : ''}"></div>`;
        }
      }
      bodyHtml += '</div>';
    });

    if (!app.slots.length) {
      bodyHtml = `<div class="tt-empty-state"><i class="ti ti-calendar-off"></i><p>No timetable slots yet.${app.canEdit ? ' Tap + to assign a class to a teacher.' : ''}</p></div>`;
    }

    app.els.body.innerHTML = bodyHtml;
    TT.Grid.bindCardClicks(app);
  },

  render: function (app) {
    if (TT.isMobile()) TT.Grid.renderMobile(app);
    else TT.Grid.renderDesktop(app);
    if (app.els.scrollHint) {
      app.els.scrollHint.style.display = (!TT.isMobile() && window.innerWidth < 1024) ? 'flex' : 'none';
    }
  },
};
