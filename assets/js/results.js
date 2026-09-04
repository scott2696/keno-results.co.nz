/* Renders latest draw, archive list and frequency stats from the draw feed.
   Every surface has an honest empty state - we never invent numbers. */
(function () {
  'use strict';
  var K = window.Keno;
  if (!K) return;

  var heroEl  = document.getElementById('latest-draw');
  var hcHost  = document.getElementById('hotcold');
  var recent  = document.getElementById('recent-draws');
  var archive = document.getElementById('archive-list');
  var freqEl  = document.getElementById('freq-list');
  if (!heroEl && !recent && !archive && !freqEl && !hcHost) return;

  function emptyBlock(title, body) {
    var d = document.createElement('div');
    d.className = 'empty';
    var h = document.createElement('h3'); h.textContent = title;
    var p = document.createElement('p'); p.textContent = body;
    d.appendChild(h); d.appendChild(p);
    return d;
  }

  function ballList(nums, label, reveal) {
    var ul = document.createElement('ul');
    ul.className = 'balls';
    ul.setAttribute('aria-label', label);
    nums.forEach(function (n, i) {
      var b = K.ball(n);
      if (reveal) {
        b.classList.add('reveal');
        b.style.animationDelay = (i * 20) + 'ms';
      }
      ul.appendChild(b);
    });
    return ul;
  }

  function drawRow(d) {
    var a = document.createElement('a');
    a.className = 'draw-row';
    a.href = '/check/?draw=' + encodeURIComponent(d.id);

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
      m.className = 'badge badge-neutral';
      m.textContent = 'x' + d.multiplier;
      top.appendChild(m);
    }
    a.appendChild(top);
    a.appendChild(ballList(d.numbers, 'Winning numbers, draw ' + d.id));
    return a;
  }

  function renderHero(data) {
    if (!heroEl) return;
    heroEl.innerHTML = '';
    var d = data.draws[0];

    if (!d) {
      heroEl.appendChild(emptyBlock(
        'No confirmed draw yet',
        'This site is not currently connected to a results feed, so there is nothing to show. ' +
        'We publish numbers only when they come from a verified source - never placeholders.'
      ));
      return;
    }

    var meta = document.createElement('div');
    meta.className = 'hero-meta';
    var t = document.createElement('span');
    t.className = 'hero-title';
    t.textContent = 'Latest draw';
    var id = document.createElement('span');
    id.className = 'draw-id';
    id.textContent = '#' + d.id;
    var when = document.createElement('span');
    when.textContent = K.fmtDate(d.drawnAt) + ', ' + K.fmtTime(d.drawnAt) + ' NZ';
    meta.appendChild(t); meta.appendChild(id); meta.appendChild(when);
    if (d.multiplier) {
      var m = document.createElement('span');
      m.className = 'badge badge-neutral';
      m.textContent = 'Multiplier x' + d.multiplier;
      meta.appendChild(m);
    }
    heroEl.appendChild(meta);

    heroEl.appendChild(ballList(d.numbers, 'Winning numbers, draw ' + d.id, true));

    var prov = document.createElement('div');
    prov.className = 'prov';
    var bits = [];
    if (data.source) {
      bits.push(data.sourceUrl
        ? 'Source <a href="' + esc(data.sourceUrl) + '" rel="nofollow noopener"><strong>' + esc(data.source) + '</strong></a>'
        : 'Source <strong>' + esc(data.source) + '</strong>');
    }
    if (data.retrievedAt) {
      bits.push('Retrieved <span class="mono">' + esc(K.fmtDate(data.retrievedAt) + ', ' + K.fmtTime(data.retrievedAt)) + '</span>');
    }
    bits.push('<a href="/about/#corrections">Report an error</a>');
    prov.innerHTML = '<span class="badge badge-ok">Verified</span>' +
      bits.map(function (b) { return '<span>' + b + '</span>'; }).join('');
    heroEl.appendChild(prov);
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function renderList(el, list, emptyTitle, emptyBody) {
    if (!el) return;
    el.innerHTML = '';
    if (!list.length) {
      el.appendChild(emptyBlock(emptyTitle, emptyBody));
      return;
    }
    list.forEach(function (d) {
      var li = document.createElement('li');
      li.appendChild(drawRow(d));
      el.appendChild(li);
    });
  }

  function renderFreq(draws) {
    if (!freqEl) return;
    freqEl.innerHTML = '';
    if (!draws.length) {
      freqEl.appendChild(emptyBlock(
        'No draw history yet',
        'Frequency counts appear here once confirmed draws have been published.'
      ));
      return;
    }
    var counts = new Array(K.RANGE + 1).fill(0);
    draws.forEach(function (d) {
      d.numbers.forEach(function (n) { counts[n]++; });
    });
    var max = Math.max.apply(null, counts.slice(1)) || 1;

    /* Ordered by number, never by frequency - a ranked list would read as
       a prediction, which it is not. See the caveat on the page. */
    for (var n = 1; n <= K.RANGE; n++) {
      var li = document.createElement('li');
      var a = document.createElement('span'); a.className = 'n'; a.textContent = n;
      var bar = document.createElement('span'); bar.className = 'bar';
      var i = document.createElement('i'); i.style.width = ((counts[n] / max) * 100) + '%';
      bar.appendChild(i);
      var c = document.createElement('span'); c.className = 'c'; c.textContent = counts[n];
      li.appendChild(a); li.appendChild(bar); li.appendChild(c);
      li.setAttribute('aria-label', 'Number ' + n + ' drawn ' + counts[n] + ' times');
      freqEl.appendChild(li);
    }
    var tot = document.getElementById('freq-total');
    if (tot) tot.textContent = draws.length;
    var sel = document.getElementById('hc-window');
    if (sel) {
      /* drop window sizes we do not have the history for */
      Array.prototype.slice.call(sel.options).forEach(function (o) {
        var v = parseInt(o.value, 10);
        if (v > draws.length) o.disabled = true;
      });
    }
  }


  /* ---------- hot / cold over the last N draws ---------- */
  var hcEl = document.getElementById('hotcold');
  var hcSel = document.getElementById('hc-window');
  var allDraws = [];

  function renderHotCold() {
    if (!hcEl) return;
    var want = hcSel ? parseInt(hcSel.value, 10) : 25;
    var win = allDraws.slice(0, want);

    if (!win.length) {
      hcEl.innerHTML = '';
      hcEl.appendChild(emptyBlock('No draw history yet',
        'Hot and cold numbers appear once confirmed draws have been published.'));
      return;
    }

    var counts = new Array(K.RANGE + 1).fill(0);
    win.forEach(function (d) {
      d.numbers.forEach(function (n) { counts[n]++; });
    });

    /* Rank by appearance rate. Ties break on the lower number so the list is
       stable between renders rather than reshuffling on identical counts. */
    var ranked = [];
    for (var n = 1; n <= K.RANGE; n++) ranked.push({ n: n, c: counts[n] });
    ranked.sort(function (a, b) { return b.c - a.c || a.n - b.n; });

    var hot = ranked.slice(0, 5);
    var cold = ranked.slice(-5).sort(function (a, b) { return a.c - b.c || a.n - b.n; });

    function column(title, items, kind) {
      var wrapEl = document.createElement('div');
      wrapEl.className = 'hc-' + kind;
      var h = document.createElement('p');
      h.className = 'hc-h';
      h.innerHTML = '<span class="dot"></span>' + title;
      wrapEl.appendChild(h);
      var ul = document.createElement('ul');
      ul.className = 'hc-list';
      ul.setAttribute('aria-label', title + ' numbers over the last ' + win.length + ' draws');
      items.forEach(function (it) {
        var li = document.createElement('li');
        li.className = 'hc-item';
        var b = K.ball(it.n);
        var pct = Math.round((it.c / win.length) * 100);
        var r = document.createElement('span');
        r.className = 'rate';
        r.textContent = pct + '%';
        li.appendChild(b);
        li.appendChild(r);
        li.setAttribute('aria-label',
          'Number ' + it.n + ' appeared in ' + it.c + ' of ' + win.length + ' draws, ' + pct + ' percent');
        ul.appendChild(li);
      });
      wrapEl.appendChild(ul);
      return wrapEl;
    }

    var grid = document.createElement('div');
    grid.className = 'hc';
    grid.appendChild(column('Most drawn', hot, 'hot'));
    grid.appendChild(column('Least drawn', cold, 'cold'));

    var base = document.createElement('p');
    base.className = 'hc-base';
    base.textContent = 'Share of the last ' + win.length + ' draws each number appeared in. ' +
      'Because 20 of 80 numbers are drawn each time, every number averages 25% over the long run.';

    hcEl.innerHTML = '';
    hcEl.appendChild(grid);
    hcEl.appendChild(base);
  }

  if (hcSel) hcSel.addEventListener('change', renderHotCold);

  K.load().then(function (data) {
    allDraws = data.draws;
    renderHotCold();
    renderHero(data);
    renderList(recent, data.draws.slice(1, 11),
      'No earlier draws', 'Past draws appear here once a feed is connected.');
    renderList(archive, data.draws,
      'Archive is empty', 'Confirmed draws will be listed here, newest first.');
    renderFreq(data.draws);

    if (data.rejected > 0 && window.console) {
      console.warn('[keno] ' + data.rejected + ' draw(s) rejected by validation (must be 20 unique numbers in 1-80).');
    }
  }).catch(function () {
    if (heroEl) {
      heroEl.innerHTML = '';
      heroEl.appendChild(emptyBlock(
        'Results are temporarily unavailable',
        'We could not load the draw feed. Rather than show numbers we cannot verify, we show nothing.'
      ));
    }
    [recent, archive, freqEl, hcEl].forEach(function (el) {
      if (el) { el.innerHTML = ''; el.appendChild(emptyBlock('Unavailable', 'Could not load the draw feed.')); }
    });
  });
})();
