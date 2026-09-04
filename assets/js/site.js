/* keno-results.co.nz - shared behaviour.
   No framework, no dependencies. Everything degrades to working HTML. */
(function () {
  'use strict';

  /* ---------- theme ---------- */
  var root = document.documentElement;
  try {
    var saved = localStorage.getItem('theme');
    if (saved === 'dark' || saved === 'light') root.setAttribute('data-theme', saved);
  } catch (e) { /* private mode - fall through to system preference */ }

  function currentTheme() {
    var set = root.getAttribute('data-theme');
    if (set) return set;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  document.addEventListener('click', function (ev) {
    var t = ev.target.closest('[data-theme-toggle]');
    if (!t) return;
    var next = currentTheme() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('theme', next); } catch (e) { /* ignore */ }
    t.setAttribute('aria-label', next === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  });

  /* ---------- mobile nav ---------- */
  var navBtn = document.querySelector('[data-nav-toggle]');
  var nav = document.getElementById('site-nav');
  if (navBtn && nav) {
    navBtn.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      navBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  /* ---------- shared helpers ---------- */
  var NZ = { timeZone: 'Pacific/Auckland' };

  function fmtDate(iso) {
    try {
      return new Date(iso).toLocaleDateString('en-NZ', Object.assign({
        day: 'numeric', month: 'long', year: 'numeric'
      }, NZ));
    } catch (e) { return iso; }
  }
  function fmtTime(iso) {
    try {
      return new Date(iso).toLocaleTimeString('en-NZ', Object.assign({
        hour: 'numeric', minute: '2-digit'
      }, NZ));
    } catch (e) { return ''; }
  }
  function ball(n, cls, label) {
    var li = document.createElement('li');
    li.className = 'ball' + (cls ? ' ' + cls : '');
    li.textContent = n;
    if (label) {
      var s = document.createElement('span');
      s.className = 'vh';
      s.textContent = ', ' + label;
      li.appendChild(s);
    }
    return li;
  }

  window.Keno = {
    fmtDate: fmtDate, fmtTime: fmtTime, ball: ball,
    RANGE: 80, DRAW_SIZE: 20, MIN_SPOTS: 1, MAX_SPOTS: 10,

    /* Never trust the feed. Same rule the ingest validator enforces. */
    validDraw: function (d) {
      if (!d || !Array.isArray(d.numbers)) return false;
      if (d.numbers.length !== this.DRAW_SIZE) return false;
      var seen = {};
      for (var i = 0; i < d.numbers.length; i++) {
        var n = d.numbers[i];
        if (typeof n !== 'number' || n % 1 !== 0) return false;
        if (n < 1 || n > this.RANGE) return false;
        if (seen[n]) return false;
        seen[n] = 1;
      }
      return true;
    },

    load: function () {
      return fetch('/assets/data/draws.json', { cache: 'no-cache' })
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (data) {
          var all = Array.isArray(data.draws) ? data.draws : [];
          var ok = all.filter(function (d) { return window.Keno.validDraw(d); });
          return {
            source: data.source || null,
            sourceUrl: data.sourceUrl || null,
            retrievedAt: data.retrievedAt || null,
            draws: ok.sort(function (a, b) { return new Date(b.drawnAt) - new Date(a.drawnAt); }),
            rejected: all.length - ok.length
          };
        });
    }
  };
})();
