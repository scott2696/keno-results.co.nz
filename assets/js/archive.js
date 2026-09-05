/* Draw archive: search by draw ID or date, filter by range, page through.
   Everything runs client-side against the same feed the rest of the site uses. */
(function () {
  'use strict';
  var K = window.Keno;
  var list = document.getElementById('archive-list');
  if (!list || !K) return;

  var q       = document.getElementById('arc-q');
  var from    = document.getElementById('arc-from');
  var to      = document.getElementById('arc-to');
  var clear   = document.getElementById('arc-clear');
  var count   = document.getElementById('arc-count');
  var more    = document.getElementById('arc-more');
  var empty   = document.getElementById('arc-empty');

  var PAGE = 25;
  var all = [], shown = [], limit = PAGE;

  function ymd(iso) { return (iso || '').slice(0, 10); }

  function matches(d) {
    var term = (q && q.value || '').trim().toLowerCase();
    if (term) {
      /* draw id, or any part of the date, or a drawn number */
      var hay = d.id + ' ' + ymd(d.drawnAt) + ' ' + K.fmtDate(d.drawnAt).toLowerCase();
      var asNum = parseInt(term, 10);
      var numHit = !isNaN(asNum) && String(asNum) === term && d.numbers.indexOf(asNum) > -1;
      if (hay.indexOf(term) === -1 && !numHit) return false;
    }
    if (from && from.value && ymd(d.drawnAt) < from.value) return false;
    if (to && to.value && ymd(d.drawnAt) > to.value) return false;
    return true;
  }

  function row(d) {
    var a = document.createElement('a');
    a.className = 'draw-row';
    a.href = '/results/' + ymd(d.drawnAt) + '/' + d.id + '/';

    var top = document.createElement('div');
    top.className = 'draw-row-top';
    var id = document.createElement('span');
    id.className = 'draw-id';
    id.textContent = 'Draw ' + d.id;
    var when = document.createElement('span');
    when.textContent = K.fmtDate(d.drawnAt) + ', ' + K.fmtTime(d.drawnAt);
    top.appendChild(id);
    top.appendChild(when);
    if (d.multiplier) {
      var m = document.createElement('span');
      m.className = 'badge badge-gold';
      m.textContent = '×' + d.multiplier;
      top.appendChild(m);
    }
    a.appendChild(top);

    var ul = document.createElement('ul');
    ul.className = 'balls';
    ul.setAttribute('aria-label', 'Winning numbers, draw ' + d.id);
    d.numbers.forEach(function (n) { ul.appendChild(K.ball(n)); });
    a.appendChild(ul);
    return a;
  }

  function render() {
    shown = all.filter(matches);
    list.innerHTML = '';
    shown.slice(0, limit).forEach(function (d) {
      var li = document.createElement('li');
      li.appendChild(row(d));
      list.appendChild(li);
    });

    if (count) {
      count.textContent = shown.length === all.length
        ? all.length + ' draws'
        : shown.length + ' of ' + all.length + ' draws';
    }
    if (empty) empty.hidden = shown.length !== 0;
    if (more) {
      more.hidden = shown.length <= limit;
      more.textContent = 'Show ' + Math.min(PAGE, shown.length - limit) + ' more';
    }
    if (clear) {
      clear.disabled = !((q && q.value) || (from && from.value) || (to && to.value));
    }
  }

  function reset() { limit = PAGE; render(); }

  [q, from, to].forEach(function (el) {
    if (el) el.addEventListener('input', reset);
  });
  if (clear) {
    clear.addEventListener('click', function () {
      if (q) q.value = ''; if (from) from.value = ''; if (to) to.value = '';
      reset();
      if (q) q.focus();
    });
  }
  if (more) {
    more.addEventListener('click', function () { limit += PAGE; render(); });
  }

  K.load().then(function (data) {
    all = data.draws;
    /* seed the date bounds from the data we actually hold */
    if (all.length) {
      var lo = ymd(all[all.length - 1].drawnAt), hi = ymd(all[0].drawnAt);
      [from, to].forEach(function (el) { if (el) { el.min = lo; el.max = hi; } });
    }
    /* deep link: /results/?draw=27708 */
    var p = new URLSearchParams(window.location.search).get('draw');
    if (p && q) q.value = p;
    render();
  }).catch(function () {
    list.innerHTML = '';
    if (empty) { empty.hidden = false; }
  });
})();
