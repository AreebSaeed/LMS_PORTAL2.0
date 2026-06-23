window.TT = window.TT || {};

TT.App = {
  create: function (root) {
    return {
      root: root,
      slots: JSON.parse(root.dataset.slots || '[]'),
      timeRanges: JSON.parse(root.dataset.timeRanges || '[]'),
      canEdit: root.dataset.canEdit === 'true',
      adminMode: root.dataset.adminMode === 'true',
      selectedClassDefault: root.dataset.selectedClass || '',
      classOptions: JSON.parse(root.dataset.classes || '[]'),
      apiAdd: root.dataset.apiAdd || '',
      apiAddBulk: root.dataset.apiAddBulk || '',
      apiUpdate: root.dataset.apiUpdate || '',
      apiDelete: root.dataset.apiDelete || '',
      apiAvailability: root.dataset.apiAvailability || '',
      selectedClass: root.dataset.adminMode === 'true' ? (root.dataset.selectedClass || '') : '',
      searchQuery: '',
      detailsVisible: true,
      editingId: null,
      selectedMobileDay: TT.todayKey(),
      availabilityData: null,
      availabilityTimer: null,
      selectedSlots: [],
      colCount: JSON.parse(root.dataset.timeRanges || '[]').length,
      els: {
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
      },
      resizeTimer: null,
    };
  },

  bindEvents: function (app) {
    app.root.querySelector('.tt-search-btn')?.addEventListener('click', function () {
      app.els.searchWrap?.classList.toggle('open');
      if (app.els.searchWrap?.classList.contains('open')) app.els.searchInput?.focus();
    });

    app.els.searchInput?.addEventListener('input', function () {
      app.searchQuery = app.els.searchInput.value.trim();
      TT.Grid.render(app);
    });

    app.root.querySelector('.tt-add-btn')?.addEventListener('click', function () {
      TT.Modal.open(app, null);
    });

    const classFilter = app.root.querySelector('.tt-class-filter');
    if (classFilter) {
      if (app.classOptions.length <= 1) classFilter.style.display = 'none';
      classFilter.addEventListener('change', function () {
        app.selectedClass = classFilter.value;
        TT.Grid.render(app);
      });
    }

    app.root.querySelector('.tt-modal-close')?.addEventListener('click', function () {
      TT.Modal.close(app);
    });
    app.els.modal?.addEventListener('click', function (e) {
      if (e.target === app.els.modal) TT.Modal.close(app);
    });
    app.root.querySelector('.tt-btn-delete')?.addEventListener('click', function () {
      TT.Modal.delete(app);
    });
    app.els.form?.addEventListener('submit', function (e) { TT.Modal.submit(app, e); });

    if (app.els.form?.teacher_id) {
      app.els.form.teacher_id.addEventListener('change', function () {
        TT.Availability.scheduleLoad(app, true);
      });
    }
    if (app.els.form?.class_id) {
      app.els.form.class_id.addEventListener('change', function () {
        TT.Availability.scheduleLoad(app, true);
      });
    }
    app.els.clearSelection?.addEventListener('click', function () {
      TT.Modal.clearSelected(app);
    });
    if (app.els.form?.day_of_week) {
      app.els.form.day_of_week.addEventListener('change', function () { TT.Availability.renderPanel(app); });
    }
    if (app.els.form?.start_time) {
      app.els.form.start_time.addEventListener('change', function () { TT.Availability.renderPanel(app); });
    }
    if (app.els.form?.end_time) {
      app.els.form.end_time.addEventListener('change', function () { TT.Availability.renderPanel(app); });
    }

    const onResize = function () {
      clearTimeout(app.resizeTimer);
      app.resizeTimer = setTimeout(function () { TT.Grid.render(app); }, 120);
    };

    if (typeof TT.MOBILE_MQ.addEventListener === 'function') {
      TT.MOBILE_MQ.addEventListener('change', onResize);
    } else if (typeof TT.MOBILE_MQ.addListener === 'function') {
      TT.MOBILE_MQ.addListener(onResize);
    }
    window.addEventListener('resize', onResize);
  },

  init: function (root) {
    if (!root) return;
    const app = TT.App.create(root);
    TT.App.bindEvents(app);
    TT.Grid.render(app);
  },

  initAll: function () {
    document.querySelectorAll('.tt-app').forEach(TT.App.init);
  },
};

document.addEventListener('DOMContentLoaded', TT.App.initAll);
