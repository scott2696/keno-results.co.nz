/* Keno odds and return calculator.
   Competitors ship these with invented paytables, which produces an RTP figure
   that is precise and meaningless. Ours computes the probabilities exactly -
   those are fixed by the rules - and asks you for the prize values off your own
   ticket. Enter them and it returns a real expected value and house edge for
   that paytable. Leave them blank and it just shows the odds. */
(function () {
  'use strict';
  var K = window.Keno;
  var host = document.getElementById('calc');
  if (!host || !K) return;

  var spotsSel = document.getElementById('calc-spots');
  var stakeIn  = document.getElementById('calc-stake');
  var tbody    = document.getElementById('calc-rows');
  var summary  = document.getElementById('calc-summary');

  function comb(n, r) {
    if (r < 0 || r > n) return 0;
    r = Math.min(r, n - r);
    var v = 1;
    for (var i = 0; i < r; i++) v = v * (n - i) / (i + 1);
    return v;
  }

  function prob(spots, k) {
    return comb(20, k) * comb(60, spots - k) / comb(80, spots);
  }

  function fmtOdds(p) {
    if (p <= 0) return '—';
    var o = 1 / p;
    return '1 in ' + (o < 100 ? o.toFixed(1) : Math.round(o).toLocaleString('en-NZ'));
  }

  function build() {
    var spots = parseInt(spotsSel.value, 10);
    tbody.innerHTML = '';
    for (var k = spots; k >= 0; k--) {
      var p = prob(spots, k);
      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td class="num">' + k + ' of ' + spots + '</td>' +
        '<td class="num">' + fmtOdds(p) + '</td>' +
        '<td class="num">' + (p * 100).toFixed(4) + '%</td>' +
        '<td class="num"><input class="input calc-prize" type="number" min="0" step="0.01" ' +
        'inputmode="decimal" data-k="' + k + '" placeholder="0.00" aria-label="Prize for ' +
        k + ' of ' + spots + '"></td>';
      tbody.appendChild(tr);
    }
    tbody.querySelectorAll('.calc-prize').forEach(function (el) {
      el.addEventListener('input', compute);
    });
    compute();
  }

  function compute() {
    var spots = parseInt(spotsSel.value, 10);
    var stake = parseFloat(stakeIn.value) || 0;
    var ev = 0, anyPrize = false;

    tbody.querySelectorAll('.calc-prize').forEach(function (el) {
      var k = parseInt(el.dataset.k, 10);
      var prize = parseFloat(el.value);
      if (!isNaN(prize) && prize > 0) { anyPrize = true; ev += prob(spots, k) * prize; }
    });

    /* the part that needs no paytable */
    var half = Math.ceil(spots / 2), pHalf = 0, pAny = 0;
    for (var k = 1; k <= spots; k++) pAny += prob(spots, k);
    for (var k2 = half; k2 <= spots; k2++) pHalf += prob(spots, k2);

    var out =
      '<div class="calc-stats">' +
      '<div class="stat"><b>' + fmtOdds(prob(spots, spots)).replace('1 in ', '') + '</b>' +
      '<span>to 1 &mdash; matching all ' + spots + '</span></div>' +
      '<div class="stat"><b>' + (pHalf * 100).toFixed(1) + '%</b>' +
      '<span>matching ' + half + ' or more</span></div>' +
      '<div class="stat"><b>' + (pAny * 100).toFixed(1) + '%</b>' +
      '<span>matching at least one</span></div>' +
      '</div>';

    if (anyPrize && stake > 0) {
      var rtp = (ev / stake) * 100;
      var edge = 100 - rtp;
      out +=
        '<div class="calc-result">' +
        '<p class="result-h">Expected return: $' + ev.toFixed(2) + ' per $' +
        stake.toFixed(2) + ' staked</p>' +
        '<p>That is an RTP of <strong>' + rtp.toFixed(1) + '%</strong>, a house edge of ' +
        '<strong>' + edge.toFixed(1) + '%</strong>. Over 1,000 tickets at this stake you ' +
        'would expect to be down about <strong>$' +
        (stake * 1000 * edge / 100).toFixed(0) + '</strong>.</p>' +
        '<p class="muted" style="font-size:12.5px;margin-top:8px">Calculated from the prize ' +
        'values you entered. The probabilities are fixed by the rules of the game; the ' +
        'prizes are not ours and we cannot verify them.</p>' +
        '</div>';
    } else {
      out +=
        '<p class="muted" style="font-size:13.5px;text-align:center;margin-top:6px">' +
        'Enter the prize for each tier from your ticket or the operator&rsquo;s schedule to ' +
        'see the expected return and house edge for that paytable.</p>';
    }
    summary.innerHTML = out;
  }

  spotsSel.addEventListener('change', build);
  stakeIn.addEventListener('input', compute);
  build();
})();
