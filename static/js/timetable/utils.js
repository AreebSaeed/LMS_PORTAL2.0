window.TT = window.TT || {};

TT.parseTime = function (t) {
  if (!t) return 0;
  const p = String(t).split(':');
  return parseInt(p[0], 10) * 60 + parseInt(p[1] || 0, 10);
};

TT.todayKey = function () {
  const d = new Date().getDay();
  return TT.DAYS[d === 0 ? 6 : d - 1] || 'monday';
};

TT.isMobile = function () {
  return TT.MOBILE_MQ.matches;
};

TT.shortTimeLabel = function (range) {
  function h12(t) {
    const p = t.split(':');
    const h = parseInt(p[0], 10);
    const suffix = h < 12 ? 'AM' : 'PM';
    return `${h % 12 || 12}${suffix}`;
  }
  return `${h12(range.start)}–${h12(range.end)}`;
};

TT.slotMatchesSearch = function (slot, q) {
  if (!q) return true;
  const hay = [slot.subject_name, slot.teacher_name, slot.room, slot.class_label].join(' ').toLowerCase();
  return hay.includes(q.toLowerCase());
};

TT.slotPlacement = function (slot, ranges) {
  const start = TT.parseTime(slot.start_time);
  const end = TT.parseTime(slot.end_time);
  let colStart = -1;
  let colEnd = -1;
  ranges.forEach(function (r, i) {
    const rs = TT.parseTime(r.start);
    const re = TT.parseTime(r.end);
    if (start < re && end > rs) {
      if (colStart === -1) colStart = i;
      colEnd = i;
    }
  });
  if (colStart === -1) return null;
  return { col: colStart, span: colEnd - colStart + 1 };
};

TT.slotInRange = function (slot, range) {
  const start = TT.parseTime(slot.start_time);
  const end = TT.parseTime(slot.end_time);
  const rs = TT.parseTime(range.start);
  const re = TT.parseTime(range.end);
  return start < re && end > rs;
};

TT.isCurrentHourColumn = function (range) {
  const nowMins = new Date().getHours() * 60 + new Date().getMinutes();
  return nowMins >= TT.parseTime(range.start) && nowMins < TT.parseTime(range.end);
};

TT.slotKey = function (s) {
  return (s.day_of_week || '') + '|' + (s.start_time || '') + '|' + (s.end_time || '');
};

TT.slotLabel = function (day, start, end, timeLabel) {
  if (timeLabel) return TT.DAY_LABELS[day].slice(0, 3) + ' ' + timeLabel;
  return TT.DAY_LABELS[day].slice(0, 3) + ' ' + start + '–' + end;
};
