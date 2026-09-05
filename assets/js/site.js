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

  /* ---------- cookie notice ----------
     Informational only: this site sets no cookies, so there is nothing to
     grant or refuse. Dismissal is remembered in the same local storage the
     notice describes, which is the honest place for it. */
  var notice = document.getElementById('cookie-notice');
  if (notice) {
    var SEEN = 'storage-notice-seen';
    var seen = false;
    try { seen = localStorage.getItem(SEEN) === '1'; } catch (e) { seen = false; }

    /* If the welcome offer is about to open, stay down and let it go first -
       it will un-hide this once dismissed. Two overlays at once is clutter. */
    var promoPending = false;
    try {
      promoPending = !!document.getElementById('promo-modal') &&
        localStorage.getItem('promo-seen') !== '1' &&
        !/^\/(responsible-gambling|privacy-policy|cookie-policy|terms|authors)\//
          .test(location.pathname);
    } catch (e) { promoPending = false; }

    if (!seen) {
      notice.hidden = promoPending;
      var dismiss = function () {
        notice.hidden = true;
        try { localStorage.setItem(SEEN, '1'); } catch (e) { /* private mode */ }
      };
      var okBtn = document.getElementById('cookie-ok');
      if (okBtn) okBtn.addEventListener('click', dismiss);
      document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape' && !notice.hidden) dismiss();
      });
    }
  }

  /* ---------- keep the sticky rails clear of the footer ----------
     The rails are position:fixed, so left alone they sit over the footer at
     the bottom of the page. Clamp each one's top so its lower edge never
     passes the footer, and let it ride up as the footer scrolls in. */
  var rails = [].slice.call(document.querySelectorAll('.promo-rail'));
  var footer = document.querySelector('.site-foot');
  if (rails.length && footer) {
    var TOP = 110, GAP = 24, ticking = false;

    var placeRails = function () {
      ticking = false;
      var footerTop = footer.getBoundingClientRect().top;
      rails.forEach(function (rail) {
        if (!rail.firstElementChild) return;               // empty slot
        if (getComputedStyle(rail).display === 'none') return;  // below breakpoint
        var h = rail.offsetHeight;
        var maxTop = footerTop - h - GAP;
        rail.style.top = Math.round(Math.min(TOP, maxTop)) + 'px';
      });
    };

    var onScrollResize = function () {
      if (!ticking) { ticking = true; window.requestAnimationFrame(placeRails); }
    };
    window.addEventListener('scroll', onScrollResize, { passive: true });
    window.addEventListener('resize', onScrollResize);
    /* re-measure once images and fonts have settled */
    window.addEventListener('load', placeRails);
    placeRails();
  }

  /* ---------- condense the masthead on scroll ---------- */
  var head = document.querySelector('.site-head');
  if (head) {
    var stuck = false;
    var onScroll = function () {
      var should = window.scrollY > 12;
      if (should !== stuck) {
        stuck = should;
        head.classList.toggle('is-stuck', stuck);
      }
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
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
  /* One jewel tone per ten: 1-10 -> b1 ... 71-80 -> b8. */
  function band(n) {
    var v = parseInt(n, 10);
    return (v >= 1 && v <= 80) ? ' b' + Math.ceil(v / 10) : '';
  }

  function ball(n, cls, label) {
    var li = document.createElement('li');
    li.className = 'ball' + band(n) + (cls ? ' ' + cls : '');
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
    fmtDate: fmtDate, fmtTime: fmtTime, ball: ball, band: band,
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

  /* ---------- welcome offer ----------
     Shown once ever, and deliberately not everywhere:

     - never on /responsible-gambling/ or the legal pages. Interrupting someone
       reading about gambling harm with a casino bonus is indefensible, and no
       conversion is worth it.
     - never at the same time as the storage notice. Two overlays at once is
       clutter, so the notice waits and appears once this is dismissed.
     - after a short delay, so the page paints first. A modal that beats the
       content to the screen reads as a trap rather than an offer.

     Full dialog behaviour: focus moves in and is trapped, Escape and the
     backdrop close it, and focus returns to wherever it came from.
  */
  (function () {
    var modal = document.getElementById('promo-modal');
    if (!modal) return;

    var BLOCK = /^\/(responsible-gambling|privacy-policy|cookie-policy|terms|authors)\//;
    var SEEN = 'promo-seen';
    var seen = true;
    try { seen = localStorage.getItem(SEEN) === '1'; } catch (e) { seen = true; }
    if (seen || BLOCK.test(location.pathname)) { showNotice(); return; }

    var card = modal.querySelector('.promo-card');
    var opener = null;

    function focusables() { return card.querySelectorAll('a[href],button:not([disabled])'); }

    function onKey(e) {
      if (e.key === 'Escape') { close(); return; }
      if (e.key !== 'Tab') return;
      var f = focusables(); if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }

    function open() {
      opener = document.activeElement;
      modal.hidden = false;
      document.documentElement.style.overflow = 'hidden';
      window.requestAnimationFrame(function () { modal.classList.add('is-in'); });
      var cta = card.querySelector('.promo-cta');
      if (cta) cta.focus({ preventScroll: true });
      document.addEventListener('keydown', onKey);
    }

    function close() {
      try { localStorage.setItem(SEEN, '1'); } catch (e) { /* private mode */ }
      modal.classList.remove('is-in');
      document.removeEventListener('keydown', onKey);
      document.documentElement.style.overflow = '';
      window.setTimeout(function () {
        modal.hidden = true;
        showNotice();
        if (opener && opener.focus && opener !== document.body) opener.focus();
      }, 300);
    }

    function showNotice() {
      var n = document.getElementById('cookie-notice');
      if (!n) return;
      var s = true;
      try { s = localStorage.getItem('storage-notice-seen') === '1'; } catch (e) {}
      if (!s) n.hidden = false;
    }

    Array.prototype.forEach.call(modal.querySelectorAll('[data-promo-close]'),
      function (el) { el.addEventListener('click', close); });

    /* following the offer counts as having answered it */
    var go = modal.querySelector('[data-promo-go]');
    if (go) go.addEventListener('click', function () {
      try { localStorage.setItem(SEEN, '1'); } catch (e) {}
    });

    var timer = window.setTimeout(open, 1400);
    window.addEventListener('pagehide', function () { window.clearTimeout(timer); });
  }());

  /* ---------- bonus box ----------
     Opens the three partner offers from the nav. Same dialog contract as the
     welcome modal: focus in and trapped, Escape and backdrop close, focus
     returned, scroll locked. The attention dot on the trigger stops for good
     once the box has been opened - a badge that never goes away is just noise.
  */
  (function () {
    var box = document.getElementById('bonus-box');
    var btn = document.querySelector('[data-bb-open]');
    if (!box || !btn) return;

    var panel = box.querySelector('.bb-panel');
    var opener = null;
    var SEEN = 'bonusbox-seen';
    try { if (localStorage.getItem(SEEN) === '1') btn.classList.add('is-seen'); } catch (e) {}

    function onKey(e) {
      if (e.key === 'Escape') { close(); return; }
      if (e.key !== 'Tab') return;
      var f = panel.querySelectorAll('a[href],button:not([disabled])');
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    function open() {
      opener = document.activeElement;
      box.hidden = false;
      document.documentElement.style.overflow = 'hidden';
      window.requestAnimationFrame(function () { box.classList.add('is-in'); });
      var x = panel.querySelector('.bb-x');
      if (x) x.focus({ preventScroll: true });
      document.addEventListener('keydown', onKey);
      btn.classList.add('is-seen');
      try { localStorage.setItem(SEEN, '1'); } catch (e) { /* private mode */ }
    }
    function close() {
      box.classList.remove('is-in');
      document.removeEventListener('keydown', onKey);
      document.documentElement.style.overflow = '';
      window.setTimeout(function () {
        box.hidden = true;
        /* after the panel is gone, not before - focusing into a node that is
           still on screen and about to be hidden loses the focus again */
        var back = (opener && opener.focus && opener !== document.body) ? opener : btn;
        if (back && back.focus) back.focus();
      }, 300);
    }

    btn.addEventListener('click', open);
    Array.prototype.forEach.call(box.querySelectorAll('[data-bb-close]'),
      function (el) { el.addEventListener('click', close); });
  }());
})();
