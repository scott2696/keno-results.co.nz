/* Quick-pick generator. Client-side, cryptographically seeded where available.
   Unlike competitors' versions, it shows the true odds of the line it just
   produced - because the odds are the honest part of picking numbers. */
(function () {
  'use strict';
  var K = window.Keno;
  var grid = document.getElementById('gen-grid');
  if (!grid || !K) return;

  var spotsSel = document.getElementById('gen-spots');
  var goBtn = document.getElementById('gen-go');
  var out = document.getElementById('gen-out');
  var oddsEl = document.getElementById('gen-odds');
  var copyBtn = document.getElementById('gen-copy');
  var picks = [];

  /* C(n, r) without overflow for the ranges Keno uses */
  function comb(n, r) {
    if (r < 0 || r > n) return 0;
    r = Math.min(r, n - r);
    var v = 1;
    for (var i = 0; i < r; i++) v = v * (n - i) / (i + 1);
    return v;
  }

  function randomInts(count, max) {
    var pool = [], i;
    for (i = 1; i <= max; i++) pool.push(i);
    var rand;
    if (window.crypto && window.crypto.getRandomValues) {
      rand = function (n) {
        var a = new Uint32Array(1);
        var limit = Math.floor(0xFFFFFFFF / n) * n;   // reject bias
        do { window.crypto.getRandomValues(a); } while (a[0] >= limit);
        return a[0] % n;
      };
    } else {
      rand = function (n) { return Math.floor(Math.random() * n); };
    }
    /* Fisher-Yates over the tail we need */
    for (i = 0; i < count; i++) {
      var j = i + rand(pool.length - i);
      var t = pool[i]; pool[i] = pool[j]; pool[j] = t;
    }
    return pool.slice(0, count).sort(function (a, b) { return a - b; });
  }

  function render() {
    grid.innerHTML = '';
    picks.forEach(function (n, i) {
      var li = K.ball(n, 'is-hit reveal');
      li.style.animationDelay = (i * 45) + 'ms';
      grid.appendChild(li);
    });
    if (out) out.value = picks.join(' ');

    var s = picks.length;
    var pTop = comb(20, s) / comb(80, s);
    var half = Math.ceil(s / 2);
    var pHalf = 0;
    for (var k = half; k <= s; k++) pHalf += comb(20, k) * comb(60, s - k) / comb(80, s);
    if (oddsEl) {
      oddsEl.innerHTML =
        '<p><strong>' + s + ' spot' + (s > 1 ? 's' : '') + '.</strong> ' +
        'Matching all ' + s + ' is about <strong>1 in ' +
        Math.round(1 / pTop).toLocaleString('en-NZ') + '</strong>. ' +
        'Matching at least ' + half + ' happens about <strong>' +
        (pHalf * 100).toFixed(1) + '%</strong> of the time.</p>' +
        '<p class="muted" style="font-size:13px;margin:8px 0 0">' +
        'These odds are identical for any ' + s + ' numbers you could have picked. ' +
        '<a href="/odds/' + s + '-spot/">Full ' + s + '-spot table</a>.</p>';
    }
  }

  function generate() {
    var s = spotsSel ? parseInt(spotsSel.value, 10) : 6;
    picks = randomInts(s, K.RANGE);
    render();
  }

  if (goBtn) goBtn.addEventListener('click', generate);
  if (spotsSel) spotsSel.addEventListener('change', generate);
  if (copyBtn) {
    copyBtn.addEventListener('click', function () {
      if (!picks.length) return;
      var txt = picks.join(' ');
      var done = function () {
        copyBtn.textContent = 'Copied';
        setTimeout(function () { copyBtn.textContent = 'Copy numbers'; }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt).then(done, function () {});
      } else if (out) { out.select(); try { document.execCommand('copy'); done(); } catch (e) {} }
    });
  }

  var useBtn = document.getElementById('gen-use');
  if (useBtn) {
    useBtn.addEventListener('click', function () {
      try { localStorage.setItem('picks', JSON.stringify(picks)); } catch (e) {}
      window.location.href = '/check/';
    });
  }

  generate();
})();
