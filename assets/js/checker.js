/* Ticket checker - the only interactive island on the site. */
(function () {
  'use strict';
  var K = window.Keno;
  var grid = document.getElementById('pick-grid');
  if (!grid || !K) return;

  var input   = document.getElementById('pick-input');
  var countEl = document.getElementById('pick-count');
  var clearBt = document.getElementById('pick-clear');
  var drawSel = document.getElementById('draw-select');
  var out     = document.getElementById('check-result');
  var picks   = [];
  var draws   = [];

  /* ---------- build the 80-grid ---------- */
  for (var n = 1; n <= K.RANGE; n++) {
    var li = document.createElement('li');
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'ball' + K.band(n);
    b.textContent = n;
    b.dataset.n = n;
    b.setAttribute('aria-pressed', 'false');
    b.setAttribute('aria-label', 'Number ' + n);
    li.appendChild(b);
    grid.appendChild(li);
  }

  grid.addEventListener('click', function (ev) {
    var b = ev.target.closest('button.ball');
    if (b) toggle(parseInt(b.dataset.n, 10));
  });

  /* roving arrow-key navigation across the grid */
  grid.addEventListener('keydown', function (ev) {
    var b = ev.target.closest('button.ball');
    if (!b) return;
    var n = parseInt(b.dataset.n, 10), to = null;
    if (ev.key === 'ArrowRight') to = n + 1;
    else if (ev.key === 'ArrowLeft') to = n - 1;
    else if (ev.key === 'ArrowDown') to = n + 10;
    else if (ev.key === 'ArrowUp') to = n - 10;
    else if (ev.key === 'Home') to = 1;
    else if (ev.key === 'End') to = K.RANGE;
    if (to && to >= 1 && to <= K.RANGE) {
      ev.preventDefault();
      var next = grid.querySelector('button[data-n="' + to + '"]');
      if (next) next.focus();
    }
  });

  function toggle(n) {
    var i = picks.indexOf(n);
    if (i > -1) picks.splice(i, 1);
    else if (picks.length < K.MAX_SPOTS) picks.push(n);
    else return;
    picks.sort(function (a, b) { return a - b; });
    save(); sync(); check();
  }

  /* ---------- permissive parsing: "4 9 11", "4,9,11", "4-9-11" all work ---------- */
  function parse(str) {
    var found = String(str).match(/\d+/g) || [];
    var out = [], seen = {};
    for (var i = 0; i < found.length && out.length < K.MAX_SPOTS; i++) {
      var v = parseInt(found[i], 10);
      if (v >= 1 && v <= K.RANGE && !seen[v]) { seen[v] = 1; out.push(v); }
    }
    return out.sort(function (a, b) { return a - b; });
  }

  if (input) {
    input.addEventListener('input', function () {
      picks = parse(input.value);
      save(); syncGrid(); check();
    });
  }
  if (clearBt) {
    clearBt.addEventListener('click', function () {
      picks = []; save(); sync(); check();
      if (input) input.focus();
    });
  }

  function syncGrid() {
    var set = {};
    picks.forEach(function (p) { set[p] = 1; });
    var full = picks.length >= K.MAX_SPOTS;
    grid.querySelectorAll('button.ball').forEach(function (b) {
      var n = parseInt(b.dataset.n, 10), on = !!set[n];
      b.classList.toggle('is-picked', on);
      b.classList.toggle('is-ghost', !on && full);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.disabled = !on && full;
    });
    if (countEl) {
      countEl.textContent = picks.length + ' of ' + K.MAX_SPOTS + ' selected';
      countEl.classList.toggle('over', full);
    }
    if (clearBt) clearBt.disabled = picks.length === 0;
  }
  function sync() {
    if (input) input.value = picks.join(' ');
    syncGrid();
  }

  function save() {
    try { localStorage.setItem('picks', JSON.stringify(picks)); } catch (e) { /* ignore */ }
  }
  function restore() {
    try {
      var v = JSON.parse(localStorage.getItem('picks') || '[]');
      if (Array.isArray(v)) picks = parse(v.join(' '));
    } catch (e) { picks = []; }
  }

  /* ---------- checking ---------- */
  function selectedDraw() {
    if (!draws.length) return null;
    if (!drawSel) return draws[0];
    return draws.find(function (d) { return d.id === drawSel.value; }) || draws[0];
  }

  function check() {
    if (!out) return;
    out.innerHTML = '';
    if (!picks.length) {
      out.hidden = true;
      return;
    }
    out.hidden = false;

    var draw = selectedDraw();
    if (!draw) {
      out.innerHTML = '<div class="result result-n">' +
        '<p class="result-h">No draw to check against</p>' +
        '<p>Your numbers are saved. Once a confirmed draw is published they will be checked automatically.</p></div>';
      return;
    }

    var set = {};
    draw.numbers.forEach(function (n) { set[n] = 1; });
    var hits = picks.filter(function (p) { return set[p]; });

    var wrapEl = document.createElement('div');
    wrapEl.className = 'result ' + (hits.length ? 'result-y' : 'result-n');

    var h = document.createElement('p');
    h.className = 'result-h';
    h.textContent = hits.length + ' of ' + picks.length + ' numbers matched';
    wrapEl.appendChild(h);

    var p = document.createElement('p');
    p.textContent = hits.length
      ? 'Checked against draw ' + draw.id + ', ' + K.fmtDate(draw.drawnAt) +
        '. Confirm any win with Lotto NZ before claiming.'
      : 'No matches in draw ' + draw.id + ', ' + K.fmtDate(draw.drawnAt) + '.';
    wrapEl.appendChild(p);

    var ul = document.createElement('ul');
    ul.className = 'balls';
    ul.style.marginTop = '14px';
    ul.setAttribute('aria-label', 'Your numbers, matched and unmatched');
    picks.forEach(function (n) {
      ul.appendChild(K.ball(n, set[n] ? 'is-hit' : 'is-miss', set[n] ? 'matched' : 'not matched'));
    });
    wrapEl.appendChild(ul);

    out.appendChild(wrapEl);
  }

  /* ---------- init ---------- */
  restore();
  sync();
  check();

  K.load().then(function (data) {
    draws = data.draws;
    if (drawSel && draws.length) {
      drawSel.innerHTML = '';
      draws.slice(0, 200).forEach(function (d) {
        var o = document.createElement('option');
        o.value = d.id;
        o.textContent = 'Draw ' + d.id + ' — ' + K.fmtDate(d.drawnAt) + ', ' + K.fmtTime(d.drawnAt);
        drawSel.appendChild(o);
      });
      drawSel.disabled = false;
      drawSel.addEventListener('change', check);
      var wrapSel = document.getElementById('draw-select-wrap');
      if (wrapSel) wrapSel.hidden = false;
    }
    check();
  }).catch(function () { check(); });
})();
