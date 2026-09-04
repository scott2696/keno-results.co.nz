/* Latest draw panel for the secondary game pages (Lotto/Powerball, Bullseye).
   Reads the same-origin JSON written by tools/fetch_draws.py. */
(function () {
  'use strict';
  var K = window.Keno;
  var host = document.querySelector('[data-game-latest]');
  if (!host || !K) return;

  var game = host.getAttribute('data-game-latest');

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function empty(msg) {
    host.innerHTML = '<div class="empty"><h3>Latest draw unavailable</h3><p>' +
      esc(msg) + '</p></div>';
  }

  fetch('/assets/data/' + game + '-results.json', { cache: 'no-cache' })
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (d) {
      if (!d || !d.numbers || !d.numbers.length) {
        return empty('No confirmed draw is available for this game right now.');
      }

      var meta = document.createElement('div');
      meta.className = 'hero-meta';
      var t = document.createElement('span');
      t.className = 'hero-title';
      t.textContent = 'Latest ' + (d.gameLabel || game) + ' draw';
      var id = document.createElement('span');
      id.className = 'draw-id';
      id.textContent = '#' + d.drawNumber;
      meta.appendChild(t);
      meta.appendChild(id);
      if (d.drawnAt) {
        var when = document.createElement('span');
        when.textContent = K.fmtDate(d.drawnAt) + ', ' + K.fmtTime(d.drawnAt) + ' NZ';
        meta.appendChild(when);
      }

      var ul = document.createElement('ul');
      ul.className = 'balls';
      ul.setAttribute('aria-label', 'Winning numbers, draw ' + d.drawNumber);
      d.numbers.forEach(function (n) {
        var b = K.ball(n);
        /* Bullseye draws one long number rather than a set of balls */
        if (d.singleNumber) {
          b.className = 'ball';
          b.style.width = 'auto';
          b.style.flex = '0 0 auto';
          b.style.borderRadius = 'var(--r-md)';
          b.style.padding = '0 16px';
          b.style.letterSpacing = '.08em';
        }
        ul.appendChild(b);
      });

      host.innerHTML = '';
      host.appendChild(meta);
      host.appendChild(ul);

      if (d.extras && d.extras.length) {
        var ex = document.createElement('div');
        ex.className = 'prov';
        ex.style.borderTop = 'none';
        ex.style.paddingTop = '12px';
        d.extras.forEach(function (e) {
          var s = document.createElement('span');
          s.innerHTML = esc(e.label) + ' <strong>' + esc(e.value) + '</strong>';
          ex.appendChild(s);
        });
        host.appendChild(ex);
      }

      var prov = document.createElement('div');
      prov.className = 'prov';
      var src = d.sourceUrl
        ? '<a href="' + esc(d.sourceUrl) + '" rel="nofollow noopener"><strong>' + esc(d.source) + '</strong></a>'
        : '<strong>' + esc(d.source || 'unknown') + '</strong>';
      prov.innerHTML = '<span class="badge badge-ok">Verified</span><span>Source ' + src + '</span>' +
        (d.retrievedAt ? '<span>Retrieved <span class="mono">' +
          esc(K.fmtDate(d.retrievedAt) + ', ' + K.fmtTime(d.retrievedAt)) + '</span></span>' : '');
      host.appendChild(prov);
    })
    .catch(function () {
      empty('We could not load this game’s feed. Rather than show numbers we cannot verify, we show nothing.');
    });
})();
