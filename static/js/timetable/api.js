window.TT = window.TT || {};

TT.Api = {
  saveSingle: function (payload, url, onTeacherConflict) {
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
              if (onTeacherConflict) onTeacherConflict();
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
  },

  saveBulk: function (base, slotList, url, onError) {
    fetch(url, {
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
        if (onError) onError();
      })
      .catch(function () { alert('Could not save. Try again.'); });
  },

  deleteSlot: function (url) {
    fetch(url, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) window.location.reload();
        else alert(data.error || 'Could not delete.');
      });
  },

  loadAvailability: function (url) {
    return fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); });
  },
};
