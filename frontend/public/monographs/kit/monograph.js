/* eslint-disable react-hooks/rules-of-hooks -- the kit is the approved page's plain browser script, not React */
(function () {
  'use strict';
  var root = document.documentElement;
  var mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
  function reduced() { return mq.matches || root.getAttribute('data-reduced-motion') === 'true'; }
  function store(k, v) { try { if (v == null || v === '') localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function arr(x) { return Array.prototype.slice.call(x || []); }
  function $(s, c) { return (c || document).querySelector(s); }
  function $$(s, c) { return arr((c || document).querySelectorAll(s)); }
  var KV = window.KV = {};
  KV.reduced = reduced;

  KV.near = function (el, fn, margin) {
    if (!el) return;
    if (!('IntersectionObserver' in window)) { fn(); return; }
    var done = false;
    var o = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting && !done) { done = true; o.disconnect(); fn(); } });
    }, { rootMargin: (margin || 900) + 'px 0px' });
    o.observe(el);
  };

  KV.scope = function (key) {
    var pre = key + '-';
    function roots() { return $$('.bx-' + key); }
    function fix(sel) {
      return String(sel).replace(/#([A-Za-z_][\w-]*)/g, function (m, id) { return ':is(#' + id + ',#' + pre + id + ',[data-aid="' + id + '"])'; });
    }
    function byId(id) {
      var rs = roots();
      for (var i = 0; i < rs.length; i++) {
        var x = rs[i].querySelector('[id="' + pre + id + '"]') || rs[i].querySelector('[id="' + id + '"]') || rs[i].querySelector('[data-aid="' + id + '"]');
        if (x) return x;
      }
      return null;
    }
    function qs(sel) {
      var f = fix(sel), rs = roots();
      for (var i = 0; i < rs.length; i++) { var x = rs[i].querySelector(f); if (x) return x; }
      return null;
    }
    function qsa(sel) {
      var f = fix(sel), out = [];
      roots().forEach(function (r) { Array.prototype.push.apply(out, arr(r.querySelectorAll(f))); });
      return out;
    }
    var api = { getElementById: byId, querySelector: qs, querySelectorAll: qsa, getElementsByClassName: function (c) { return qsa('.' + c); } };
    return new Proxy(document, {
      get: function (t, p) {
        if (Object.prototype.hasOwnProperty.call(api, p)) return api[p];
        var v = t[p];
        return typeof v === 'function' ? v.bind(t) : v;
      }
    });
  };

  KV.boot = function (key, fn) {
    var rs = $$('.bx-' + key).filter(function (r) { return !r.hidden; });
    var done = false;
    function run() {
      if (done) return; done = true;
      try { fn(KV.scope(key)); } catch (e) { if (window.console) console.error('KalaVigyan ' + key, e); }
    }
    if (!rs.length) return;
    if (!('IntersectionObserver' in window)) { run(); return; }
    var o = new IntersectionObserver(function (es) {
      if (es.some(function (e) { return e.isIntersecting; })) { o.disconnect(); run(); }
    }, { rootMargin: '1400px 0px' });
    rs.forEach(function (r) { o.observe(r); });
  };

  var ICON_X = '<svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2 2 L12 12 M12 2 L2 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
  var ICON_OK = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5 L6.5 12 L13 4.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  function toast(title, desc, tone) {
    var zone = document.getElementById('toasts'); if (!zone) return;
    var el = document.createElement('div');
    el.className = 'toast ' + (tone || 'success');
    el.innerHTML = '<span class="t-ic">' + ICON_OK + '</span><span class="t-body"><span class="t-title">' + esc(title) + '</span>' + (desc ? '<span class="t-desc">' + esc(desc) + '</span>' : '') + '</span><button class="t-x" type="button" aria-label="Dismiss">' + ICON_X + '</button>';
    zone.appendChild(el);
    while (zone.children.length > 3) zone.removeChild(zone.firstChild);
    var gone = function () { if (el.parentNode) el.parentNode.removeChild(el); };
    el.querySelector('.t-x').addEventListener('click', gone);
    setTimeout(gone, 5000);
  }
  KV.toast = toast;

  function effTheme() {
    var t = root.getAttribute('data-theme');
    if (t === 'light' || t === 'dark') return t;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  function paintTools() {
    $$('[data-kv-tool="theme"]').forEach(function (b) { b.setAttribute('aria-pressed', effTheme() === 'dark' ? 'true' : 'false'); });
    [['contrast', 'data-high-contrast'], ['text', 'data-larger-text'], ['motion', 'data-reduced-motion']].forEach(function (t) {
      $$('[data-kv-tool="' + t[0] + '"]').forEach(function (b) { b.setAttribute('aria-pressed', root.getAttribute(t[1]) === 'true' ? 'true' : 'false'); });
    });
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-kv-tool]');
    if (!b) return;
    var k = b.getAttribute('data-kv-tool');
    if (k === 'theme') {
      var next = effTheme() === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next); store('kv-theme', next);
    } else {
      var map = { contrast: ['data-high-contrast', 'kv-contrast'], text: ['data-larger-text', 'kv-text'], motion: ['data-reduced-motion', 'kv-motion'] }[k];
      var on = root.getAttribute(map[0]) === 'true';
      if (on) root.removeAttribute(map[0]); else root.setAttribute(map[0], 'true');
      store(map[1], on ? '' : 'true');
    }
    paintTools();
    window.dispatchEvent(new Event('kv-prefs'));
  });
  paintTools();

  var CD = { s: {}, c: {} };
  try { CD = JSON.parse(document.getElementById('kv-cites').textContent); } catch (e) {}
  var STR = {
    en: { one: '1 source for this sentence', many: '{n} sources for this sentence', open: 'Open the source', foot: 'Quotes are verbatim.', close: 'Close', relw: 'Reliability ', rel: { A: 'A · peer-reviewed or official', B: 'B · reputable reference', C: 'C · general web', D: 'D · unknown' }, from: 'From the {x}' },
    hi: { one: 'इस वाक्य का 1 स्रोत', many: 'इस वाक्य के {n} स्रोत', open: 'स्रोत खोलें', foot: 'उद्धरण स्रोत की अपनी भाषा में, शब्दशः हैं।', close: 'बंद करें', relw: 'विश्वसनीयता ', rel: { A: 'A · समकक्ष-समीक्षित या आधिकारिक', B: 'B · प्रतिष्ठित संदर्भ', C: 'C · सामान्य वेब', D: 'D · अज्ञात' }, from: null },
    ur: { one: 'اس جملے کا 1 ماخذ', many: 'اس جملے کے {n} ماخذ', open: 'ماخذ کھولیں', foot: 'اقتباسات ماخذ کی اپنی زبان میں، لفظ بہ لفظ ہیں۔', close: 'بند کریں', relw: 'اعتباریت ', rel: { A: 'A · ہم مرتبہ جائزہ شدہ یا سرکاری', B: 'B · معتبر حوالہ', C: 'C · عام ویب', D: 'D · نامعلوم' }, from: null }
  };
  var pop = document.getElementById('kv-pop');
  var scrim = document.getElementById('kv-scrim');
  var home = pop.parentNode;
  var current = null;
  function langOf(el) { var l = el.closest('[data-ui-lang]'); return l ? l.getAttribute('data-ui-lang') : 'en'; }
  function buildPop(btn) {
    var lang = langOf(btn), S = STR[lang] || STR.en;
    var gs = (btn.getAttribute('data-g') || '').split(' ').filter(Boolean);
    gs.sort(function (a, b) { return (CD.s[a] ? CD.s[a][0] : 0) - (CD.s[b] ? CD.s[b][0] : 0); });
    var seen = {}; gs = gs.filter(function (g) { if (seen[g]) return false; seen[g] = 1; return true; });
    var qs = CD.c[btn.getAttribute('data-c')] || [];
    var h = '<div class="pop-head"><p id="kv-pop-t">' + (gs.length === 1 ? S.one : S.many.replace('{n}', gs.length)) + '</p><button class="pop-close" type="button" aria-label="' + S.close + '">' + ICON_X + '</button></div>';
    gs.forEach(function (g) {
      var s = CD.s[g]; if (!s) return;
      h += '<div class="pop-src"><div class="pop-src-h"><b>' + s[0] + '</b><strong lang="en" dir="ltr">' + esc(s[1]) + '</strong></div>';
      h += '<p class="pop-by" lang="en" dir="ltr">' + esc(s[3]) + (s[4] ? ', ' + s[4] : '') + '</p>';
      if (s[7] && S.from) h += '<p class="pop-scope">' + esc(S.from.replace('{x}', s[7])) + '</p>';
      var seenq = {};
      qs.forEach(function (q) {
        if (q[0] !== g || !q[2] || seenq[q[2]]) return; seenq[q[2]] = 1;
        h += '<p class="pop-q" lang="en" dir="ltr">“' + esc(q[2]) + '”</p>' + (q[1] ? '<p class="pop-loc" lang="en" dir="ltr">' + esc(q[1]) + '</p>' : '');
      });
      h += '<p class="pop-rel"><span class="rel ' + esc(s[5]) + '" aria-hidden="true"></span>' + S.relw + esc(S.rel[s[5]] || s[5]) + '</p>';
      if (s[6]) h += '<p class="pop-loc"><a href="' + esc(s[6]) + '" rel="noopener" target="_blank">' + S.open + '</a></p>';
      h += '</div>';
    });
    h += '<p class="pop-foot">' + S.foot + '</p>';
    return { html: h, lang: lang };
  }
  function place(btn) {
    var vw = document.documentElement.clientWidth;
    pop.classList.remove('sheet', 'docked', 'floating');
    pop.style.left = pop.style.top = pop.style.width = pop.style.position = '';
    if (vw < 640) {
      document.body.appendChild(pop);
      pop.classList.add('sheet'); pop.setAttribute('aria-modal', 'true'); scrim.hidden = false; return;
    }
    pop.setAttribute('aria-modal', 'false'); scrim.hidden = true;
    var spread = btn.closest('.spread');
    var margin = spread && spread.querySelector(':scope > .margin');
    var inMain = spread && btn.closest('.spread > .main, .spread > .wide');
    if (vw >= 1200 && margin && inMain && margin.offsetParent !== null && getComputedStyle(margin).display !== 'none') {
      margin.appendChild(pop);
      pop.classList.add('docked');
      var m = margin.getBoundingClientRect(), r = btn.getBoundingClientRect();
      pop.style.top = Math.max(0, r.top - m.top - 14) + 'px';
      return;
    }
    document.body.appendChild(pop);
    pop.classList.add('floating');
    var rr = btn.getBoundingClientRect();
    var width = Math.min(380, vw - 32);
    var left = Math.max(16, Math.min(rr.left - 24, vw - 16 - width)) + window.scrollX;
    pop.style.position = 'absolute'; pop.style.width = width + 'px';
    pop.style.left = left + 'px'; pop.style.top = (rr.bottom + window.scrollY + 10) + 'px';
  }
  function close(returnFocus) {
    if (!current) return;
    current.setAttribute('aria-expanded', 'false');
    var s = current.closest('.s'); if (s) s.classList.remove('is-lit');
    pop.hidden = true; pop.classList.remove('is-open'); scrim.hidden = true;
    var c = current; current = null;
    if (returnFocus) c.focus({ preventScroll: true });
  }
  function open(btn) {
    if (current === btn) { close(true); return; }
    close(false);
    current = btn;
    var b = buildPop(btn);
    pop.innerHTML = b.html;
    pop.setAttribute('lang', b.lang);
    if (b.lang === 'ur') pop.setAttribute('dir', 'rtl'); else pop.removeAttribute('dir');
    pop.hidden = false;
    place(btn);
    pop.classList.remove('is-open'); void pop.offsetWidth; pop.classList.add('is-open');
    btn.setAttribute('aria-expanded', 'true');
    if (!reduced()) { btn.classList.remove('press'); void btn.offsetWidth; btn.classList.add('press'); }
    var s = btn.closest('.s'); if (s) s.classList.add('is-lit');
    pop.querySelector('.pop-close').addEventListener('click', function () { close(true); });
    pop.focus({ preventScroll: true });
  }
  pop.setAttribute('tabindex', '-1');
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.kcite');
    if (btn && !btn.closest('[inert]')) { e.preventDefault(); open(btn); return; }
    if (current && !pop.contains(e.target)) close(false);
  });
  scrim.addEventListener('click', function () { close(true); closeMenu(); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { if (current) { close(true); return; } if (menuOpen()) { closeMenu(true); return; } }
    if (e.key === 'Tab' && current && pop.classList.contains('sheet')) {
      var f = pop.querySelectorAll('button, a[href]');
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === pop)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  var rt = 0;
  window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(function () { if (current) place(current); }, 80); });

  var srcStatus = document.getElementById('kv-src-status');
  var lit = [], litI = -1;
  function clearLit() { $$('.is-src').forEach(function (x) { x.classList.remove('is-src'); }); lit = []; litI = -1; }
  $$('.kv-sources .src').forEach(function (b) {
    b.addEventListener('click', function () {
      var on = b.getAttribute('aria-pressed') === 'true';
      $$('.kv-sources .src').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
      clearLit();
      if (on) { srcStatus.innerHTML = ''; return; }
      b.setAttribute('aria-pressed', 'true');
      var g = b.getAttribute('data-g'), n = b.querySelector('b').textContent;
      $$('.kcite').forEach(function (c) {
        if ((' ' + c.getAttribute('data-g') + ' ').indexOf(' ' + g + ' ') < 0) return;
        if (c.closest('.kv-sources') || c.closest('[hidden]')) return;
        var s = c.closest('.s') || c.parentNode;
        if (lit.indexOf(s) < 0) { s.classList.add('is-src'); lit.push(s); }
      });
      srcStatus.innerHTML = '<span>Source ' + esc(n) + ' lights ' + lit.length + ' sentence' + (lit.length === 1 ? '' : 's') + ' on this page.</span>' + (lit.length ? '<button class="kv-btn sm" type="button" data-src-next>Show the first</button>' : '');
    });
  });
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-src-next]');
    if (!b || !lit.length) return;
    litI = (litI + 1) % lit.length;
    lit[litI].scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'center' });
    b.textContent = 'Show the next (' + (litI + 1) + ' of ' + lit.length + ')';
  });

  document.addEventListener('click', function (e) {
    var a = e.target.closest('[data-rp-step]');
    if (!a) return;
    var p = a.getAttribute('data-rp-step').split(':');
    var fig = document.getElementById(p[0]);
    if (!fig) return;
    var btn = fig.querySelectorAll('.rp-rail button')[+p[1] - 1];
    if (btn) setTimeout(function () { btn.click(); }, reduced() ? 0 : 350);
  });
  $$('[data-kv-save]').forEach(function (b) {
    b.addEventListener('click', function () {
      var on = b.getAttribute('aria-pressed') === 'true';
      b.setAttribute('aria-pressed', String(!on));
      b.textContent = on ? 'Save' : 'Saved';
      if (!on) toast('Saved', 'Find it under Saved.', 'success');
    });
  });
  function settle(t) {
    var n = 0, last = null;
    (function chk() {
      n++;
      var want = parseFloat(getComputedStyle(root).scrollPaddingTop) || 0;
      var top = t.getBoundingClientRect().top;
      if (last !== null && Math.abs(top - last) < 2 && Math.abs(top - want) > 24) t.scrollIntoView({ behavior: 'auto', block: 'start' });
      last = top;
      if (n < 12) setTimeout(chk, 250);
    })();
  }
  function selTab(which, focus) {
    $$('[data-kv-ct]').forEach(function (t) {
      var on = t.getAttribute('data-kv-ct') === which;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
      var p = document.getElementById(t.getAttribute('aria-controls'));
      if (p) p.hidden = !on;
      if (on && focus) t.focus();
    });
  }
  $$('[data-kv-ct]').forEach(function (t, i, all) {
    t.addEventListener('click', function () { selTab(t.getAttribute('data-kv-ct')); });
    t.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft' && e.key !== 'Home' && e.key !== 'End') return;
      e.preventDefault();
      var k = e.key === 'Home' ? 0 : e.key === 'End' ? all.length - 1 : (i + (e.key === 'ArrowRight' ? 1 : -1) + all.length) % all.length;
      selTab(all[k].getAttribute('data-kv-ct'), true);
    });
  });
  $$('.kv-q-more').forEach(function (b) {
    b.addEventListener('click', function () {
      var p = document.getElementById(b.getAttribute('aria-controls'));
      var on = b.getAttribute('aria-expanded') === 'true';
      if (p) p.hidden = on;
      b.setAttribute('aria-expanded', on ? 'false' : 'true');
      b.textContent = on ? 'Show the full question' : 'Show less';
    });
  });
  $$('[data-kv-goto]').forEach(function (b) {
    b.addEventListener('click', function () {
      var t = document.getElementById(b.getAttribute('data-kv-goto'));
      if (!t) return;
      if (b.getAttribute('data-kv-tab')) selTab(b.getAttribute('data-kv-tab'));
      t.scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'start' });
      settle(t);
      var f = t.querySelector('button');
      if (f) setTimeout(function () { f.focus({ preventScroll: true }); }, reduced() ? 0 : 600);
    });
  });

  var made = document.querySelector('[data-kv-made]');
  if (made) {
    var mBtn = made.querySelector('[data-kv-made-play]');
    var mSrc = $$('.kv-ms', made), mSec = $$('.kv-mw', made), mPg = $$('.prog li', made);
    var mReady = made.querySelector('[data-kv-made-ready]'), mSay = made.querySelector('[data-kv-made-status]');
    var mT = [];
    var SRC0 = 500, SRC_STEP = Math.max(60, Math.round(4200 / Math.max(1, mSrc.length))), SEC0 = 1400, SEC_STEP = 820;
    var SRC_END = SRC0 + SRC_STEP * mSrc.length, SEC_END = SEC0 + SEC_STEP * mSec.length;
    var PG = [[0, 450], [450, SRC_END], [SEC0, SEC_END], [SEC0 + 300, SEC_END + 500], [SEC_END + 200, SEC_END + 1200]];
    var END = SEC_END + 1300;
    function mRender(t) {
      mSrc.forEach(function (li, i) { li.classList.toggle('is-in', t >= SRC0 + i * SRC_STEP); });
      mSec.forEach(function (li, i) {
        var a = SEC0 + i * SEC_STEP;
        li.classList.toggle('is-in', t >= a);
        li.classList.toggle('is-busy', t >= a && t < a + SEC_STEP - 120);
        li.classList.toggle('is-done', t >= a + SEC_STEP - 120);
      });
      var on = [];
      mPg.forEach(function (li, i) {
        var w = PG[i] || PG[PG.length - 1];
        var st = t >= w[1] ? 'done' : (t >= w[0] ? 'on' : 'next');
        li.classList.toggle('is-done', st === 'done');
        li.classList.toggle('is-on', st === 'on');
        if (st === 'on') { li.setAttribute('aria-current', 'step'); var l = li.querySelector('.pg-l'); if (l) on.push(l.textContent); } else li.removeAttribute('aria-current');
      });
      if (mReady) mReady.classList.toggle('is-in', t >= END);
      if (mSay) mSay.textContent = t >= END ? 'The answer is ready' : on.join(', ');
    }
    function mStop() { mT.forEach(clearTimeout); mT = []; }
    function mPlay() {
      mStop();
      if (reduced()) { made.classList.remove('is-run'); mRender(END); return; }
      made.classList.add('is-run');
      mRender(0);
      var start = performance.now();
      (function step() {
        var t = performance.now() - start;
        mRender(t);
        if (t < END) mT.push(setTimeout(step, 50)); else { made.classList.remove('is-run'); mBtn.textContent = 'Watch it again'; }
      })();
      mBtn.textContent = 'Watching';
    }
    mRender(END);
    if (mBtn) mBtn.addEventListener('click', mPlay);
  }

  var chapters = $$('section.kv-ch');
  var railLinks = $$('.kv-rail a');
  var menuBtn = document.getElementById('kv-menu-btn');
  var menu = document.getElementById('kv-menu');
  var menuLabel = document.getElementById('kv-menu-label');
  var rail = $('.kv-rail');
  var railList = rail ? rail.querySelector('ol') : null;
  var railGo = rail ? $$('.kv-rail-go', rail) : [];
  var RAIL_FADE = 48;
  function railEnds() {
    var max = Math.max(0, railList.scrollWidth - railList.clientWidth);
    var at = Math.min(max, Math.abs(railList.scrollLeft));
    return { over: max > 1, back: max > 1 ? Math.min(RAIL_FADE, at) : 0, on: max > 1 ? Math.min(RAIL_FADE, max - at) : 0 };
  }
  function railHide(b, ends) {
    var hide = ends[b.getAttribute('data-go')] < 1;
    if (hide && !b.hidden && document.activeElement === b) {
      var other = railGo.filter(function (o) { return o !== b && ends[o.getAttribute('data-go')] >= 1; })[0];
      var to = other || railList.querySelector('a[aria-current]') || railList.querySelector('a');
      if (to) to.focus();
    }
    b.hidden = hide;
  }
  function railEdges() {
    if (!railList) return;
    var ends = railEnds();
    rail.setAttribute('data-edges', ends.over ? 'over' : 'fit');
    rail.style.setProperty('--rail-back', ends.back + 'px');
    rail.style.setProperty('--rail-on', ends.on + 'px');
    railGo.forEach(function (b) { railHide(b, ends); });
  }
  function railGoBy(dir) {
    var step = Math.max(120, railList.clientWidth - 2 * RAIL_FADE);
    railList.scrollBy({ left: dir * step, behavior: reduced() ? 'auto' : 'smooth' });
  }
  function railShow(a) {
    if (!railList || railList.scrollWidth <= railList.clientWidth + 1) return;
    var r = a.getBoundingClientRect(), box = railList.getBoundingClientRect();
    if (r.left >= box.left + RAIL_FADE && r.right <= box.right - RAIL_FADE) return;
    var left = railList.scrollLeft + (r.left - box.left) - (box.width - r.width) / 2;
    railList.scrollTo({ left: Math.max(0, left), behavior: reduced() ? 'auto' : 'smooth' });
  }
  if (railList) {
    railGo.forEach(function (b) { b.addEventListener('click', function () { railGoBy(b.getAttribute('data-go') === 'back' ? -1 : 1); }); });
    railList.addEventListener('scroll', railEdges, { passive: true });
    window.addEventListener('resize', railEdges);
    if ('ResizeObserver' in window) {
      var railSizes = new ResizeObserver(railEdges);
      railSizes.observe(railList);
      $$('li', railList).forEach(function (li) { railSizes.observe(li); });
    }
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(railEdges);
    railEdges();
  }
  function setCurrent(id) {
    railLinks.forEach(function (a) {
      var on = a.getAttribute('href') === '#' + id;
      if (on) a.setAttribute('aria-current', 'location'); else a.removeAttribute('aria-current');
      if (on) railShow(a);
    });
    $$('#kv-menu a').forEach(function (a) { if (a.getAttribute('href') === '#' + id) a.setAttribute('aria-current', 'location'); else a.removeAttribute('aria-current'); });
    var ch = document.getElementById(id);
    var railed = railLinks.some(function (a) { return a.getAttribute('href') === '#' + id; });
    if (!railed && railLinks.length) ch = document.getElementById(railLinks[0].getAttribute('href').slice(1));
    if (ch && menuLabel) {
      var n = +ch.getAttribute('data-ch');
      menuLabel.innerHTML = (n ? '<b>' + n + '</b>' : '') + '<span>' + esc(ch.getAttribute('data-label')) + '</span>';
    }
  }
  if ('IntersectionObserver' in window && chapters.length) {
    var vis = {};
    var so = new IntersectionObserver(function (es) {
      es.forEach(function (e) { vis[e.target.id] = e.isIntersecting; });
      for (var i = 0; i < chapters.length; i++) { if (vis[chapters[i].id]) { setCurrent(chapters[i].id); break; } }
    }, { rootMargin: '-35% 0px -60% 0px' });
    chapters.forEach(function (c) { so.observe(c); });
  }
  function menuOpen() { return menu && !menu.hidden; }
  function openMenu() { menu.hidden = false; scrim.hidden = false; menuBtn.setAttribute('aria-expanded', 'true'); var a = menu.querySelector('a[aria-current]') || menu.querySelector('a'); if (a) a.focus(); }
  function closeMenu(focus) { if (!menuOpen()) return; menu.hidden = true; if (!current) scrim.hidden = true; menuBtn.setAttribute('aria-expanded', 'false'); if (focus) menuBtn.focus(); }
  if (menuBtn) menuBtn.addEventListener('click', function () { if (menuOpen()) closeMenu(true); else openMenu(); });
  if (menu) {
    menu.addEventListener('click', function (e) { if (e.target.closest('a')) closeMenu(false); });
    var mc = menu.querySelector('.kv-menu-close'); if (mc) mc.addEventListener('click', function () { closeMenu(true); });
  }

  var player = document.getElementById('kv-player');
  var LS = { sents: [], i: 0, playing: false, rate: 1, timer: 0, wi: 0, words: [], speech: false, utter: null, totalW: 0, startT: 0, base: 0 };
  function sentText(s) {
    var c = s.cloneNode(true);
    $$('.kcite', c).forEach(function (x) { x.remove(); });
    return c.textContent.replace(/\s+/g, ' ').trim();
  }
  function collect() {
    LS.sents = $$('#answer .ans-lede .s, .kv-ch:not(#answer) .t-lede .s').filter(function (s) {
      return !s.closest('[hidden], .kv-lang, .lang-demo, .kv-alt, #media, .kv-made-how, .kv-coda, details:not([open])');
    });
    LS.counts = LS.sents.map(function (s) { return sentText(s).split(' ').length; });
    LS.totalW = LS.counts.reduce(function (a, b) { return a + b; }, 0);
    LS.before = [];
    var acc = 0; LS.counts.forEach(function (c) { LS.before.push(acc); acc += c; });
  }
  collect();
  $$('[data-listen-min]').forEach(function (el) { el.textContent = Math.max(1, Math.round(LS.totalW / 150)); });
  function mmss(t) { t = Math.max(0, Math.round(t)); return Math.floor(t / 60) + ':' + ('0' + (t % 60)).slice(-2); }
  function sectionName(s) {
    var ch = s.closest('.kv-ch');
    if (!ch || ch.id === 'answer') return 'The short answer';
    var n = +ch.getAttribute('data-ch');
    return (n ? n + ' · ' : '') + ch.getAttribute('data-label');
  }
  function unwrap(s) { if (s && s.__orig != null) { s.innerHTML = s.__orig; s.__orig = null; } if (s) s.classList.remove('is-reading'); }
  function wrapWords(s) {
    s.__orig = s.innerHTML;
    var walker = document.createTreeWalker(s, NodeFilter.SHOW_TEXT, { acceptNode: function (n) { return n.parentNode.closest('.kcite') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT; } });
    var nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
    var words = [];
    nodes.forEach(function (n) {
      var parts = n.nodeValue.split(/(\s+)/);
      var frag = document.createDocumentFragment();
      parts.forEach(function (p) {
        if (!p) return;
        if (/^\s+$/.test(p)) { frag.appendChild(document.createTextNode(p)); return; }
        var sp = document.createElement('span'); sp.className = 'kv-w'; sp.textContent = p; frag.appendChild(sp); words.push(sp);
      });
      n.parentNode.replaceChild(frag, n);
    });
    return words;
  }
  function paint() {
    var s = LS.sents[LS.i];
    var el = player.querySelector('.kvp-where'), st = player.querySelector('.kvp-status');
    el.textContent = s ? sectionName(s) : '';
    st.textContent = 'Sentence ' + (LS.i + 1) + ' of ' + LS.sents.length;
    var done = (LS.before[LS.i] || 0) + LS.wi;
    var secs = done / (150 * LS.rate) * 60, tot = LS.totalW / (150 * LS.rate) * 60;
    player.querySelector('.kvp-t').textContent = mmss(secs) + ' / ' + mmss(tot);
    player.querySelector('.kvp-bar b').style.width = (LS.totalW ? done / LS.totalW * 100 : 0) + '%';
    var pb = player.querySelector('.kvp-play');
    pb.setAttribute('aria-label', LS.playing ? 'Pause' : 'Play');
    pb.innerHTML = LS.playing ? '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3.5" y="2.8" width="3.2" height="10.4" rx=".8" fill="currentColor"/><rect x="9.3" y="2.8" width="3.2" height="10.4" rx=".8" fill="currentColor"/></svg>' : '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 2.8 L13 8 L4.5 13.2 Z" fill="currentColor"/></svg>';
  }
  function markWord() {
    LS.words.forEach(function (w, k) { w.classList.toggle('is-word', k === LS.wi); });
    paint();
  }
  function stopTimers() { clearTimeout(LS.timer); if (LS.speech && window.speechSynthesis) { try { speechSynthesis.cancel(); } catch (e) {} } }
  function useSpeech() {
    if (!('speechSynthesis' in window)) return false;
    var v = speechSynthesis.getVoices();
    return v && v.length > 0;
  }
  function voice() {
    var vs = speechSynthesis.getVoices();
    return vs.filter(function (v) { return /en[-_]IN/i.test(v.lang); })[0] || vs.filter(function (v) { return /^en/i.test(v.lang); })[0] || vs[0];
  }
  function startSentence(i, scroll) {
    stopTimers();
    unwrap(LS.sents[LS.i]);
    LS.i = Math.max(0, Math.min(LS.sents.length - 1, i));
    var s = LS.sents[LS.i];
    if (!s) return;
    s.classList.add('is-reading');
    LS.words = wrapWords(s);
    LS.wi = 0;
    if (scroll !== false) {
      var r = s.getBoundingClientRect();
      if (r.top < 90 || r.bottom > window.innerHeight - 120) s.scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'center' });
    }
    markWord();
    if (!LS.playing) return;
    if (LS.speech) {
      var text = LS.words.map(function (w) { return w.textContent; }).join(' ');
      var starts = []; var acc = 0; LS.words.forEach(function (w) { starts.push(acc); acc += w.textContent.length + 1; });
      var u = new SpeechSynthesisUtterance(text);
      u.rate = LS.rate; var vv = voice(); if (vv) { u.voice = vv; u.lang = vv.lang; }
      u.onboundary = function (e) {
        if (e.name && e.name !== 'word') return;
        var k = 0; for (var j = 0; j < starts.length; j++) { if (starts[j] <= e.charIndex) k = j; }
        LS.wi = k; markWord();
      };
      u.onend = function () { if (LS.utter !== u) return; next(true); };
      u.onerror = function () { if (LS.utter !== u) return; LS.speech = false; tick(); };
      LS.utter = u;
      speechSynthesis.speak(u);
    } else {
      tick();
    }
  }
  function tick() {
    clearTimeout(LS.timer);
    if (!LS.playing) return;
    var ms = 60000 / (150 * LS.rate);
    LS.timer = setTimeout(function () {
      if (LS.wi < LS.words.length - 1) { LS.wi++; markWord(); tick(); }
      else next(true);
    }, ms);
  }
  function next(auto) {
    if (LS.i >= LS.sents.length - 1) {
      LS.playing = false; stopTimers(); LS.wi = LS.words.length - 1; markWord();
      player.querySelector('.kvp-status').textContent = 'Read to the end';
      return;
    }
    startSentence(LS.i + 1);
  }
  function play() {
    LS.playing = true;
    LS.speech = useSpeech();
    startSentence(LS.i);
  }
  function pause() { LS.playing = false; stopTimers(); paint(); }
  function openPlayer() {
    player.hidden = false;
    document.body.classList.add('kv-has-player');
    if (!LS.sents.length) collect();
    if (!LS.playing) play();
    player.querySelector('.kvp-play').focus({ preventScroll: true });
  }
  if (player) {
    document.addEventListener('click', function (e) { if (e.target.closest('[data-listen-open]')) openPlayer(); });
    player.querySelector('.kvp-play').addEventListener('click', function () { if (LS.playing) pause(); else play(); });
    player.querySelector('.kvp-prev').addEventListener('click', function () { startSentence(LS.i - 1); });
    player.querySelector('.kvp-next').addEventListener('click', function () { startSentence(LS.i + 1); });
    player.querySelector('.kvp-rate').addEventListener('change', function (e) { LS.rate = +e.target.value; if (LS.playing) startSentence(LS.i, false); else paint(); });
    player.querySelector('.kvp-close').addEventListener('click', function () {
      LS.playing = false; stopTimers(); unwrap(LS.sents[LS.i]); player.hidden = true; document.body.classList.remove('kv-has-player');
    });
    player.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') { e.preventDefault(); startSentence(LS.i - 1); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); startSentence(LS.i + 1); }
      else if (e.key === 'Escape') { player.querySelector('.kvp-close').click(); }
    });
    if ('speechSynthesis' in window) { try { speechSynthesis.getVoices(); speechSynthesis.onvoiceschanged = function () {}; } catch (e) {} }
    LS.words = []; paint();
  }
})();
KV.boot('chem', function (document) {
(function () {
  var root = document.documentElement;
  var osReduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  function reduced() { return osReduce.matches || root.getAttribute('data-reduced-motion') === 'true'; }
  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function arr(x) { return Array.prototype.slice.call(x); }

  var frames = arr(document.querySelectorAll('iframe.kv-frame'));
  var frameBase = frames.map(function (f) { return f.getAttribute('data-srcdoc') || ''; }); frames.forEach(function (f) { KV.near(f, function () { f.__near = 1; rekey(); }, 700); }); window.addEventListener('kv-prefs', function () { rekey(); });
  function rekey() {
    var attrs = '';
    var t = root.getAttribute('data-theme');
    if (t) attrs += ' data-theme="' + t + '"';
    if (root.getAttribute('data-high-contrast') === 'true') attrs += ' data-high-contrast="true"';
    if (reduced()) attrs += ' data-reduced-motion="true"';
    frames.forEach(function (f, i) { if (!f.__near) return; f.setAttribute('srcdoc', frameBase[i].replace('<html lang="en">', '<html lang="en"' + attrs + '>')); });
  }
  window.addEventListener('message', function (e) {
    var d = e.data;
    if (!d || typeof d !== 'object' || Object.keys(d).length !== 1 || typeof d.kvFrameHeight !== 'number' || !isFinite(d.kvFrameHeight)) return;
    frames.forEach(function (f) { if (f.contentWindow === e.source) f.style.height = Math.min(1200, Math.max(120, Math.ceil(d.kvFrameHeight))) + 'px'; });
  });

  var themeBtn = document.getElementById('theme-toggle');
  function effectiveTheme() {
    var t = root.getAttribute('data-theme');
    if (t === 'light' || t === 'dark') return t;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  function paintTheme() { themeBtn.setAttribute('aria-pressed', effectiveTheme() === 'dark' ? 'true' : 'false'); }
  themeBtn.addEventListener('click', function () {
    var next = effectiveTheme() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next); store('kv-theme', next); paintTheme(); rekey();
  });
  paintTheme();
  [['motion-toggle', 'data-reduced-motion', 'kv-motion'], ['contrast-toggle', 'data-high-contrast', 'kv-contrast'], ['text-toggle', 'data-larger-text', 'kv-text']].forEach(function (t) {
    var b = document.getElementById(t[0]);
    if (!b) return;
    function paint() { b.setAttribute('aria-pressed', root.getAttribute(t[1]) === 'true' ? 'true' : 'false'); }
    b.addEventListener('click', function () {
      var on = root.getAttribute(t[1]) === 'true';
      if (on) root.removeAttribute(t[1]); else root.setAttribute(t[1], 'true');
      store(t[2], on ? '' : 'true'); paint(); rekey();
    });
    paint();
  });

  function fit(svg) {
    var vb = svg.viewBox && svg.viewBox.baseVal;
    var w = svg.getBoundingClientRect().width;
    if (!vb || !vb.width || !w) return;
    var k = vb.width / w;
    svg.style.setProperty('--k', k.toFixed(3));
    svg.classList.toggle('tight', k > 1.45);
    minText(svg, k);
  }
  function minText(svg, k) {
    arr(svg.querySelectorAll('text, tspan')).forEach(function (el) {
      el.style.removeProperty('font-size');
      var px = parseFloat(getComputedStyle(el).fontSize);
      if (px && px / k < 12) el.style.fontSize = (12 * k).toFixed(2) + 'px';
    });
  }
  var fitSvgs = arr(document.querySelectorAll('svg[data-fit]'));
  if ('ResizeObserver' in window) {
    var ro = new ResizeObserver(function (es) { es.forEach(function (en) { fit(en.target); }); });
    fitSvgs.forEach(function (s) { ro.observe(s); });
  }
  fitSvgs.forEach(fit);

  var qBtn = document.querySelector('.q-more');
  if (qBtn) qBtn.addEventListener('click', function () {
    var h = document.querySelector('h1.ask-q');
    var open = qBtn.getAttribute('aria-expanded') !== 'true';
    qBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    h.classList.toggle('is-open', open);
    qBtn.textContent = open ? 'Show less of the question' : 'Show the full question';
  });

  var data = { sources: {}, claims: {}, rel: {} };
  try { data = JSON.parse(document.getElementById('cite-data').textContent); } catch (e) {}
  var pop = document.getElementById('pop');
  var scrim = document.getElementById('scrim');
  var current = null;
  function build(btn) {
    var nums = {};
    btn.getAttribute('data-n').split(',').forEach(function (pair) { var b = pair.split('='); nums[b[0]] = +b[1]; });
    var bySource = {};
    btn.getAttribute('data-claims').split(' ').forEach(function (cid) {
      (data.claims[cid] || []).forEach(function (q) { (bySource[q[0]] = bySource[q[0]] || []).push(q); });
    });
    var order = Object.keys(bySource).sort(function (a, b) { return nums[a] - nums[b]; });
    var out = '<div class="pop-head"><p id="pop-title">' + (order.length === 1 ? 'Source' : order.length + ' sources') + ' for this sentence</p>' +
      '<button class="pop-close" type="button" aria-label="Close"><svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2 2 L12 12 M12 2 L2 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button></div>';
    order.forEach(function (sk) {
      var s = data.sources[sk] || {};
      out += '<div class="pop-src"><div class="pop-src-h"><b>' + nums[sk] + '</b><strong>' + esc(s.t || sk) + '</strong></div>' +
        '<p class="pop-by">' + esc(s.by || '') + (s.y ? ', ' + s.y : '') + '</p>' + (s.sc ? '<p class="pop-scope">From the ' + esc(s.sc) + '</p>' : '');
      var seen = {};
      bySource[sk].forEach(function (q) {
        if (seen[q[2]]) return; seen[q[2]] = 1;
        out += '<p class="pop-q">“' + esc(q[2]) + '”</p>' + (q[1] ? '<p class="pop-loc">' + esc(q[1]) + '</p>' : '');
      });
      out += '<p class="pop-rel"><span class="rel ' + esc(s.r) + '" aria-hidden="true"></span>Reliability ' + esc(s.r) + ' · ' + esc((data.rel || {})[s.r] || '') + '</p>';
      if (s.u) out += '<p class="pop-loc"><a href="' + esc(s.u) + '" rel="noopener" target="_blank">Open the source</a></p>';
      out += '</div>';
    });
    out += '<p class="pop-foot">Quotes are verbatim.</p>';
    return out;
  }
  function place(btn) {
    var vw = document.documentElement.clientWidth;
    pop.classList.remove('sheet', 'docked', 'floating');
    pop.style.left = pop.style.top = pop.style.width = pop.style.position = '';
    if (vw < 640) {
      document.body.appendChild(pop);
      pop.classList.add('sheet'); pop.setAttribute('aria-modal', 'true'); scrim.hidden = false; return;
    }
    pop.setAttribute('aria-modal', 'false'); scrim.hidden = true;
    var spread = btn.closest('.spread');
    var margin = spread && spread.querySelector(':scope > .margin');
    var inMain = spread && btn.closest('.spread > .main');
    if (vw >= 1200 && margin && inMain && margin.offsetParent !== null) {
      margin.appendChild(pop);
      pop.classList.add('docked');
      var m = margin.getBoundingClientRect(), r = btn.getBoundingClientRect();
      pop.style.top = Math.max(0, r.top - m.top - 14) + 'px';
      return;
    }
    var block = btn.closest('p, li, dd, figcaption, .reading, div') || btn.parentNode;
    block.insertAdjacentElement('afterend', pop);
    pop.classList.add('floating');
    var op = pop.offsetParent || document.body;
    var o = op.getBoundingClientRect(), rr = btn.getBoundingClientRect();
    var width = Math.min(380, vw - 32);
    var left = Math.max(16 - o.left, Math.min(rr.left - o.left - 24, vw - 16 - width - o.left));
    pop.style.position = 'absolute'; pop.style.width = width + 'px';
    pop.style.left = left + 'px'; pop.style.top = (rr.bottom - o.top + 10) + 'px';
  }
  function close(returnFocus) {
    if (!current) return;
    current.setAttribute('aria-expanded', 'false');
    var s = current.closest('.s'); if (s) s.classList.remove('is-lit');
    pop.hidden = true; pop.classList.remove('is-open'); scrim.hidden = true;
    if (returnFocus) current.focus({ preventScroll: true });
    current = null;
  }
  function openPop(btn) {
    if (current === btn) { close(true); return; }
    close(false);
    current = btn;
    pop.innerHTML = build(btn);
    pop.hidden = false;
    place(btn);
    pop.classList.remove('is-open'); void pop.offsetWidth; pop.classList.add('is-open');
    btn.setAttribute('aria-expanded', 'true');
    if (!reduced()) { btn.classList.remove('press'); void btn.offsetWidth; btn.classList.add('press'); }
    var s = btn.closest('.s'); if (s) s.classList.add('is-lit');
    pop.querySelector('.pop-close').addEventListener('click', function () { close(true); });
    pop.focus({ preventScroll: true });
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.cite');
    if (btn && !btn.closest('[inert]')) { e.preventDefault(); openPop(btn); return; }
    if (current && !pop.contains(e.target)) close(false);
  });
  scrim.addEventListener('click', function () { close(true); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && current) { close(true); return; }
    if (e.key === 'Tab' && current && pop.classList.contains('sheet')) {
      var f = pop.querySelectorAll('button, a[href]');
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === pop)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  window.addEventListener('resize', function () { if (current) place(current); });

  function pick(spec, s) {
    var best = null, bk = -1;
    spec.split(';').forEach(function (p) {
      var i = p.indexOf('=');
      if (i < 0) return;
      var k = +p.slice(0, i);
      if (k <= s && k > bk) { bk = k; best = p.slice(i + 1); }
    });
    return best;
  }
  function inRange(spec, s) {
    return spec.split(',').some(function (r) { var a = r.split('-'); return a.length > 1 ? s >= +a[0] && s <= +a[1] : s === +a[0]; });
  }
  var players = [];
  function Player(fig) {
    var n = +fig.getAttribute('data-steps');
    var step = +fig.getAttribute('data-step');
    var btns = arr(fig.querySelectorAll('.rp-rail button'));
    var panels = arr(fig.querySelectorAll('.rp-step'));
    var chems = arr(fig.querySelectorAll('.rp-chem'));
    var rxs = arr(fig.querySelectorAll('.rx'));
    var scene = fig.querySelector('svg.scene');
    var els = arr(fig.querySelectorAll('svg.scene [data-on], svg.scene [data-fill], svg.scene [data-stroke], svg.scene [data-tf], svg.scene [data-op], svg.scene [data-dim]'));
    var status = fig.querySelector('.rp-status');
    var playBtn = fig.querySelector('.rp-play');
    var stepMs = rxs.length ? 3600 : 3800;
    var timers = [], playing = false, runT = 0;
    function clear() { timers.forEach(clearTimeout); timers = []; }
    function apply(s) {
      els.forEach(function (el) {
        var v;
        if (el.hasAttribute('data-on')) el.classList.toggle('off', !inRange(el.getAttribute('data-on'), s));
        if (el.hasAttribute('data-dim')) el.classList.toggle('dim', inRange(el.getAttribute('data-dim'), s));
        if (el.hasAttribute('data-fill')) { v = pick(el.getAttribute('data-fill'), s); if (v != null) el.style.fill = v; }
        if (el.hasAttribute('data-stroke')) { v = pick(el.getAttribute('data-stroke'), s); if (v != null) el.style.stroke = v; }
        if (el.hasAttribute('data-tf')) { v = pick(el.getAttribute('data-tf'), s); if (v != null) el.style.transform = v; }
        if (el.hasAttribute('data-op')) { v = pick(el.getAttribute('data-op'), s); if (v != null) el.style.opacity = v; }
      });
    }
    function say(s) {
      var p = panels[s - 1];
      if (!p || !status) return;
      var h = p.querySelector('h4');
      status.innerHTML = '<b>Step ' + s + ' of ' + n + '</b> · ' + esc(h ? h.textContent.replace(/\s*$/, '') : '') + '.';
    }
    function go(s, opts) {
      opts = opts || {};
      step = s;
      fig.setAttribute('data-step', String(s));
      btns.forEach(function (b, i) {
        var on = i + 1 === s;
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
        b.tabIndex = on ? 0 : -1;
      });
      panels.forEach(function (p, i) { p.hidden = i + 1 !== s; });
      chems.forEach(function (c, i) { c.hidden = i + 1 !== s; });
      if (rxs.length) {
        rxs.forEach(function (r, i) { r.hidden = i + 1 !== s; r.classList.remove('run'); });
        var r = rxs[s - 1];
        arr(r.querySelectorAll('svg[data-fit]')).forEach(fit);
        if (opts.user && !reduced()) {
          void r.offsetWidth; r.classList.add('run');
          clearTimeout(runT); runT = setTimeout(function () { r.classList.remove('run'); }, 2800);
        }
      } else apply(s);
      say(s);
      if (opts.focus) btns[s - 1].focus();
    }
    function setPlaying(on) {
      playing = on;
      fig.classList.toggle('is-playing', on);
      playBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
      playBtn.querySelector('span').textContent = on ? 'Pause' : 'Play';
      playBtn.querySelector('path').setAttribute('d', on ? 'M3 2 H6 V12 H3 Z M8 2 H11 V12 H8 Z' : 'M3 1.8 L12 7 L3 12.2 Z');
    }
    function schedule() {
      clear();
      if (!playing) return;
      if (step >= n) { setPlaying(false); return; }
      timers.push(setTimeout(function () { go(step + 1, { user: true }); schedule(); }, stepMs));
    }
    playBtn.addEventListener('click', function () {
      if (playing) { clear(); setPlaying(false); return; }
      players.forEach(function (p) { if (p !== api) p.stop(); });
      setPlaying(true);
      if (step >= n) {
        if (scene) { fig.classList.add('no-tr'); apply(0); void fig.getBoundingClientRect(); fig.classList.remove('no-tr'); }
        timers.push(setTimeout(function () { go(1, { user: true }); schedule(); }, 260));
      } else { go(step, { user: true }); schedule(); }
    });
    btns.forEach(function (b, i) {
      b.addEventListener('click', function () { clear(); setPlaying(false); go(i + 1, { user: true }); });
      b.addEventListener('keydown', function (e) {
        var k = e.key, t = null;
        if (k === 'ArrowRight' || k === 'ArrowDown') t = Math.min(n, i + 2);
        else if (k === 'ArrowLeft' || k === 'ArrowUp') t = Math.max(1, i);
        else if (k === 'Home') t = 1; else if (k === 'End') t = n;
        if (t != null) { e.preventDefault(); clear(); setPlaying(false); go(t, { focus: true, user: true }); }
      });
    });
    var api = { stop: function () { clear(); setPlaying(false); } };
    go(step, {});
    setPlaying(false);
    return api;
  }
  arr(document.querySelectorAll('.rp')).forEach(function (f) { players.push(Player(f)); });

  function bez(x1, y1, x2, y2) {
    function a(p1, p2) { return 1 - 3 * p2 + 3 * p1; } function b(p1, p2) { return 3 * p2 - 6 * p1; } function c(p1) { return 3 * p1; }
    function calc(t, p1, p2) { return ((a(p1, p2) * t + b(p1, p2)) * t + c(p1)) * t; }
    function slope(t, p1, p2) { return 3 * a(p1, p2) * t * t + 2 * b(p1, p2) * t + c(p1); }
    return function (x) { if (x <= 0) return 0; if (x >= 1) return 1; var t = x; for (var i = 0; i < 8; i++) { var s = slope(t, x1, x2); if (s === 0) break; t -= (calc(t, x1, x2) - x) / s; } return calc(t, y1, y2); };
  }
  var inOut = bez(0.65, 0, 0.35, 1), easeOut = bez(0.16, 1, 0.3, 1);

  function initVat(fig) {
    var mv = fig.querySelector('.cl-move'), base = fig.querySelector('.cl-base'), green = fig.querySelector('.cl-green'), blue = fig.querySelector('.cl-blue');
    var s0 = fig.querySelector('.ox0'), s1 = fig.querySelector('.ox1'), z0 = fig.querySelector('.fz0'), z1 = fig.querySelector('.fz1');
    var fzb = arr(fig.querySelectorAll('.fz-b')), fzg = fig.querySelector('.fz-g'), fzbp = arr(fig.querySelectorAll('.fz-bp'));
    var dots = arr(fig.querySelectorAll('.fz-dot')), liq = fig.querySelector('.fz-liq');
    var zc = fig.querySelector('.zl-c'), zl = fig.querySelector('.zl-l');
    var btn = fig.querySelector('.vat-dip'), status = fig.querySelector('.vat-status');
    var vpD = fig.querySelector('.vp-d'), vpN = fig.querySelector('.vp-n');
    var strip = arr(fig.querySelectorAll('.vs'));
    var dipLis = arr(fig.querySelectorAll('.dips li'));
    if (!mv || !btn) return;
    var DIP = 316, SY = 0.6, TOT = 2600;
    var S = { dips: Math.min(4, Math.max(1, +fig.getAttribute('data-dips') || 1)), dy: 0, sy: 1, g: 1, f: 1.08, pose: 'air' };
    var names = { vat: 'In the vat', lifted: 'Lifted', air: 'In the air' };
    var says = { vat: 'Into the vat: the dissolved dye soaks into the fibre.', lifted: 'Lifted out: the cloth is bright green.', air: 'In the air the cloth turns from green to blue, from the top down.' };
    var anim = null;
    function col(n) { return n <= 0 ? 'var(--dye-cloth)' : 'var(--dip-' + n + ')'; }
    function apply() {
      mv.setAttribute('transform', 'translate(0 ' + (S.dy + 64).toFixed(2) + ') scale(1 ' + S.sy.toFixed(4) + ') translate(0 -64)');
      fig.style.setProperty('--dip-c', col(S.dips)); fig.style.setProperty('--dip-c-prev', col(S.dips - 1));
      base.style.fill = col(S.dips - 1); blue.style.fill = col(S.dips);
      green.setAttribute('opacity', S.g.toFixed(3));
      var a = Math.max(0, Math.min(1, S.f - 0.07)), b = Math.max(0, Math.min(1, S.f));
      s0.setAttribute('offset', a.toFixed(4)); s1.setAttribute('offset', b.toFixed(4));
      if (z0) { z0.setAttribute('offset', a.toFixed(4)); z1.setAttribute('offset', b.toFixed(4)); }
      fzb.forEach(function (p) { p.style.stroke = col(S.dips - 1); });
      fzbp.forEach(function (p) { p.style.stroke = col(S.dips); });
      if (fzg) fzg.setAttribute('opacity', S.g.toFixed(3));
      liq.setAttribute('opacity', S.dy > DIP * 0.5 ? '0.45' : '0');
      dots.forEach(function (d) {
        var y = +d.getAttribute('data-y');
        d.classList.toggle('ox', S.f >= 1.07 || (S.f > 0 && y < S.f - 0.04));
      });
      var my = 64 + S.dy + (176 - 64) * S.sy;
      zc.setAttribute('cy', my.toFixed(1)); zl.setAttribute('d', 'M406 ' + (my - 3).toFixed(1) + ' L517 152');
      fig.setAttribute('data-pose', S.pose); fig.setAttribute('data-dips', S.dips);
      strip.forEach(function (li) { if (li.getAttribute('data-pose') === S.pose) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current'); });
      dipLis.forEach(function (li) { li.classList.toggle('on', +li.getAttribute('data-n') === S.dips); });
      vpD.textContent = 'Dip ' + S.dips + ' of 4'; vpN.textContent = names[S.pose];
    }
    function rest() {
      if (S.dips === 1) return 'Dip 1 of 4. In the air the cloth has turned from green to blue.';
      if (S.dips === 4) return 'Dip 4 of 4: the darkest blue. Start again returns to the first dip.';
      return 'Dip ' + S.dips + ' of 4. Each dip deepens the blue.';
    }
    function say(p) { status.textContent = 'Dip ' + S.dips + ' of 4. ' + says[p || S.pose]; }
    function label() { btn.textContent = S.dips >= 4 ? 'Start again' : 'Dip again'; }
    function frame(el) {
      var k;
      if (el < 600) { k = inOut(el / 600); S.dy = DIP * k; S.sy = 1 - (1 - SY) * k; S.g = el < 300 ? 0 : inOut((el - 300) / 300); S.f = -0.1; S.pose = 'vat'; }
      else if (el < 1100) { k = el < 850 ? easeOut((el - 600) / 250) : 1; S.dy = DIP * (1 - k); S.sy = SY + (1 - SY) * k; S.g = 1; S.f = -0.1; S.pose = 'lifted'; }
      else { k = inOut(Math.min(1, (el - 1100) / 1500)); S.dy = 0; S.sy = 1; S.g = 1; S.f = -0.1 + 1.18 * k; S.pose = 'air'; }
    }
    function finish() { S.dy = 0; S.sy = 1; S.g = 1; S.f = 1.08; S.pose = 'air'; anim = null; apply(); status.textContent = rest(); label(); }
    function step(now) {
      if (!anim) return;
      var el = now - anim.t0;
      var prev = S.pose;
      if (el >= TOT) { finish(); return; }
      frame(el); apply();
      if (S.pose !== prev) say();
      requestAnimationFrame(step);
    }
    btn.addEventListener('click', function () {
      if (anim) finish();
      S.dips = S.dips >= 4 ? 1 : S.dips + 1;
      if (reduced()) { finish(); return; }
      anim = { t0: performance.now() };
      frame(0); apply(); say('vat');
      requestAnimationFrame(step);
    });
    apply(); label();
  }
  arr(document.querySelectorAll('figure.vat')).forEach(function (f) { if (!f.closest('[inert]')) initVat(f); });

  var molData = {};
  try { molData = JSON.parse(document.getElementById('mol-data').textContent); } catch (e) {}
  var RAD = { C: 0.38, N: 0.36, O: 0.36, H: 0.2 };
  function Viewer(fig) {
    var m = molData[fig.getAttribute('data-cid')];
    if (!m) return null;
    var dial = fig.querySelector('.mol-dial');
    var svg = dial.querySelector('svg');
    var g = svg.querySelector('g.mol-g');
    var yaw = +fig.getAttribute('data-yaw'), pitch = +fig.getAttribute('data-pitch');
    var atomEls = [], bondEls = [];
    arr(g.children).forEach(function (el) {
      if (el.hasAttribute('data-a')) {
        var i = +el.getAttribute('data-a');
        atomEls[i] = { g: el, c: el.querySelector('circle:not(.mol-ring)'), r: el.querySelector('.mol-ring'), t: el.querySelector('text') };
      } else if (el.hasAttribute('data-b')) bondEls[+el.getAttribute('data-b')] = el;
    });
    var order = arr(g.children);
    var s = 0.95 / m.R, bw = 0.11 * s;
    function f3(v) { return Math.round(v * 1000) / 1000; }
    function draw() {
      var cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
      var P = m.atoms.map(function (a) {
        var x1 = cy * a[1] + sy * a[3], z1 = -sy * a[1] + cy * a[3];
        return [a[0], x1, cp * a[2] - sp * z1, sp * a[2] + cp * z1];
      });
      var unit = 2 / Math.max(1, svg.getBoundingClientRect().width);
      var minLetter = 12 * unit;
      var items = [];
      P.forEach(function (p, i) {
        var e = atomEls[i]; if (!e) return;
        var k = 1 + p[3] * s * 0.14, r = (RAD[p[0]] || 0.36) * s * k;
        var cx = f3(p[1] * s), cyy = f3(-p[2] * s);
        e.c.setAttribute('cx', cx); e.c.setAttribute('cy', cyy); e.c.setAttribute('r', f3(r));
        if (e.r) { e.r.setAttribute('cx', cx); e.r.setAttribute('cy', cyy); e.r.setAttribute('r', f3(r + 0.05)); }
        if (e.t) {
          var fs = Math.max(r * 1.15, minLetter);
          e.t.setAttribute('x', cx); e.t.setAttribute('y', cyy); e.t.setAttribute('font-size', f3(fs));
          e.t.style.display = fs > r * 2.3 ? 'none' : '';
        }
        items.push([p[3], e.g]);
      });
      m.bonds.forEach(function (b, j) {
        var el = bondEls[j]; if (!el) return;
        var p = P[b[0]], q = P[b[1]];
        var x1 = p[1] * s, y1 = -p[2] * s, x2 = q[1] * s, y2 = -q[2] * s;
        if (b[2] === 2) {
          var dx = x2 - x1, dy = y2 - y1, L = Math.sqrt(dx * dx + dy * dy) || 1, ox = -dy / L * 0.07 * s, oy = dx / L * 0.07 * s;
          el.setAttribute('d', 'M' + f3(x1 + ox) + ' ' + f3(y1 + oy) + 'L' + f3(x2 + ox) + ' ' + f3(y2 + oy) + 'M' + f3(x1 - ox) + ' ' + f3(y1 - oy) + 'L' + f3(x2 - ox) + ' ' + f3(y2 - oy));
        } else el.setAttribute('d', 'M' + f3(x1) + ' ' + f3(y1) + 'L' + f3(x2) + ' ' + f3(y2));
        items.push([(p[3] + q[3]) / 2 - 0.08, el]);
      });
      items.sort(function (a, b) { return a[0] - b[0]; });
      var changed = false;
      for (var i = 0; i < items.length; i++) if (order[i] !== items[i][1]) { changed = true; break; }
      if (changed) { items.forEach(function (it) { g.appendChild(it[1]); }); order = items.map(function (it) { return it[1]; }); }
      var deg = ((Math.round(yaw * 180 / Math.PI) % 360) + 360) % 360;
      dial.setAttribute('aria-valuenow', String(deg)); dial.setAttribute('aria-valuetext', 'Turned ' + deg + ' degrees');
    }
    var anim = 0, pending = false;
    function req() { if (pending) return; pending = true; requestAnimationFrame(function () { pending = false; draw(); }); }
    function turn(total, ms) {
      cancelAnimationFrame(anim);
      if (reduced()) { yaw += Math.PI / 2; draw(); return; }
      var y0 = yaw, t0 = 0;
      function fr(now) {
        if (!t0) t0 = now;
        var k = Math.min(1, (now - t0) / ms);
        yaw = y0 + total * inOut(k); draw();
        if (k < 1) anim = requestAnimationFrame(fr);
      }
      anim = requestAnimationFrame(fr);
    }
    var drag = null;
    dial.addEventListener('pointerdown', function (e) { cancelAnimationFrame(anim); drag = [e.clientX, e.clientY]; try { dial.setPointerCapture(e.pointerId); } catch (x) {} });
    dial.addEventListener('pointermove', function (e) {
      if (!drag) return;
      yaw += (e.clientX - drag[0]) * 0.012; pitch = Math.max(-1.5, Math.min(1.5, pitch + (e.clientY - drag[1]) * 0.012));
      drag = [e.clientX, e.clientY]; req();
    });
    function end() { drag = null; }
    dial.addEventListener('pointerup', end); dial.addEventListener('pointercancel', end);
    dial.addEventListener('keydown', function (e) {
      var d = { ArrowLeft: [-Math.PI / 12, 0], ArrowRight: [Math.PI / 12, 0], ArrowUp: [0, -0.2], ArrowDown: [0, 0.2], PageUp: [Math.PI / 2, 0], PageDown: [-Math.PI / 2, 0] }[e.key];
      if (e.key === 'Home') { e.preventDefault(); yaw = 0; draw(); return; }
      if (e.key === 'End') { e.preventDefault(); yaw = Math.PI * 359 / 180; draw(); return; }
      if (!d) return;
      e.preventDefault(); cancelAnimationFrame(anim);
      yaw += d[0]; pitch = Math.max(-1.5, Math.min(1.5, pitch + d[1])); draw();
    });
    var tb = fig.querySelector('.mol-turn');
    if (tb) tb.addEventListener('click', function () { turn(Math.PI * 2, 2400); });
    if ('ResizeObserver' in window) new ResizeObserver(function () { req(); }).observe(dial);
    draw();
    return { draw: draw };
  }
  arr(document.querySelectorAll('.mol[data-cid]')).forEach(function (f) { if (!f.closest('[inert]')) KV.near(f, function () { Viewer(f); }, 600); });

  var subLinks = arr(document.querySelectorAll('.subrail a'));
  if ('IntersectionObserver' in window && subLinks.length) {
    var sio = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        subLinks.forEach(function (a) { if (a.getAttribute('href') === '#' + en.target.id) { subLinks.forEach(function (o) { o.removeAttribute('aria-current'); }); a.setAttribute('aria-current', 'location'); } });
      });
    }, { rootMargin: '-25% 0px -65% 0px' });
    subLinks.forEach(function (a) { var t = document.querySelector(a.getAttribute('href')); if (t) sio.observe(t); });
  }

  arr(document.querySelectorAll('.src[data-src]')).forEach(function (b) {
    b.addEventListener('click', function () {
      var on = b.getAttribute('aria-pressed') !== 'true';
      var scope = b.closest('.screen');
      arr(scope.querySelectorAll('.src[aria-pressed="true"]')).forEach(function (o) { o.setAttribute('aria-pressed', 'false'); });
      arr(scope.querySelectorAll('.s.is-src')).forEach(function (s) { s.classList.remove('is-src'); });
      if (!on) return;
      b.setAttribute('aria-pressed', 'true');
      var key = b.getAttribute('data-src');
      arr(scope.querySelectorAll('.s[data-src]')).forEach(function (s) {
        if ((' ' + s.getAttribute('data-src') + ' ').indexOf(' ' + key + ' ') !== -1) s.classList.add('is-src');
      });
    });
  });
})();

});
KV.boot('pt', function (document) {
(function () {
  var root = document.documentElement;
  var osReduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  function reduced() { return osReduce.matches || root.getAttribute('data-reduced-motion') === 'true'; }
  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function all(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  var EASE = 'cubic-bezier(0.65, 0, 0.35, 1)';

  var themeBtn = document.getElementById('theme-toggle');
  function effectiveTheme() {
    var t = root.getAttribute('data-theme');
    if (t === 'light' || t === 'dark') return t;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  function paintTheme() { themeBtn.setAttribute('aria-pressed', effectiveTheme() === 'dark' ? 'true' : 'false'); }
  themeBtn.addEventListener('click', function () {
    var next = effectiveTheme() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next); store('kv-theme', next); paintTheme();
  });
  paintTheme();
  [['motion-toggle', 'data-reduced-motion', 'kv-motion'], ['contrast-toggle', 'data-high-contrast', 'kv-contrast'], ['text-toggle', 'data-larger-text', 'kv-text']].forEach(function (t) {
    var b = document.getElementById(t[0]);
    if (!b) return;
    function paint() { b.setAttribute('aria-pressed', root.getAttribute(t[1]) === 'true' ? 'true' : 'false'); }
    b.addEventListener('click', function () {
      var on = root.getAttribute(t[1]) === 'true';
      if (on) root.removeAttribute(t[1]); else root.setAttribute(t[1], 'true');
      store(t[2], on ? '' : 'true'); paint();
    });
    paint();
  });

  var qBtn = document.querySelector('.q-more'), qH = document.querySelector('.q-h1');
  if (qBtn && qH) {
    qBtn.addEventListener('click', function () {
      var open = !qH.classList.contains('is-open');
      qH.classList.toggle('is-open', open);
      qBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      qBtn.textContent = open ? 'Show less of the question' : 'Show the full question';
    });
  }

  function fitSvg(svg) {
    var vb = svg.viewBox && svg.viewBox.baseVal;
    if (!vb || !vb.width) return;
    var r = svg.getBoundingClientRect();
    if (!r.width || !r.height) return;
    var kx = vb.width / r.width, ky = vb.height / r.height;
    var k = (svg.getAttribute('preserveAspectRatio') || '').indexOf('slice') >= 0 ? Math.min(kx, ky) : Math.max(kx, ky);
    svg.style.setProperty('--k', k.toFixed(4));
  }
  var fitList = all('svg[data-fit]');
  fitList.forEach(fitSvg);
  if ('ResizeObserver' in window) { var fro = new ResizeObserver(function (es) { es.forEach(function (e) { fitSvg(e.target); }); }); fitList.forEach(function (s) { fro.observe(s); }); }

  var data = { sources: {}, claims: {}, rel: {} };
  try { data = JSON.parse(document.getElementById('cite-data').textContent); } catch (e) {}
  var pop = document.getElementById('pop');
  var scrim = document.getElementById('scrim');
  var current = null;
  function build(btn) {
    var nums = {};
    btn.getAttribute('data-n').split(',').forEach(function (pair) { var b = pair.split('='); nums[b[0]] = +b[1]; });
    var bySource = {};
    btn.getAttribute('data-claims').split(' ').forEach(function (cid) {
      (data.claims[cid] || []).forEach(function (q) { (bySource[q[0]] = bySource[q[0]] || []).push(q); });
    });
    var order = Object.keys(bySource).sort(function (a, b) { return nums[a] - nums[b]; });
    var out = '<div class="pop-head"><p id="pop-title">' + (order.length === 1 ? 'Source' : order.length + ' sources') + ' for this sentence</p>' +
      '<button class="pop-close" type="button" aria-label="Close"><svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2 2 L12 12 M12 2 L2 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button></div>';
    order.forEach(function (sk) {
      var s = data.sources[sk] || {};
      var seen = {};
      out += '<div class="pop-src"><div class="pop-src-h"><b>' + nums[sk] + '</b><strong>' + esc(s.t || sk) + '</strong></div>' +
        '<p class="pop-by">' + esc(s.by || '') + (s.y ? ', ' + s.y : '') + '</p>' + (s.sc ? '<p class="pop-sc">' + esc(s.sc) + '</p>' : '');
      bySource[sk].forEach(function (q) {
        if (seen[q[2]]) return; seen[q[2]] = 1;
        out += '<p class="pop-q">“' + esc(q[2]) + '”</p>' + (q[1] ? '<p class="pop-loc">' + esc(q[1]) + '</p>' : '');
      });
      out += '<p class="pop-rel"><span class="rel ' + esc(s.r) + '" aria-hidden="true"></span>Reliability ' + esc(s.r) + ' · ' + esc((data.rel || {})[s.r] || '') + '</p>';
      if (s.u) out += '<p class="pop-loc"><a href="' + esc(s.u) + '" rel="noopener" target="_blank">Open the source</a></p>';
      out += '</div>';
    });
    out += '<p class="pop-foot">Quotes are verbatim.</p>';
    return out;
  }
  function place(btn) {
    var vw = document.documentElement.clientWidth;
    var vh = window.innerHeight;
    var r = btn.getBoundingClientRect();
    var sx = window.scrollX || window.pageXOffset, sy = window.scrollY || window.pageYOffset;
    pop.classList.remove('sheet');
    pop.style.left = pop.style.top = pop.style.width = pop.style.maxHeight = '';
    if (vw < 640 || btn.closest('.pf-screen')) {
      pop.classList.add('sheet'); pop.setAttribute('aria-modal', 'true'); scrim.hidden = false; return;
    }
    pop.setAttribute('aria-modal', 'false'); scrim.hidden = true;
    var spread = btn.closest('.spread');
    var margin = spread && spread.querySelector(':scope > .margin');
    var top, left, width;
    if (vw >= 1200 && margin && margin.offsetParent !== null) {
      var m = margin.getBoundingClientRect();
      width = Math.min(300, m.right - 8); left = m.right - width + sx; top = r.top - 14;
    } else {
      width = Math.min(380, vw - 32); left = Math.max(16, Math.min(r.left + sx - 24, sx + vw - width - 16)); top = r.bottom + 10;
    }
    var maxH = Math.max(240, vh - 32);
    pop.style.width = width + 'px'; pop.style.left = left + 'px'; pop.style.maxHeight = maxH + 'px';
    var h = Math.min(pop.scrollHeight, maxH);
    if (top + h > vh - 16) top = Math.max(16, vh - 16 - h);
    pop.style.top = (top + sy) + 'px';
  }
  function focusables(el) { return all('button, a[href], [tabindex="0"], input, select, summary', el).filter(function (n) { return n.offsetParent !== null && !n.disabled; }); }
  function close(returnFocus) {
    if (!current) return;
    var btn = current;
    btn.setAttribute('aria-expanded', 'false');
    var s = btn.closest('.s'); if (s) s.classList.remove('is-lit');
    pop.hidden = true; pop.classList.remove('is-open'); scrim.hidden = true;
    if (returnFocus) btn.focus({ preventScroll: true });
    current = null;
    return btn;
  }
  function open(btn, focus) {
    if (current === btn) { close(true); return; }
    close(false);
    current = btn;
    pop.innerHTML = build(btn);
    pop.hidden = false;
    place(btn);
    pop.classList.remove('is-open'); void pop.offsetWidth; pop.classList.add('is-open');
    btn.classList.remove('press'); void btn.offsetWidth; if (!reduced()) btn.classList.add('press');
    btn.setAttribute('aria-expanded', 'true');
    var s = btn.closest('.s'); if (s) s.classList.add('is-lit');
    pop.querySelector('.pop-close').addEventListener('click', function () { close(true); });
    if (focus) pop.focus({ preventScroll: true });
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.cite');
    if (btn) { e.preventDefault(); open(btn, true); return; }
    if (current && !pop.contains(e.target)) close(false);
  });
  scrim.addEventListener('click', function () { close(true); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && current) { close(true); return; }
    if (e.key !== 'Tab' || !current) return;
    var f = focusables(pop);
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1], act = document.activeElement;
    if (pop.classList.contains('sheet')) {
      if (e.shiftKey && (act === first || act === pop)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && act === last) { e.preventDefault(); first.focus(); }
      return;
    }
    if (!pop.contains(act)) return;
    if (e.shiftKey && (act === first || act === pop)) { e.preventDefault(); close(true); return; }
    if (!e.shiftKey && act === last) {
      e.preventDefault();
      var btn = close(false);
      var seq = focusables(document.body).filter(function (n) { return !pop.contains(n); });
      var i = seq.indexOf(btn);
      (seq[i + 1] || btn).focus();
    }
  });
  window.addEventListener('resize', function () { if (current) place(current); });

  function fitVB(b, aspect) {
    var w = b[2], h = b[3], cx = b[0] + w / 2, cy = b[1] + h / 2;
    if (w / h > aspect) h = w / aspect; else w = h * aspect;
    return [cx - w / 2, cy - h / 2, w, h];
  }
  function camera(svg, box, onApply) {
    var cam = svg.querySelector('.cam');
    var st = { vb: null, t: null };
    function apply(vb) {
      st.vb = vb;
      svg.setAttribute('viewBox', vb.map(function (v) { return v.toFixed(2); }).join(' '));
      var px = box.getBoundingClientRect().width || 600;
      svg.style.setProperty('--k', (vb[2] / px).toFixed(4));
      if (onApply) onApply(vb, vb[2] / px);
    }
    function go(target, animate) {
      var r = box.getBoundingClientRect();
      var to = fitVB(target, r.width && r.height ? r.width / r.height : 1);
      clearTimeout(st.t);
      var from = st.vb;
      if (!animate || reduced() || !from) { cam.classList.remove('glide'); cam.style.transform = ''; svg.classList.remove('is-moving'); apply(to); return; }
      var s = to[2] / from[2];
      var tx = to[0] - from[0] * s, ty = to[1] - from[1] * s;
      cam.classList.remove('glide');
      apply(to);
      cam.style.transform = 'matrix(' + s + ',0,0,' + s + ',' + tx + ',' + ty + ')';
      svg.classList.add('is-moving');
      void cam.getBoundingClientRect();
      cam.classList.add('glide');
      cam.style.transform = 'matrix(1,0,0,1,0,0)';
      st.t = setTimeout(function () { cam.classList.remove('glide'); cam.style.transform = ''; svg.classList.remove('is-moving'); }, 1040);
    }
    return { go: go, state: st };
  }

  function clothSVG(n, green) {
    var t = green ? 'tile-g' : 'tile-' + n, b = green ? 'brd-g' : 'brd-' + n;
    return '<rect width="1200" height="540" fill="url(#' + t + ')"/>' +
      '<g transform="translate(44 0) rotate(90)"><rect width="540" height="44" fill="url(#' + b + ')"/></g>' +
      '<g transform="translate(1156 540) rotate(-90)"><rect width="540" height="44" fill="url(#' + b + ')"/></g>' +
      '<rect width="1200" height="44" fill="url(#' + b + ')"/><rect y="496" width="1200" height="44" fill="url(#' + b + ')"/>' +
      '<path d="M0 44.5 H1200 M0 495.5 H1200 M44.5 44 V496 M1155.5 44 V496" stroke="var(--dye-kut)" stroke-opacity=".55" stroke-width="1"/>' +
      '<rect width="1200" height="540" fill="url(#weave)"/>';
  }
  var clothApi = {};
  all('[data-comp="cloth"]').forEach(function (lc) {
    var stages = JSON.parse(lc.getAttribute('data-stages'));
    var svg = lc.querySelector('.lc-bsvg');
    var L = { base: svg.querySelector('[data-l="base"]'), top: svg.querySelector('[data-l="top"]'), ox: svg.querySelector('[data-l="ox"]') };
    var dipg = svg.querySelector('.dipg'), oxg = svg.querySelector('.oxg'), title = svg.querySelector('title');
    var btns = all('.rb', lc), items = all('.lc-step', lc);
    var kEl = lc.querySelector('[data-k]'), hEl = lc.querySelector('[data-h]'), aEl = lc.querySelector('[data-a]'), live = lc.querySelector('[data-live]'), playBtn = lc.querySelector('[data-play]');
    var cur = +lc.getAttribute('data-rest'), timers = [], playing = false, paused = false, pt = null;
    function mask(g, y, ms) { g.style.transition = ms ? 'transform ' + ms + 'ms ' + EASE : 'none'; g.style.transform = 'translate(0px, ' + y + 'px)'; }
    function reset() { timers.forEach(clearTimeout); timers = []; L.top.innerHTML = ''; L.ox.innerHTML = ''; mask(dipg, 600, 0); mask(oxg, -20, 0); }
    function label(n) {
      var s = stages[n - 1];
      kEl.textContent = 'Stage ' + n + ' of 11';
      hEl.innerHTML = s.local ? '<i>' + esc(s.name) + '</i><span>' + esc(s.eng) + '</span>' : '<span class="nolocal">' + esc(s.eng) + '</span>';
      aEl.textContent = s.after;
      title.textContent = 'The cloth after stage ' + n + ', ' + s.name + ': ' + s.after;
      btns.forEach(function (b) { var on = +b.getAttribute('data-go') === n; b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.tabIndex = on ? 0 : -1; });
      items.forEach(function (it) { if (+it.getAttribute('data-stage') === n) it.setAttribute('aria-current', 'step'); else it.removeAttribute('aria-current'); });
    }
    function say(n, extra) { var s = stages[n - 1]; live.textContent = (extra || '') + 'Stage ' + n + ' of 11, ' + s.name + ': ' + s.after + '.'; }
    function setStage(n, animate, extra) {
      reset();
      var prev = cur; cur = n;
      label(n); say(n, extra);
      if (!animate || reduced()) { L.base.innerHTML = clothSVG(n); return 0; }
      if (n === 8) {
        L.top.innerHTML = clothSVG(8, true); mask(dipg, 600, 0); void svg.getBoundingClientRect(); mask(dipg, 0, 600);
        timers.push(setTimeout(function () {
          L.ox.innerHTML = clothSVG(8); mask(oxg, -20, 0); void svg.getBoundingClientRect(); mask(oxg, 580, 1500);
        }, 1100));
        timers.push(setTimeout(function () { L.base.innerHTML = clothSVG(8); L.top.innerHTML = ''; L.ox.innerHTML = ''; mask(dipg, 600, 0); mask(oxg, -20, 0); }, 2650));
        return 2600;
      }
      L.top.innerHTML = clothSVG(n); mask(dipg, 600, 0); void svg.getBoundingClientRect(); mask(dipg, 0, 600);
      timers.push(setTimeout(function () { L.base.innerHTML = clothSVG(n); L.top.innerHTML = ''; mask(dipg, 600, 0); }, 660));
      return 600;
    }
    L.base.innerHTML = clothSVG(cur); reset(); label(cur);
    function stopPlay(msg) {
      playing = false; clearTimeout(pt);
      playBtn.setAttribute('aria-pressed', 'false'); playBtn.querySelector('span').textContent = 'Play the stages';
      playBtn.querySelector('svg').innerHTML = '<path d="M3 2 L12 7 L3 12 Z" fill="currentColor"/>';
      if (msg) live.textContent = msg;
    }
    function step() {
      if (!playing) return;
      if (cur >= 11) { stopPlay('Played all eleven stages.'); return; }
      var d = setStage(cur + 1, true, 'Playing. ');
      pt = setTimeout(step, Math.max(d, 600) + 900);
    }
    playBtn.addEventListener('click', function () {
      if (playing) { stopPlay('Paused at stage ' + cur + '.'); paused = true; return; }
      var resume = paused; paused = false; playing = true;
      playBtn.setAttribute('aria-pressed', 'true'); playBtn.querySelector('span').textContent = 'Pause';
      playBtn.querySelector('svg').innerHTML = '<path d="M3 2 H6 V12 H3 Z M8 2 H11 V12 H8 Z" fill="currentColor"/>';
      if (!resume || cur >= 11) { setStage(1, false, 'Playing. '); pt = setTimeout(step, 1200); } else step();
    });
    btns.forEach(function (b, i) {
      b.addEventListener('click', function () { if (playing) stopPlay(); paused = false; setStage(+b.getAttribute('data-go'), true); });
      b.addEventListener('keydown', function (e) {
        var n = null;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') n = Math.min(btns.length - 1, i + 1);
        else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') n = Math.max(0, i - 1);
        else if (e.key === 'Home') n = 0; else if (e.key === 'End') n = btns.length - 1;
        if (n === null) return;
        e.preventDefault(); if (playing) stopPlay();
        btns[n].focus(); setStage(n + 1, true);
      });
    });
    clothApi[lc.id] = { go: function (n) { if (playing) stopPlay(); setStage(n, true); } };
  });
  all('[data-goto-stage]').forEach(function (b) {
    b.addEventListener('click', function () {
      var api = clothApi['a-lc'];
      var fig = document.getElementById('a-lc');
      if (!api || !fig) return;
      fig.scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'start' });
      setTimeout(function () { api.go(+b.getAttribute('data-goto-stage')); }, reduced() ? 0 : 500);
    });
  });

  var RS = null;
  try { RS = JSON.parse(document.getElementById('rs-data').textContent); } catch (e) {}
  all('[data-comp="region"]').forEach(function (rs) { KV.near(rs, function () {
    if (!RS) return;
    var svg = rs.querySelector('svg.geo');
    var mapEl = rs.querySelector('.rs-map');
    var tip = rs.querySelector('.rs-tip');
    var inBox = rs.querySelector('.in-box');
    var salt = svg.querySelector('.saltpat');
    var legend = rs.querySelector('[data-legend]');
    var live = rs.querySelector('[data-map-live]');
    var ovH = svg.querySelector('.ovl-halo'), ovL = svg.querySelector('.ovl-line');
    var rankT = rs.querySelector('[data-rank]'), rankCap = rs.querySelector('[data-rank-cap]'), rankSrc = rs.querySelector('[data-rank-src]'), rankAll = rs.querySelector('[data-rank-all]');
    var layerBtns = all('[data-layer]', rs), zoomBtns = all('[data-z]', rs);
    var dists = all('.dist', svg), dlabs = all('.dlab', svg);
    var pre = rs.id.replace('-rs', '');
    var state = { zoom: 'region', layer: 'rain', rankOpen: false, kf: -1, order: [] };
    var cam = camera(svg, mapEl, function (vb, k) {
      if (salt) salt.setAttribute('patternTransform', 'scale(' + k.toFixed(4) + ')');
      var iv = RS.views.india;
      inBox.setAttribute('x', vb[0]); inBox.setAttribute('y', vb[1]);
      inBox.setAttribute('width', Math.min(vb[2], iv[2])); inBox.setAttribute('height', Math.min(vb[3], iv[3]));
    });
    function setZoom(z, animate) {
      state.zoom = z;
      svg.setAttribute('data-zoom', z);
      rs.setAttribute('data-zoomnow', z);
      zoomBtns.forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-z') === z ? 'true' : 'false'); });
      cam.go(RS.views[z], animate);
    }
    function fmtV(L, v) {
      var s = L.nd === 0 ? Math.round(v).toLocaleString('en-IN') : v.toFixed(L.nd);
      if (L.plus && v > 0) s = '+' + s;
      return L.pre ? 'pH ' + s : s + ' ' + L.unit;
    }
    function shortV(L, v) {
      var s = L.nd === 0 ? String(Math.round(v)) : v.toFixed(L.nd);
      if (L.plus && v > 0) s = '+' + s;
      return s;
    }
    function renderLegend(L) {
      var ticks = [];
      for (var i = 0; i < L.steps.length; i++) {
        var lo = i === 0 ? null : L.breaks[i - 1], hi = i < L.breaks.length ? L.breaks[i] : null;
        ticks.push(lo === null ? '< ' + hi : (hi === null ? lo + ' +' : String(lo)));
      }
      legend.innerHTML = '<span class="lg-title">' + esc(L.title) + ', ' + esc(L.unit) + '</span><span><span class="lg-ramp">' +
        L.steps.map(function (s) { return '<span style="background:var(--' + L.ramp + '-' + s + ')"></span>'; }).join('') + '</span><span class="lg-ticks">' +
        ticks.map(function (t) { return '<span>' + t + '</span>'; }).join('') + '</span></span>' +
        '<span class="lg-item"><span class="lg-k"></span>Kachchh</span><span class="lg-item"><span class="lg-sw" style="background:var(--map-salt);background-image:radial-gradient(var(--map-salt-hatch) 0.7px,transparent 0.9px);background-size:4px 4px"></span>Salt flat</span>' +
        '<span class="lg-item"><span class="lg-line"></span>Suran, dry</span>';
    }
    function rows(L) {
      var r = Object.keys(L.values).map(function (k) { return [+k, L.values[k]]; });
      r.sort(function (x, y) { return L.order === 'desc' ? y[1] - x[1] : x[1] - y[1]; });
      return r;
    }
    function renderRank(L) {
      var rr = rows(L);
      state.order = rr.map(function (r) { return r[0]; });
      var vals = rr.map(function (r) { return r[1]; });
      var mx = Math.max.apply(null, vals), mn = Math.min.apply(null, vals);
      var lo = L.pre ? mn - 0.4 : 0;
      var ki = state.order.indexOf(449);
      var html = '<thead class="vh"><tr><th scope="col">District</th><th scope="col">Value</th><th scope="col">Bar</th></tr></thead><tbody>';
      rr.forEach(function (r, i) {
        var near = Math.abs(i - ki) <= 4;
        var w = Math.max(2, (r[1] - lo) / (mx - lo) * 100);
        html += '<tr' + (r[0] === 449 ? ' class="k"' : '') + (near || state.rankOpen ? '' : ' hidden') + '><th scope="row">' + (i + 1) + '. ' + esc(L.names[r[0]]) + '<small>' + esc(L.states[r[0]]) + '</small></th><td class="v">' + fmtV(L, r[1]) + '</td><td class="bar"><i style="width:' + w.toFixed(1) + '%"></i></td></tr>';
      });
      rankT.innerHTML = html + '</tbody>';
      rankCap.textContent = L.finding;
      rankSrc.textContent = L.src;
      rankAll.textContent = state.rankOpen ? 'Show the nine around Kachchh' : 'Show all 27';
      rankAll.setAttribute('aria-expanded', state.rankOpen ? 'true' : 'false');
    }
    function setLayer(id) {
      state.layer = id;
      var L = RS.layers[id];
      svg.setAttribute('data-layer', id);
      layerBtns.forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-layer') === id ? 'true' : 'false'); });
      dists.forEach(function (p) { var c = L.cls[p.getAttribute('data-lgd')]; p.style.fill = c ? 'var(--' + L.ramp + '-' + c + ')' : ''; });
      dlabs.forEach(function (g) { var v = L.values[g.getAttribute('data-lgd')]; g.querySelector('[data-v]').textContent = v == null ? '' : shortV(L, v); });
      renderLegend(L); renderRank(L);
      if (state.kf >= 0) focusDist(state.kf, false);
    }
    layerBtns.forEach(function (b) { b.addEventListener('click', function () { setLayer(b.getAttribute('data-layer')); }); });
    zoomBtns.forEach(function (b) { b.addEventListener('click', function () { setZoom(b.getAttribute('data-z'), true); }); });
    rankAll.addEventListener('click', function () { state.rankOpen = !state.rankOpen; renderRank(RS.layers[state.layer]); });
    function tipFor(lgd, x, y) {
      var L = RS.layers[state.layer];
      tip.innerHTML = '<b>' + esc(L.names[lgd]) + '</b><span>' + esc(L.states[lgd]) + ' · ' + fmtV(L, L.values[lgd]) + (L.p ? ' · p = ' + L.p[lgd] : '') + '</span>';
      tip.hidden = false;
      var mr = mapEl.getBoundingClientRect();
      var tw = tip.offsetWidth, th = tip.offsetHeight;
      tip.style.left = Math.max(6, Math.min(mr.width - tw - 6, x + 12)) + 'px';
      tip.style.top = Math.max(6, Math.min(mr.height - th - 6, y + 12)) + 'px';
    }
    function focusDist(i, announce) {
      state.kf = i;
      var lgd = state.order[i];
      var p = svg.getElementById ? svg.getElementById(pre + '-d-' + lgd) : document.getElementById(pre + '-d-' + lgd);
      if (!p) return;
      [ovH, ovL].forEach(function (u) { u.setAttribute('href', '#' + pre + '-d-' + lgd); u.style.display = ''; });
      var br = p.getBoundingClientRect(), mr = mapEl.getBoundingClientRect();
      var cx = Math.max(10, Math.min(mr.width - 10, br.left + br.width / 2 - mr.left)), cy = Math.max(10, Math.min(mr.height - 10, br.top + br.height / 2 - mr.top));
      tipFor(String(lgd), cx, cy);
      if (announce) { var L = RS.layers[state.layer]; live.textContent = (i + 1) + ' of 27. ' + L.names[lgd] + ', ' + L.states[lgd] + ': ' + fmtV(L, L.values[lgd]); }
    }
    function clearFocus() { state.kf = -1; tip.hidden = true; [ovH, ovL].forEach(function (u) { u.style.display = 'none'; }); }
    mapEl.addEventListener('keydown', function (e) {
      var n = state.kf;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') n = n < 0 ? state.order.indexOf(449) : Math.min(26, n + 1);
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') n = n < 0 ? state.order.indexOf(449) : Math.max(0, n - 1);
      else if (e.key === 'Home') n = 0; else if (e.key === 'End') n = 26;
      else if (e.key === 'Escape') { clearFocus(); return; }
      else return;
      e.preventDefault(); focusDist(n, true);
    });
    mapEl.addEventListener('blur', clearFocus);
    dists.forEach(function (p) {
      p.addEventListener('pointermove', function (e) { var mr = mapEl.getBoundingClientRect(); tipFor(p.getAttribute('data-lgd'), e.clientX - mr.left, e.clientY - mr.top); });
      p.addEventListener('pointerleave', function () { if (state.kf < 0) tip.hidden = true; });
    });
    setLayer('rain');
    setZoom('region', false);
    if ('ResizeObserver' in window) new ResizeObserver(function () { if (!svg.classList.contains('is-moving')) cam.go(RS.views[state.zoom], false); }).observe(mapEl);
  });

  all('[data-comp="rain"]').forEach(function (box) {
    var ser = JSON.parse(box.getAttribute('data-series'));
    var bars = all('rect.bar', box), hits = all('rect.hit', box);
    var tip = box.querySelector('.r2-tip');
    var sel = -1;
    function show(i) {
      if (sel >= 0) bars[sel].classList.remove('hl');
      sel = i;
      if (i < 0) { tip.hidden = true; return; }
      bars[i].classList.add('hl');
      tip.innerHTML = '<b>' + ser[i][0] + '</b> · ' + ser[i][1] + ' mm';
      tip.hidden = false;
      var x = (i + 0.5) / ser.length * 100, y = (1 - ser[i][1] / 900) * 100;
      tip.style.left = x + '%'; tip.style.top = y + '%';
    }
    hits.forEach(function (h) {
      h.addEventListener('pointerenter', function () { show(+h.getAttribute('data-i')); });
      h.addEventListener('click', function () { show(+h.getAttribute('data-i')); });
    });
    box.addEventListener('pointerleave', function () { if (document.activeElement !== box) show(-1); });
    box.addEventListener('focus', function () { if (sel < 0) show(ser.length - 1); });
    box.addEventListener('blur', function () { show(-1); });
    box.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault();
        var n = sel < 0 ? 0 : sel + (e.key === 'ArrowRight' ? 1 : -1);
        show(Math.max(0, Math.min(ser.length - 1, n)));
      } else if (e.key === 'Home') { e.preventDefault(); show(0); } else if (e.key === 'End') { e.preventDefault(); show(ser.length - 1); } else if (e.key === 'Escape') { show(-1); }
    });
  });

  all('[data-comp="time"]').forEach(function (tl) { KV.near(tl, function () {
    var evs = JSON.parse(tl.getAttribute('data-events'));
    var svg = tl.querySelector('svg.geo');
    var mapEl = tl.querySelector('.tl-map');
    var views = JSON.parse(mapEl.getAttribute('data-views'));
    var salt = svg.querySelector('.saltpat'), hatch = svg.querySelector('.hatchpat');
    var axisBtns = all('.tl-axis .ev', tl), cards = all('[data-evc]', tl), lis = all('.tl-li', tl), picks = all('.tl-pick', tl);
    var playBtn = tl.querySelector('[data-play]'), status = tl.querySelector('[data-tl-status]');
    var supBtn = tl.querySelector('[data-supply]'), supNote = tl.querySelector('[data-supply-note]');
    var st = { i: -1, playing: false, timer: null, view: 'corridor' };
    var cam = camera(svg, mapEl, function (vb, k) {
      if (salt) salt.setAttribute('patternTransform', 'scale(' + (k * 0.6).toFixed(4) + ')');
      if (hatch) hatch.setAttribute('patternTransform', 'rotate(45) scale(' + (k * 1.0).toFixed(4) + ')');
    });
    function zoomTo(name, animate) { st.view = name; svg.setAttribute('data-zoom', name); cam.go(views[name], animate); }
    function select(i, animate) {
      var same = i === st.i;
      st.i = i;
      var ev = evs[i];
      axisBtns.forEach(function (b) { var on = +b.getAttribute('data-ev') === i; b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.tabIndex = on ? 0 : -1; });
      cards.forEach(function (c) { c.hidden = +c.getAttribute('data-evc') !== i; });
      lis.forEach(function (l) { var on = +l.getAttribute('data-li') === i; if (on) l.setAttribute('aria-current', 'step'); else l.removeAttribute('aria-current'); });
      picks.forEach(function (p) { p.setAttribute('aria-pressed', +p.getAttribute('data-ev') === i ? 'true' : 'false'); });
      if (ev.view !== st.view || !animate) zoomTo(ev.view, animate && ev.view !== st.view);
      var kk = parseFloat(svg.style.getPropertyValue('--k')) || 1;
      all('.rt', svg).forEach(function (g) {
        var on = ev.routes.indexOf(g.getAttribute('data-route')) !== -1;
        g.classList.toggle('on', on);
        var r = g.querySelector('.route-on');
        r.classList.remove('go');
        if (on && animate && !reduced() && !same) { r.style.setProperty('--len', (r.getTotalLength() / kk * 1.03 + 4).toFixed(1) + 'px'); void r.getBoundingClientRect(); r.classList.add('go'); }
      });
      all('[data-route-label]', svg).forEach(function (g) { g.classList.toggle('on', ev.routes.indexOf(g.getAttribute('data-route-label')) !== -1); });
      all('.wp', svg).forEach(function (p) {
        var on = ev.pins.indexOf(p.getAttribute('data-wp')) !== -1;
        p.classList.toggle('on', on); p.classList.toggle('dim', !on);
      });
      status.textContent = (st.playing ? 'Playing. ' : '') + ev.when + ': ' + ev.title;
    }
    axisBtns.forEach(function (b, idx) {
      b.addEventListener('click', function () { stop(); select(+b.getAttribute('data-ev'), true); });
      b.addEventListener('keydown', function (e) {
        var n = null;
        if (e.key === 'ArrowRight') n = Math.min(axisBtns.length - 1, idx + 1);
        else if (e.key === 'ArrowLeft') n = Math.max(0, idx - 1);
        else if (e.key === 'Home') n = 0; else if (e.key === 'End') n = axisBtns.length - 1;
        if (n === null) return;
        e.preventDefault(); axisBtns[n].focus(); stop(); select(n, true);
      });
    });
    picks.forEach(function (b) { b.addEventListener('click', function () { stop(); select(+b.getAttribute('data-ev'), true); }); });
    function paintPlay() {
      playBtn.setAttribute('aria-pressed', st.playing ? 'true' : 'false');
      playBtn.querySelector('span').textContent = st.playing ? 'Pause' : 'Play';
      playBtn.setAttribute('aria-label', st.playing ? 'Pause the timeline' : 'Play the timeline');
      playBtn.querySelector('svg').innerHTML = st.playing ? '<path d="M3 2 H6 V12 H3 Z M8 2 H11 V12 H8 Z" fill="currentColor"/>' : '<path d="M3 2 L12 7 L3 12 Z" fill="currentColor"/>';
    }
    function stop() { if (!st.playing) return; st.playing = false; clearInterval(st.timer); st.timer = null; paintPlay(); }
    function tick() {
      if (st.i >= evs.length - 1) { stop(); status.textContent = 'Played all ' + evs.length + ' moments.'; return; }
      select(st.i + 1, true);
    }
    playBtn.addEventListener('click', function () {
      if (st.playing) { stop(); status.textContent = 'Paused at ' + evs[st.i].when + '.'; return; }
      st.playing = true; paintPlay();
      if (st.i >= evs.length - 1) st.i = -1;
      tick();
      st.timer = setInterval(tick, 3800);
    });
    supBtn.addEventListener('click', function () {
      var on = supBtn.getAttribute('aria-checked') !== 'true';
      supBtn.setAttribute('aria-checked', on ? 'true' : 'false');
      svg.setAttribute('data-supply', on ? 'on' : 'off');
      supNote.hidden = !on;
      if (on && st.view === 'world') zoomTo('corridor', true);
    });
    select(+tl.getAttribute('data-rest'), false);
    if ('ResizeObserver' in window) new ResizeObserver(function () { if (!svg.classList.contains('is-moving')) cam.go(views[st.view], false); }).observe(mapEl);
  });

  function bez(x1, y1, x2, y2) {
    function a(p1, p2) { return 1 - 3 * p2 + 3 * p1; }
    function b(p1, p2) { return 3 * p2 - 6 * p1; }
    function c(p1) { return 3 * p1; }
    function calc(t, p1, p2) { return ((a(p1, p2) * t + b(p1, p2)) * t + c(p1)) * t; }
    function slope(t, p1, p2) { return 3 * a(p1, p2) * t * t + 2 * b(p1, p2) * t + c(p1); }
    return function (x) {
      if (x <= 0) return 0; if (x >= 1) return 1;
      var t = x;
      for (var i = 0; i < 8; i++) { var s = slope(t, x1, x2); if (s === 0) break; t -= (calc(t, x1, x2) - x) / s; }
      return calc(t, y1, y2);
    };
  }
  var inOut = bez(0.65, 0, 0.35, 1), easeOut = bez(0.16, 1, 0.3, 1);
  function initVat(fig) {
    var mv = fig.querySelector('.cl-move'), base = fig.querySelector('.cl-base'), green = fig.querySelector('.cl-green'), blue = fig.querySelector('.cl-blue');
    var s0 = fig.querySelector('.ox0'), s1 = fig.querySelector('.ox1');
    var dots = all('.fz-dot', fig), liq = fig.querySelector('.fz-liq');
    var zc = fig.querySelector('.zl-c'), zl = fig.querySelector('.zl-l');
    var btn = fig.querySelector('[data-dip]'), status = fig.querySelector('.vat-status');
    var vpD = fig.querySelector('.vp-d'), vpN = fig.querySelector('.vp-n');
    var phs = all('.vph', fig), swAir = fig.querySelector('.vph[data-ph="air"] .vph-sw');
    var dipLis = all('.dips li', fig);
    var DIP = 316, SY = 0.6, TOT = 2600;
    var S = { dips: 1, dy: 0, sy: 1, g: 1, f: 1.08, pose: 'air' };
    var names = { vat: 'In the vat', lifted: 'Lifted, green', air: 'Blue in the air' };
    var says = { vat: 'In the vat: the cloth goes under the yellow-green liquor.', lifted: 'Lifted: the cloth comes out bright green.', air: 'In the air: the cloth turns from green to blue, from the top down.' };
    var anim = null;
    function col(n) { return n <= 0 ? 'var(--dye-harda)' : 'var(--dip-' + n + ')'; }
    function apply() {
      mv.setAttribute('transform', 'translate(0 ' + (S.dy + 64).toFixed(2) + ') scale(1 ' + S.sy.toFixed(4) + ') translate(0 -64)');
      base.style.fill = col(S.dips - 1); blue.style.fill = col(S.dips);
      green.setAttribute('opacity', S.g.toFixed(3));
      var a = Math.max(0, Math.min(1, S.f - 0.07)), b = Math.max(0, Math.min(1, S.f));
      s0.setAttribute('offset', a.toFixed(4)); s1.setAttribute('offset', b.toFixed(4));
      liq.setAttribute('opacity', S.dy > DIP * 0.5 ? '0.4' : '0');
      var fl = (S.f - 0.3) / 0.35;
      dots.forEach(function (d) {
        var y = +d.getAttribute('data-y');
        var isBlue = S.f >= 1.07 || (S.f > 0 && y < fl);
        d.style.fill = isBlue ? col(S.dips) : (S.g > 0.5 ? 'var(--dye-leuco)' : col(S.dips - 1));
      });
      var my = 64 + S.dy + (176 - 64) * S.sy;
      zc.setAttribute('cy', my.toFixed(1)); zl.setAttribute('d', 'M406 ' + (my - 3).toFixed(1) + ' L517 150');
      fig.setAttribute('data-pose', S.pose); fig.setAttribute('data-dips', S.dips);
      phs.forEach(function (p) { if (p.getAttribute('data-ph') === S.pose) p.setAttribute('aria-current', 'step'); else p.removeAttribute('aria-current'); });
      swAir.style.background = col(S.dips);
      dipLis.forEach(function (li) { li.classList.toggle('on', +li.getAttribute('data-n') === S.dips); });
      vpD.textContent = 'Dip ' + S.dips + ' of 4'; vpN.textContent = names[S.pose];
    }
    function say() { status.textContent = 'Dip ' + S.dips + ' of 4. ' + says[S.pose]; }
    function idle() { btn.textContent = S.dips >= 4 ? 'Start again' : 'Dip again'; }
    function frame(el) {
      var k;
      if (el < 600) { k = inOut(el / 600); S.dy = DIP * k; S.sy = 1 - (1 - SY) * k; S.g = el < 300 ? 0 : inOut((el - 300) / 300); S.f = -0.1; S.pose = 'vat'; }
      else if (el < 1100) { k = el < 850 ? easeOut((el - 600) / 250) : 1; S.dy = DIP * (1 - k); S.sy = SY + (1 - SY) * k; S.g = 1; S.f = -0.1; S.pose = 'lifted'; }
      else { k = inOut(Math.min(1, (el - 1100) / 1500)); S.dy = 0; S.sy = 1; S.g = 1; S.f = -0.1 + 1.18 * k; S.pose = 'air'; }
    }
    function finish() { anim = null; S.pose = 'air'; S.dy = 0; S.sy = 1; S.g = 1; S.f = 1.08; apply(); say(); idle(); }
    function step(now) {
      if (!anim) return;
      var el = now - anim.t0;
      var prev = S.pose;
      if (el >= TOT) { finish(); return; }
      frame(el); apply();
      if (S.pose !== prev) say();
      requestAnimationFrame(step);
    }
    btn.addEventListener('click', function () {
      if (anim) finish();
      S.dips = S.dips >= 4 ? 1 : S.dips + 1;
      if (reduced()) { finish(); return; }
      btn.textContent = 'Dip again';
      anim = { t0: performance.now() }; frame(0); apply(); say(); requestAnimationFrame(step);
    });
    apply(); idle();
    return { setVessel: function (v) {
      all('[data-vessel]', fig).forEach(function (g) { g.style.display = g.getAttribute('data-vessel') === v ? '' : 'none'; });
      fig.querySelector('.cl-clip').setAttribute('clip-path', 'url(#w-clip-' + (v === 'synthetic' ? 's' : 'n') + ')');
    } };
  }

  all('[data-comp="lab"]').forEach(function (lab) {
    var expBtns = all('[data-x]', lab), panels = all('[data-exp]', lab);
    expBtns.forEach(function (b) {
      b.addEventListener('click', function () {
        var x = b.getAttribute('data-x');
        expBtns.forEach(function (o) { o.setAttribute('aria-pressed', o === b ? 'true' : 'false'); });
        panels.forEach(function (p) { p.hidden = p.getAttribute('data-exp') !== x; });
        all('svg[data-fit]', lab).forEach(fitSvg);
      });
    });
    var state = { blue: 'natural', red: 'madder', water: 'alum', tap: 0, pa: false };
    function paintChoice(group, v) {
      all('[data-choice="' + group + '"] button', lab).forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-v') === v ? 'true' : 'false'); });
      var panel = lab.querySelector('[data-exp="' + group + '"]');
      all('[data-res]', panel).forEach(function (r) { r.hidden = r.getAttribute('data-res') !== v; });
      all('[data-forms]', panel).forEach(function (r) { r.hidden = r.getAttribute('data-forms') !== v; });
    }
    var vatEl = lab.querySelector('[data-vat]');
    var vat = vatEl ? initVat(vatEl) : null;
    function paintBlue() {
      paintChoice('blue', state.blue);
      if (vat) vat.setVessel(state.blue);
      all('.days-plot [data-row]', lab.querySelector('[data-exp="blue"]')).forEach(function (r) { r.classList.toggle('on', r.getAttribute('data-row') === state.blue); });
    }
    all('[data-choice="blue"] button', lab).forEach(function (b) { b.addEventListener('click', function () { state.blue = b.getAttribute('data-v'); paintBlue(); }); });
    paintBlue();
    var redsw = lab.querySelector('[data-redsw]'), pink = redsw.querySelector('[data-pink]'), paG = redsw.querySelector('[data-pa]'), paNote = lab.querySelector('[data-pa-note]');
    var tapBtn = lab.querySelector('[data-tapano]'), tapSt = lab.querySelector('[data-tap-status]'), paSw = lab.querySelector('[data-pa-sw]');
    function paintRed() {
      paintChoice('red', state.red);
      var op = state.red === 'madder' ? (0.62 * (3 - state.tap) / 3) : 0;
      pink.style.opacity = op.toFixed(2);
      paG.style.display = state.pa ? '' : 'none';
      paNote.hidden = !state.pa;
      tapBtn.disabled = state.red !== 'madder';
      tapSt.textContent = state.red === 'madder' ? 'Day ' + state.tap + ' of 3 in the sun' + (state.tap === 3 ? ': the whites are bleached' : '') : 'Alizarin leaves no pink cast to bleach';
      tapBtn.innerHTML = state.tap >= 3 ? 'Dye it again' : 'Another day of <i>tapano</i>';
      all('.days-plot [data-row]', lab.querySelector('[data-exp="red"]')).forEach(function (r) { r.classList.add('on'); });
    }
    all('[data-choice="red"] button', lab).forEach(function (b) { b.addEventListener('click', function () { state.red = b.getAttribute('data-v'); state.tap = 0; paintRed(); }); });
    tapBtn.addEventListener('click', function () { state.tap = state.tap >= 3 ? 0 : state.tap + 1; paintRed(); });
    paSw.addEventListener('click', function () { state.pa = !state.pa; paSw.setAttribute('aria-checked', state.pa ? 'true' : 'false'); paintRed(); });
    paintRed();
    var wsw = lab.querySelector('[data-wsw]'), spots = wsw.querySelector('[data-spots]'), wcl = wsw.querySelector('[data-wcloth]');
    function paintWater() {
      paintChoice('water', state.water);
      var iron = state.water === 'iron';
      spots.style.display = iron ? '' : 'none';
      if (iron) wcl.setAttribute('filter', 'url(#dull)'); else wcl.removeAttribute('filter');
    }
    all('[data-choice="water"] button', lab).forEach(function (b) { b.addEventListener('click', function () { state.water = b.getAttribute('data-v'); paintWater(); }); });
    paintWater();
  });
}, 700); }, 700); })();


});
KV.boot('mb', function (document) {
(function () {
  var root = document.documentElement;
  var osReduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  function reduced() { return osReduce.matches || root.getAttribute('data-reduced-motion') === 'true'; }
  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  var themeBtn = document.getElementById('theme-toggle');
  function effectiveTheme() {
    var t = root.getAttribute('data-theme');
    if (t === 'light' || t === 'dark') return t;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  function paintTheme() {
    var dark = effectiveTheme() === 'dark';
    themeBtn.setAttribute('aria-pressed', dark ? 'true' : 'false');
  }
  themeBtn.addEventListener('click', function () {
    var next = effectiveTheme() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next); store('kv-theme', next); paintTheme();
  });
  paintTheme();
  [['motion-toggle', 'data-reduced-motion', 'kv-motion'], ['contrast-toggle', 'data-high-contrast', 'kv-contrast'], ['text-toggle', 'data-larger-text', 'kv-text']].forEach(function (t) {
    var b = document.getElementById(t[0]);
    if (!b) return;
    function paint() { b.setAttribute('aria-pressed', root.getAttribute(t[1]) === 'true' ? 'true' : 'false'); }
    b.addEventListener('click', function () {
      var on = root.getAttribute(t[1]) === 'true';
      if (on) root.removeAttribute(t[1]); else root.setAttribute(t[1], 'true');
      store(t[2], on ? '' : 'true'); paint();
    });
    paint();
  });

  var data = { sources: {}, claims: {}, rel: {} };
  try { data = JSON.parse(document.getElementById('cite-data').textContent); } catch (e) {}
  var pop = document.getElementById('pop');
  var scrim = document.getElementById('scrim');
  var current = null;

  function build(btn) {
    var nums = {};
    btn.getAttribute('data-n').split(',').forEach(function (pair) { var b = pair.split('='); nums[b[0]] = +b[1]; });
    var bySource = {};
    btn.getAttribute('data-claims').split(' ').forEach(function (cid) {
      (data.claims[cid] || []).forEach(function (q) { (bySource[q[0]] = bySource[q[0]] || []).push(q); });
    });
    var order = Object.keys(bySource).sort(function (a, b) { return nums[a] - nums[b]; });
    var out = '<div class="pop-head"><p id="pop-title">' + (order.length === 1 ? 'Source' : order.length + ' sources') + ' for this sentence</p>' +
      '<button class="pop-close" type="button" aria-label="Close"><svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2 2 L12 12 M12 2 L2 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button></div>';
    order.forEach(function (sk) {
      var s = data.sources[sk] || {};
      out += '<div class="pop-src"><div class="pop-src-h"><b>' + nums[sk] + '</b><strong>' + esc(s.t || sk) + '</strong></div>' +
        '<p class="pop-by">' + esc(s.by || '') + (s.y ? ', ' + s.y : '') + '</p>' + (s.sc ? '<p class="pop-scope">From the ' + esc(s.sc) + '</p>' : '');
      bySource[sk].forEach(function (q) { out += '<p class="pop-q">“' + esc(q[2]) + '”</p>' + (q[1] ? '<p class="pop-loc">' + esc(q[1]) + '</p>' : ''); });
      out += '<p class="pop-rel"><span class="rel ' + esc(s.r) + '" aria-hidden="true"></span>Reliability ' + esc(s.r) + ' · ' + esc((data.rel || {})[s.r] || '') + '</p>';
      if (s.u) out += '<p class="pop-loc"><a href="' + esc(s.u) + '" rel="noopener" target="_blank">Open the source</a></p>';
      out += '</div>';
    });
    out += '<p class="pop-foot">Quotes are verbatim.</p>';
    return out;
  }

  function place(btn) {
    var vw = document.documentElement.clientWidth;
    var r = btn.getBoundingClientRect();
    var sx = window.scrollX || window.pageXOffset, sy = window.scrollY || window.pageYOffset;
    pop.classList.remove('sheet');
    pop.style.left = pop.style.top = pop.style.width = '';
    if (vw < 640) {
      pop.classList.add('sheet'); pop.setAttribute('aria-modal', 'true'); scrim.hidden = false; return;
    }
    pop.setAttribute('aria-modal', 'false'); scrim.hidden = true;
    var spread = btn.closest('.spread');
    var margin = spread && spread.querySelector(':scope > .margin');
    if (vw >= 1200 && margin && margin.offsetParent !== null) {
      var m = margin.getBoundingClientRect();
      var w = Math.min(320, vw - m.left - 16);
      pop.style.width = w + 'px'; pop.style.left = (m.left + sx) + 'px'; pop.style.top = (r.top + sy - 14) + 'px';
      return;
    }
    var width = Math.min(380, vw - 32);
    var left = Math.max(16, Math.min(r.left + sx - 24, sx + vw - width - 16));
    pop.style.width = width + 'px'; pop.style.left = left + 'px'; pop.style.top = (r.bottom + sy + 10) + 'px';
  }

  function close(returnFocus) {
    if (!current) return;
    current.setAttribute('aria-expanded', 'false');
    var s = current.closest('.s'); if (s) s.classList.remove('is-lit');
    pop.hidden = true; pop.classList.remove('is-open'); scrim.hidden = true;
    if (returnFocus) current.focus({ preventScroll: true });
    current = null;
  }

  function open(btn, focus) {
    if (current === btn) { close(true); return; }
    close(false);
    current = btn;
    pop.innerHTML = build(btn);
    pop.hidden = false;
    place(btn);
    pop.classList.remove('is-open'); void pop.offsetWidth; pop.classList.add('is-open');
    btn.setAttribute('aria-expanded', 'true');
    var s = btn.closest('.s'); if (s) s.classList.add('is-lit');
    pop.querySelector('.pop-close').addEventListener('click', function () { close(true); });
    if (focus) pop.focus({ preventScroll: true });
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.cite');
    if (btn) { e.preventDefault(); open(btn, true); return; }
    if (current && !pop.contains(e.target)) close(false);
  });
  scrim.addEventListener('click', function () { close(true); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && current) { close(true); return; }
    if (e.key === 'Tab' && current && pop.classList.contains('sheet')) {
      var f = pop.querySelectorAll('button, a[href]');
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === pop)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    if (e.key === '/' && document.activeElement && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) {
      var q = document.getElementById('atlas-q');
      if (q) { e.preventDefault(); q.focus(); q.select(); }
    }
  });
  window.addEventListener('resize', function () { if (current) place(current); });
  var demo = document.getElementById('demo-cite');
  if (demo && document.documentElement.clientWidth >= 1200) open(demo, false);

  document.querySelectorAll('.src[data-src]').forEach(function (b) {
    b.addEventListener('click', function () {
      var on = b.getAttribute('aria-pressed') !== 'true';
      var scope = b.closest('.screen');
      scope.querySelectorAll('.src[aria-pressed="true"]').forEach(function (o) { o.setAttribute('aria-pressed', 'false'); });
      scope.querySelectorAll('.s.is-src').forEach(function (s) { s.classList.remove('is-src'); });
      if (!on) return;
      b.setAttribute('aria-pressed', 'true');
      var key = b.getAttribute('data-src');
      scope.querySelectorAll('.s[data-src]').forEach(function (s) {
        if ((' ' + s.getAttribute('data-src') + ' ').indexOf(' ' + key + ' ') !== -1) s.classList.add('is-src');
      });
    });
  });

  function anchorNotes() {
    var wide = document.documentElement.clientWidth >= 1200;
    document.querySelectorAll('.spread > .margin.note').forEach(function (aside) {
      var items = Array.prototype.slice.call(aside.querySelectorAll(':scope > ul > li[data-src]'));
      var ul = aside.querySelector(':scope > ul');
      if (!ul) return;
      if (!wide || !items.length) { ul.style.position = ''; ul.style.height = ''; items.forEach(function (li) { li.style.position = ''; li.style.top = ''; }); return; }
      var spread = aside.parentElement;
      var main = spread.querySelector(':scope > .main, :scope > .wide');
      var base = ul.getBoundingClientRect().top;
      var floor = 0;
      ul.style.position = 'relative';
      items.forEach(function (li) {
        var key = li.getAttribute('data-src');
        var first = null;
        if (main) main.querySelectorAll('.s[data-src]').forEach(function (sp) { if (!first && (' ' + sp.getAttribute('data-src') + ' ').indexOf(' ' + key + ' ') !== -1) first = sp; });
        var top = first ? first.getBoundingClientRect().top - base : floor;
        top = Math.max(top, floor);
        li.style.position = 'absolute'; li.style.left = '0'; li.style.right = '0'; li.style.top = top + 'px';
        floor = top + li.offsetHeight + 8;
      });
      ul.style.height = floor + 'px';
    });
  }
  anchorNotes();
  window.addEventListener('resize', anchorNotes);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(anchorNotes);

  function fitSvgText() {
    document.querySelectorAll('svg[data-fit]').forEach(function (svg) {
      var vb = svg.viewBox && svg.viewBox.baseVal;
      var w = svg.getBoundingClientRect().width;
      if (vb && vb.width && w) svg.style.setProperty('--k', (vb.width / w).toFixed(3));
    });
  }
  fitSvgText();
  window.addEventListener('resize', fitSvgText);

  document.querySelectorAll('.res-more .btn, [data-expand]').forEach(function (b) {
    b.addEventListener('click', function () { b.setAttribute('aria-expanded', b.getAttribute('aria-expanded') === 'true' ? 'false' : 'true'); });
  });
  document.querySelectorAll('.menu-btn').forEach(function (b) {
    b.addEventListener('click', function () { b.setAttribute('aria-expanded', b.getAttribute('aria-expanded') === 'true' ? 'false' : 'true'); });
  });
  document.querySelectorAll('[data-view]').forEach(function (b) {
    b.addEventListener('click', function () {
      var v = b.getAttribute('data-view');
      document.querySelectorAll('[data-view]').forEach(function (o) { o.setAttribute('aria-pressed', o === b ? 'true' : 'false'); });
      document.querySelectorAll('[data-view-panel]').forEach(function (pn) { pn.hidden = pn.getAttribute('data-view-panel') !== v; });
    });
  });

  var spineToggle = document.getElementById('spine-toggle');
  function setSpine(expanded) {
    document.querySelectorAll('.stage').forEach(function (li) { li.hidden = !expanded && +li.id.split('-')[1] > 5; });
    spineToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    spineToggle.textContent = expanded ? 'Show the first five stages' : 'Show all 11 stages';
  }
  if (spineToggle) spineToggle.addEventListener('click', function () { setSpine(spineToggle.getAttribute('aria-expanded') !== 'true'); });
  var proof = document.querySelector('.proof');
  var stageBtns = Array.prototype.slice.call(document.querySelectorAll('.proof-btns button'));
  stageBtns.forEach(function (b, i) {
    b.addEventListener('keydown', function (e) {
      var k = e.key, j = -1;
      if (k === 'ArrowRight') j = (i + 1) % stageBtns.length;
      else if (k === 'ArrowLeft') j = (i - 1 + stageBtns.length) % stageBtns.length;
      else if (k === 'Home') j = 0;
      else if (k === 'End') j = stageBtns.length - 1;
      if (j < 0) return;
      e.preventDefault();
      stageBtns.forEach(function (o, q) { o.tabIndex = q === j ? 0 : -1; });
      stageBtns[j].focus();
    });
    b.addEventListener('click', function () {
      var n = +b.getAttribute('data-stage');
      stageBtns.forEach(function (o) { o.setAttribute('aria-pressed', o === b ? 'true' : 'false'); o.tabIndex = o === b ? 0 : -1; });
      proof.classList.add('has-pick');
      proof.querySelectorAll('path[data-band]').forEach(function (p) { p.classList.toggle('on', +p.getAttribute('data-band') === n); });
      if (n > 5) setSpine(true);
      document.querySelectorAll('.stage').forEach(function (li) { li.classList.toggle('is-active', li.id === 'stage-' + n); });
      var li = document.getElementById('stage-' + n);
      if (li) {
        li.scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'start' });
        if (n === 8 && !reduced()) { li.classList.remove('reveal'); void li.offsetWidth; li.classList.add('reveal'); }
      }
    });
  });

  var navLinks = Array.prototype.slice.call(document.querySelectorAll('.chapters a'));
  if ('IntersectionObserver' in window && navLinks.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        navLinks.forEach(function (a) { if (a.getAttribute('href') === '#' + en.target.id) { navLinks.forEach(function (o) { o.removeAttribute('aria-current'); }); a.setAttribute('aria-current', 'location'); } });
      });
    }, { rootMargin: '-30% 0px -60% 0px' });
    navLinks.forEach(function (a) { var t = document.querySelector(a.getAttribute('href')); if (t) io.observe(t); });
  }

  var idx = null;
  try { idx = JSON.parse(document.getElementById('atlas-index').textContent); } catch (e) {}
  var q = document.getElementById('atlas-q');
  var results = document.getElementById('atlas-results');
  var status = document.getElementById('atlas-status');
  function conceptHtml(c) {
    var rows = c.rows.slice(0, 4).map(function (r) {
      return '<li class="res-row"><a class="res-name" href="' + (r[0] === 'Kutch Ajrakh' ? '#craft' : '#') + '">' + esc(r[0]) + '</a><span class="res-meta">' + esc(r[1]) + ' · ' + esc(r[2]) + '</span>' + (r[4] ? '<p class="res-s">' + r[4] + '</p>' : '') + '</li>';
    }).join('');
    var cooc = c.cooc.map(function (t) { return '<button class="chip" type="button" data-q="' + esc(t[0]) + '">' + esc(t[0]) + ' <b>' + t[1] + '</b></button>'; }).join('');
    return '<div class="res-concept"><h3>' + esc(c.label) + '</h3><p>Named in the cited sentences of ' + c.n + ' of the ' + idx.mono + ' monographs.</p>' +
      (cooc ? '<p class="cooc"><span>Named in the same monographs</span>' + cooc + '</p>' : '') + '</div><ol class="res-list">' + rows + '</ol>' +
      (c.n > 4 ? '<div class="actions res-more" data-count="1"><button class="btn sm" type="button">Show all ' + c.n + '</button></div>' : '');
  }
  function render(term) {
    if (!idx || !results) return;
    var t = term.trim().toLowerCase();
    document.querySelectorAll('.try .chip[data-q]').forEach(function (c) { c.setAttribute('aria-pressed', c.getAttribute('data-q') === t ? 'true' : 'false'); });
    if (!t) { results.innerHTML = ''; status.textContent = ''; return; }
    var html = '', said = [];
    var c = idx.concepts[t];
    if (!c && t.length > 2) Object.keys(idx.concepts).forEach(function (k) { if (!c && k.indexOf(t) === 0) c = idx.concepts[k]; });
    if (c) { html += '<div class="res-group">' + conceptHtml(c) + '</div>'; said.push(c.label + ': ' + c.n + ' monograph' + (c.n === 1 ? '' : 's')); }
    var crafts = idx.crafts.filter(function (r) { return r[0].toLowerCase().indexOf(t) !== -1 || r[1].toLowerCase().indexOf(t) === 0; });
    if (crafts.length) {
      html += '<div class="res-group"><div class="res-concept"><h3>Crafts</h3><p>' + crafts.length + ' match' + (crafts.length === 1 ? '' : 'es') + '</p></div><ol class="res-list">' +
        crafts.slice(0, 6).map(function (r) { return '<li class="res-row"><a class="res-name" href="#">' + esc(r[0]) + '</a><span class="res-meta">' + esc(r[1]) + ' · ' + esc(r[2]) + (r[3] ? ' · Monograph' : '') + '</span></li>'; }).join('') + '</ol>' +
        (crafts.length > 6 ? '<div class="actions res-more" data-count="1"><button class="btn sm" type="button">Show all ' + crafts.length + '</button></div>' : '') + '</div>';
      said.push(crafts.length + ' crafts');
    }
    if (!html) html = '<div class="res-group"><div class="res-concept"><h3>' + esc(term) + '</h3><p>Try a material, a method or a place, such as indigo, lost wax or Kerala.</p></div></div>';
    results.innerHTML = html;
    status.textContent = said.length ? said.join('; ') + '.' : 'No match.';
  }
  if (q) {
    q.addEventListener('input', function () { render(q.value); });
    document.addEventListener('click', function (e) {
      var c = e.target.closest('[data-q]');
      if (!c) return;
      e.preventDefault(); q.value = c.getAttribute('data-q'); render(q.value);
    });
  }

  document.querySelectorAll('[data-copy]').forEach(function (b) {
    b.addEventListener('click', function () {
      var t = document.getElementById(b.getAttribute('data-copy')).textContent;
      var label = b.textContent;
      function done() { b.textContent = 'Copied'; setTimeout(function () { b.textContent = label; }, 1800); }
      try { navigator.clipboard.writeText(t).then(done, done); } catch (e) { done(); }
    });
  });

  var dip = document.querySelector('.dip');
  var dipBtn = document.getElementById('dip-btn');
  var dipStatus = document.getElementById('dip-status');
  var frames = dip ? Array.prototype.slice.call(dip.querySelectorAll('.frame')) : [];
  var timers = [];
  var level = 1;
  var words = ['', 'In the air the cloth turns from green to blue.', 'A second dip: the blue deepens.', 'A third dip: deeper still.', 'A fourth dip: the darkest blue.'];
  function setFrame(n) { frames.forEach(function (f, i) { if (i + 1 === n) f.setAttribute('aria-current', 'step'); else f.removeAttribute('aria-current'); }); }
  function say(t) { dipStatus.textContent = t; }
  if (dipBtn) dipBtn.addEventListener('click', function () {
    timers.forEach(clearTimeout); timers = [];
    level = level >= 4 ? 1 : level + 1;
    var lvl = level;
    dipBtn.textContent = lvl >= 4 ? 'Start again' : 'Dip again';
    if (reduced()) {
      dip.setAttribute('data-dip', String(lvl)); setFrame(3);
      say('Dip ' + lvl + ' of 4. ' + words[lvl]);
      return;
    }
    dip.classList.add('run');
    setFrame(1); say('Dip ' + lvl + ' of 4. Into the vat: the dissolved dye soaks into the fibre.');
    timers.push(setTimeout(function () { setFrame(2); say('Dip ' + lvl + ' of 4. Lifted out: the cloth is bright green.'); }, 600));
    timers.push(setTimeout(function () { dip.setAttribute('data-dip', String(lvl)); setFrame(3); say('Dip ' + lvl + ' of 4. ' + words[lvl]); }, 1100));
    timers.push(setTimeout(function () { dip.classList.remove('run'); }, 2600));
  });

  var hero = document.querySelector('.hero');
  if (hero) {
    var steps = Array.prototype.slice.call(hero.querySelectorAll('.vat-steps li'));
    var vatStatus = document.getElementById('vat-status');
    var again = hero.querySelector('.vat-again');
    var phaseWords = { in: 'In the vat: the dissolved dye soaks into the fibre.', lifted: 'Lifted out: the cloth is bright green.', air: 'In the air the cloth turns blue, from the top down.' };
    var mark = function (k) {
      steps.forEach(function (li) { if (li.getAttribute('data-step') === k) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current'); });
      hero.setAttribute('data-phase', k);
      if (vatStatus) vatStatus.textContent = phaseWords[k] || '';
    };
    var vt = [];
    var play = function (force) {
      vt.forEach(clearTimeout); vt = [];
      if (reduced()) { mark('air'); hero.setAttribute('data-phase', 'rest'); return; }
      mark('in');
      vt.push(setTimeout(function () { mark('lifted'); }, 600));
      vt.push(setTimeout(function () { mark('air'); }, 1100));
      vt.push(setTimeout(function () { hero.setAttribute('data-phase', 'rest'); }, 2700));
    };
    var seen = false;
    try { seen = sessionStorage.getItem('kv-vat-played') === '1'; } catch (e) {}
    var first = function () {
      if (seen || reduced()) return;
      try { sessionStorage.setItem('kv-vat-played', '1'); } catch (e) {}
      vt.push(setTimeout(play, 800));
    };
    if (again) again.addEventListener('click', function () { play(true); });
    var img = hero.querySelector('.hero-img');
    var go = function () { if ('IntersectionObserver' in window) { var o = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { o.disconnect(); first(); } }); }, { threshold: 0.4 }); o.observe(hero); } else first(); };
    if (img && !img.complete) img.addEventListener('load', go, { once: true }); else go();
  }
  document.querySelectorAll('[data-cite-style]').forEach(function (b) {
    b.addEventListener('click', function () {
      var t = document.getElementById('cite-text');
      document.querySelectorAll('[data-cite-style]').forEach(function (o) { o.setAttribute('aria-pressed', o === b ? 'true' : 'false'); });
      var bib = b.getAttribute('data-cite-style') === 'bibtex';
      t.textContent = t.getAttribute(bib ? 'data-bibtex' : 'data-text');
      t.classList.toggle('is-code', bib);
    });
  });
  var clr = document.querySelector('.search-box .clear');
  if (clr) clr.addEventListener('click', function () { var i = document.getElementById('atlas-q'); i.value = ''; i.dispatchEvent(new Event('input')); i.focus(); });
})();

});
KV.boot('rm', function (document) {
(function () {
  'use strict';
  var kvData = document.getElementById('kv-data');
  if (!kvData) return;
  var D = JSON.parse(kvData.textContent);
  (function () {
    var q = null; try { q = new URLSearchParams(location.search).get('screens'); } catch (e) {}
    if (!q) return;
    var keep = {};
    q.split(',').forEach(function (part) { var m = part.split('-'); var a = +m[0], b = +(m[1] || m[0]); for (var i = a; i <= b; i++) keep[i] = true; });
    Array.prototype.forEach.call(document.querySelectorAll('[data-screen]'), function (el) { if (!keep[+el.getAttribute('data-screen')]) el.hidden = true; });
  })();
  var root = document.documentElement;
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
  function reduced() { return root.getAttribute('data-reduced-motion') === 'true' || mq.matches; }
  function store(k, v) { try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} }
  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function mmss(t) { t = Math.max(0, Math.round(t)); return Math.floor(t / 60) + ':' + ('0' + (t % 60)).slice(-2); }

  var ICON_X = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 3.5 L12.5 12.5 M12.5 3.5 L3.5 12.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
  var ICON_OK = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5 L6.5 12 L13 4.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var ICON_NO = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4 L12 12 M12 4 L4 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';

  function toast(title, desc, tone) {
    var zone = $('#toasts'); if (!zone) return;
    var el = document.createElement('div');
    el.className = 'toast ' + (tone || 'success');
    if (tone === 'error') el.setAttribute('role', 'alert');
    el.innerHTML = '<span class="t-ic">' + (tone === 'error' ? ICON_NO : ICON_OK) + '</span><span class="t-body"><span class="t-title">' + esc(title) + '</span>' + (desc ? '<span class="t-desc">' + esc(desc) + '</span>' : '') + '</span><button class="t-x" type="button" aria-label="Dismiss">' + ICON_X + '</button>';
    zone.appendChild(el);
    while (zone.children.length > 3) zone.removeChild(zone.firstChild);
    var gone = function () { if (el.parentNode) el.parentNode.removeChild(el); };
    el.querySelector('.t-x').addEventListener('click', gone);
    var life = tone === 'error' ? 0 : tone === 'warning' ? 8000 : 5000;
    var timer = life ? setTimeout(gone, life) : null;
    el.addEventListener('mouseenter', function () { clearTimeout(timer); });
    el.addEventListener('mouseleave', function () { if (life) timer = setTimeout(gone, 2400); });
  }

  function isDark() { var t = root.getAttribute('data-theme'); if (t) return t === 'dark'; return window.matchMedia('(prefers-color-scheme: dark)').matches; }
  function syncTools() {
    var th = $('#theme-toggle'); if (th) th.setAttribute('aria-pressed', String(isDark()));
    var c = $('#contrast-toggle'); if (c) c.setAttribute('aria-pressed', String(root.getAttribute('data-high-contrast') === 'true'));
    var x = $('#text-toggle'); if (x) x.setAttribute('aria-pressed', String(root.getAttribute('data-larger-text') === 'true'));
    var m = $('#motion-toggle'); if (m) m.setAttribute('aria-pressed', String(root.getAttribute('data-reduced-motion') === 'true'));
  }
  function flag(attr, key) {
    var on = root.getAttribute(attr) === 'true';
    if (on) { root.removeAttribute(attr); store(key, null); } else { root.setAttribute(attr, 'true'); store(key, 'true'); }
    syncTools(); placeOpen(); fitAll(); qmoreAll();
  }
  $('#theme-toggle').addEventListener('click', function () { var next = isDark() ? 'light' : 'dark'; root.setAttribute('data-theme', next); store('kv-theme', next); syncTools(); });
  $('#contrast-toggle').addEventListener('click', function () { flag('data-high-contrast', 'kv-contrast'); });
  $('#text-toggle').addEventListener('click', function () { flag('data-larger-text', 'kv-text'); });
  $('#motion-toggle').addEventListener('click', function () { flag('data-reduced-motion', 'kv-motion'); });
  syncTools();

  var fitObs = null;
  function fitOne(s) {
    var vb = s.viewBox && s.viewBox.baseVal; var w = s.getBoundingClientRect().width;
    if (vb && vb.width && w) s.style.setProperty('--k', (vb.width / w).toFixed(4));
  }
  function fitAll() { $$('svg[data-fit]').forEach(fitOne); }
  if (window.ResizeObserver) {
    fitObs = new ResizeObserver(function (en) { en.forEach(function (e) { fitOne(e.target); }); });
    $$('svg[data-fit]').forEach(function (s) { fitObs.observe(s); });
  }
  fitAll();

  function qmore(btn) {
    var t = document.getElementById(btn.getAttribute('aria-controls')); if (!t) return;
    if (!t.offsetParent) return;
    var h1 = t.closest('.q-title');
    if (h1.classList.contains('is-open')) { btn.hidden = false; return; }
    btn.hidden = t.scrollHeight <= t.clientHeight + 2;
  }
  function qmoreAll() { $$('.q-more').forEach(qmore); }
  $$('.q-more').forEach(function (b) {
    b.addEventListener('click', function () {
      var t = document.getElementById(b.getAttribute('aria-controls')), h1 = t.closest('.q-title');
      var open = !h1.classList.contains('is-open');
      h1.classList.toggle('is-open', open);
      b.setAttribute('aria-expanded', String(open));
      b.textContent = open ? b.getAttribute('data-less') : b.getAttribute('data-more');
      placeOpen();
    });
  });

  var STR = {
    en: { one: '1 source for this sentence', many: '{n} sources for this sentence', open: 'Open the source', foot: 'Quotes are verbatim.', close: 'Close', relw: 'Reliability ', rel: { A: 'A · peer-reviewed or official', B: 'B · reputable reference', C: 'C · general web', D: 'D · unknown' }, from: {} },
    hi: { one: 'इस वाक्य का 1 स्रोत', many: 'इस वाक्य के {n} स्रोत', open: 'स्रोत खोलें', foot: 'उद्धरण स्रोत की अपनी भाषा में, शब्दशः हैं।', close: 'बंद करें', relw: 'विश्वसनीयता ', rel: { A: 'A · समकक्ष-समीक्षित या आधिकारिक', B: 'B · प्रतिष्ठित संदर्भ', C: 'C · सामान्य वेब', D: 'D · अज्ञात' },
      from: { 'From the Textiles family monograph': 'वस्त्र परिवार मोनोग्राफ़ से', 'From the KalaVigyan craft science library': 'कलाविज्ञान शिल्प-विज्ञान पुस्तकालय से', 'From the Bagru Hand Block Print monograph': 'बगरू हैंड ब्लॉक प्रिंट मोनोग्राफ़ से', 'Compound record': 'यौगिक अभिलेख', 'From the related crafts': 'संबंधित शिल्पों से' } },
    ur: { one: 'اس جملے کا 1 ماخذ', many: 'اس جملے کے {n} ماخذ', open: 'ماخذ کھولیں', foot: 'اقتباسات ماخذ کی اپنی زبان میں، لفظ بہ لفظ ہیں۔', close: 'بند کریں', relw: 'اعتباریت ', rel: { A: 'A · ہم مرتبہ جائزہ شدہ یا سرکاری', B: 'B · معتبر حوالہ', C: 'C · عام ویب', D: 'D · نامعلوم' }, from: {} }
  };
  var popSeq = 0;
  function popHTML(sid, lang, id) {
    var S = STR[lang] || STR.en, items = D.sents[sid] || [];
    var h = '<div class="pop-head"><p id="' + id + '-t">' + (items.length === 1 ? S.one : S.many.replace('{n}', items.length)) + '</p><button class="pop-close" type="button" aria-label="' + S.close + '">' + ICON_X + '</button></div>';
    items.forEach(function (it) {
      var s = D.sources[it.n];
      h += '<div class="pop-src"><div class="pop-src-h"><b>' + it.n + '</b><strong lang="en" dir="ltr">' + esc(s.t) + '</strong></div>';
      h += '<p class="pop-by" lang="en" dir="ltr">' + esc(s.by) + (s.y ? ', ' + s.y : '') + '</p>';
      if (s.from) { var fr = S.from[s.from]; h += fr ? '<p class="pop-from">' + esc(fr) + '</p>' : '<p class="pop-from" lang="en" dir="ltr">' + esc(s.from) + '</p>'; }
      if (it.scope) h += '<p class="pop-scope" lang="en" dir="ltr">' + esc(it.scope) + '</p>';
      it.qs.forEach(function (q) {
        h += '<p class="pop-q" lang="en" dir="ltr">“' + esc(q.q) + '”</p>';
        if (q.l) h += '<p class="pop-loc" lang="en" dir="ltr">' + esc(q.l) + '</p>';
      });
      h += '<p class="pop-rel"><span class="rel ' + s.r + '" aria-hidden="true"></span>' + S.relw + S.rel[s.r] + '</p>';
      h += '<p class="pop-loc"><a href="' + esc(s.u) + '" target="_blank" rel="noopener">' + S.open + '</a></p></div>';
    });
    h += '<p class="pop-foot">' + S.foot + '</p>';
    return h;
  }

  var OPEN = [];
  function langOf(el) { var l = el.closest('[data-ui-lang]'); return l ? l.getAttribute('data-ui-lang') : 'en'; }
  function modeOf(btn) {
    if (btn.closest('.pf')) return 'phone';
    if (window.innerWidth < 640) return 'sheet';
    var spread = btn.closest('.spread');
    if (window.innerWidth >= 1200 && spread) {
      var m = spread.querySelector(':scope > .margin');
      if (m && m.offsetParent !== null) return 'dock';
    }
    return 'anchor';
  }
  function marginOf(btn) { var sp = btn.closest('.spread'); return sp ? sp.querySelector(':scope > .margin') : null; }
  function ctxOf(btn) { return btn.closest('.pf') || btn.closest('.lang-panel') || btn.closest('.screen') || document.body; }

  function closeRec(rec, refocus) {
    if (!rec) return;
    rec.btn.setAttribute('aria-expanded', 'false');
    var s = rec.btn.closest('.s'); if (s) s.classList.remove('is-lit');
    if (rec.pop.parentNode) rec.pop.parentNode.removeChild(rec.pop);
    if (rec.scrim) rec.scrim.hidden = true;
    OPEN = OPEN.filter(function (r) { return r !== rec; });
    if (refocus) rec.btn.focus({ preventScroll: true });
  }
  function closeCtx(ctx) { OPEN.filter(function (r) { return r.ctx === ctx; }).forEach(function (r) { closeRec(r, false); }); }

  function place(rec) {
    var pop = rec.pop, btn = rec.btn;
    if (rec.mode === 'dock') {
      var m = rec.host, s = btn.closest('.s') || btn;
      var mt = m.getBoundingClientRect().top, st = s.getBoundingClientRect().top;
      var top = Math.max(0, Math.round(st - mt - 6));
      pop.style.top = top + 'px';
      var box = btn.closest('[data-pop-box]'), lim = window.innerHeight - 32;
      if (box) {
        var stopSel = box.getAttribute('data-pop-stop'), stopEl = stopSel ? document.querySelector(stopSel) : null;
        var bottom = stopEl && stopEl.offsetParent ? stopEl.getBoundingClientRect().top - 16 : box.getBoundingClientRect().bottom - 8;
        lim = Math.min(lim, bottom - (mt + top));
      }
      pop.style.setProperty('--pop-max', Math.max(200, Math.round(lim)) + 'px');
    } else if (rec.mode === 'anchor') {
      var r = btn.getBoundingClientRect();
      var w = Math.min(380, window.innerWidth - 32);
      var left = r.left + window.scrollX - 24;
      var maxL = document.documentElement.clientWidth - w - 16 + window.scrollX;
      left = Math.max(16 + window.scrollX, Math.min(left, maxL));
      if (langOf(btn) === 'ur') left = Math.max(16 + window.scrollX, Math.min(r.right + window.scrollX - w + 24, maxL));
      pop.style.left = Math.round(left) + 'px';
      pop.style.top = Math.round(r.bottom + window.scrollY + 10) + 'px';
      pop.style.setProperty('--pop-max', Math.max(220, window.innerHeight - 32) + 'px');
    }
  }
  function placeOpen() { OPEN.forEach(function (rec) { var m = modeOf(rec.btn); if (m !== rec.mode) closeRec(rec, false); else place(rec); }); }

  function openCite(btn, opts) {
    opts = opts || {};
    var ctx = ctxOf(btn);
    var already = OPEN.filter(function (r) { return r.btn === btn; })[0];
    var mode = modeOf(btn);
    if (!opts.force && mode !== 'phone') OPEN.filter(function (r) { return r.mode !== 'phone'; }).forEach(function (r) { closeRec(r, false); });
    closeCtx(ctx);
    if (already && !opts.force) return;
    var lang = langOf(btn), sid = btn.getAttribute('data-sid');
    var pop = document.createElement('div');
    var id = 'pop-' + (++popSeq);
    pop.id = id;
    pop.className = 'pop' + (lang === 'hi' ? ' pop-hi' : '') + (lang === 'ur' ? ' pop-ur' : '');
    pop.setAttribute('role', 'dialog');
    pop.setAttribute('tabindex', '-1');
    pop.setAttribute('aria-labelledby', id + '-t');
    pop.setAttribute('lang', lang);
    if (lang === 'ur') pop.setAttribute('dir', 'rtl');
    pop.innerHTML = popHTML(sid, lang, id);
    btn.setAttribute('aria-controls', id);
    var rec = { btn: btn, pop: pop, mode: mode, ctx: ctx, scrim: null, host: null };
    if (mode === 'phone') {
      pop.classList.add('sheet');
      pop.setAttribute('aria-modal', 'true');
      var pf = btn.closest('.pf');
      rec.scrim = pf.querySelector('.pf-scrim');
      rec.scrim.hidden = false;
      pf.appendChild(pop);
    } else if (mode === 'sheet') {
      pop.classList.add('sheet');
      pop.setAttribute('aria-modal', 'true');
      rec.scrim = $('#scrim'); rec.scrim.hidden = false;
      rec.ctx = document.body;
      document.body.appendChild(pop);
    } else if (mode === 'dock') {
      pop.classList.add('docked');
      pop.setAttribute('aria-modal', 'false');
      rec.host = marginOf(btn);
      rec.host.appendChild(pop);
    } else {
      pop.setAttribute('aria-modal', 'false');
      document.body.appendChild(pop);
    }
    if (!reduced()) pop.classList.add('is-open');
    btn.setAttribute('aria-expanded', 'true');
    var s = btn.closest('.s'); if (s) s.classList.add('is-lit');
    if (!reduced() && opts.focus !== false) { btn.classList.remove('press'); void btn.offsetWidth; btn.classList.add('press'); }
    OPEN.push(rec);
    place(rec);
    pop.querySelector('.pop-close').addEventListener('click', function () { closeRec(rec, true); });
    if (rec.scrim) rec.scrim.onclick = function () { closeRec(rec, true); };
    if (mode === 'anchor') {
      pop.addEventListener('keydown', function (e) {
        if (e.key !== 'Tab') return;
        var f = $$('a[href], button:not([disabled])', pop), last = f[f.length - 1];
        if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); closeRec(rec, true); }
        if (e.shiftKey && (document.activeElement === f[0] || document.activeElement === pop)) { e.preventDefault(); closeRec(rec, true); }
      });
    }
    if (opts.focus !== false) pop.focus({ preventScroll: mode === 'dock' || mode === 'phone' });
  }

  document.addEventListener('click', function (e) {
    var c = e.target.closest('.cite');
    if (c) { e.preventDefault(); e.stopPropagation(); openCite(c); return; }
    if (e.target.closest('.pop')) return;
    OPEN.slice().forEach(function (rec) { if (rec.mode === 'anchor') closeRec(rec, false); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && OPEN.length) {
      var a = document.activeElement, hit = OPEN.filter(function (r) { return r.pop.contains(a) || r.btn === a; })[0];
      closeRec(hit || OPEN[OPEN.length - 1], true); return;
    }
    if (e.key === 'Tab' && OPEN.length) {
      var rec = OPEN.filter(function (r) { return r.pop.contains(document.activeElement); })[0];
      if (!rec || (rec.mode !== 'sheet' && rec.mode !== 'phone')) return;
      var f = $$('a[href], button:not([disabled])', rec.pop);
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === rec.pop)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  var rt;
  window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(function () { placeOpen(); qmoreAll(); }, 80); });

  function restOpen() {
    $$('.pf[data-rest-sid]').forEach(function (pf) {
      var b = pf.querySelector('.cite[data-sid="' + pf.getAttribute('data-rest-sid') + '"]');
      if (b) openCite(b, { focus: false, force: true });
    });
    if (window.innerWidth >= 1200) {
      $$('[data-rest-open]').forEach(function (el) {
        if (el.closest('[hidden]')) return;
        if (el.offsetParent === null) return;
        var b = el.querySelector('.cite[data-sid="' + el.getAttribute('data-rest-open') + '"]');
        if (b) openCite(b, { focus: false, force: true });
      });
    }
  }

  var srcStatus = $('#src-status');
  $$('#cite-sources .src').forEach(function (b) {
    b.addEventListener('click', function () {
      var on = b.getAttribute('aria-pressed') === 'true';
      $$('#cite-sources .src').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
      $$('#cite .s.is-src').forEach(function (x) { x.classList.remove('is-src'); });
      if (on) { srcStatus.textContent = ''; return; }
      b.setAttribute('aria-pressed', 'true');
      var n = +b.getAttribute('data-n'), count = 0;
      $$('#cite .s[data-sid]').forEach(function (s) {
        if (s.closest('.pf')) return;
        var it = D.sents[s.getAttribute('data-sid')] || [];
        if (it.some(function (x) { return x.n === n; })) { s.classList.add('is-src'); count++; }
      });
      srcStatus.textContent = count ? ('Source ' + n + ' lights ' + count + ' sentence' + (count === 1 ? '' : 's') + ' on this screen.') : ('Source ' + n + ' supports sentences in later sections.');
    });
  });

  var cb = $('#cb-text');
  $$('.cb-seg button').forEach(function (b) {
    b.addEventListener('click', function () {
      $$('.cb-seg button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      var st = b.getAttribute('data-style');
      cb.classList.toggle('is-code', st === 'bibtex');
      cb.classList.toggle('is-link', st === 'link');
      if (st === 'apa') cb.innerHTML = cb.getAttribute('data-apa'); else cb.textContent = cb.getAttribute('data-' + st);
    });
  });
  function copyText(t) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(t);
    return new Promise(function (res, rej) { var ta = document.createElement('textarea'); ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); res(); } catch (e) { rej(e); } document.body.removeChild(ta); });
  }
  $$('[data-copy]').forEach(function (b) {
    b.addEventListener('click', function () {
      var el = document.getElementById(b.getAttribute('data-copy'));
      copyText(el.textContent).then(function () { toast('Citation copied', null, 'success'); }, function () { toast('Could not copy the citation', 'Select it and copy it by hand.', 'error'); });
    });
  });
  $$('[data-save]').forEach(function (b) {
    var label = b.textContent;
    b.addEventListener('click', function () {
      var on = b.getAttribute('aria-pressed') === 'true';
      b.setAttribute('aria-pressed', String(!on));
      var l = langOf(b);
      var saved = { en: 'Saved', hi: 'सहेजा गया', ur: 'محفوظ ہو گیا' }[l] || 'Saved';
      b.textContent = on ? label : saved;
      if (!reduced()) { b.classList.remove('press'); void b.offsetWidth; b.classList.add('press'); }
      if (!on) toast(saved, l === 'en' ? 'Find it under Saved.' : null, 'success');
    });
  });
  $$('[data-goto]').forEach(function (b) {
    b.addEventListener('click', function () { var t = document.getElementById(b.getAttribute('data-goto')); if (t) { t.scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'center' }); var f = t.querySelector('button'); if (f) setTimeout(function () { f.focus({ preventScroll: true }); }, reduced() ? 0 : 500); } });
  });

  var Q = D.quiz, qi = 0, score = 0, results = [];
  var qq = $('#quiz-q'), qo = $('#quiz-opts'), qs = $('#quiz-status'), qn = $('#quiz-next'), quiz = $('#quiz');
  function steps() {
    $$('.quiz-steps i', quiz).forEach(function (el, i) { el.className = results[i] === true ? 'done-right' : results[i] === false ? 'done-wrong' : (i === qi ? 'on' : ''); });
    $('#quiz-count').textContent = 'Question ' + Math.min(qi + 1, Q.length) + ' of ' + Q.length;
  }
  function renderQ() {
    var q = Q[qi];
    quiz.classList.remove('answered', 'finished');
    qq.innerHTML = q.pre + '<span class="blank"><span class="vh">blank</span></span>' + q.post;
    qo.innerHTML = '';
    q.opts.forEach(function (o, i) {
      var d = document.createElement('div');
      d.className = 'opt';
      d.innerHTML = '<button class="opt-b" type="button"><span class="term">' + esc(o.term) + '</span><span class="mark"></span></button><p class="why">' + o.html + '</p>';
      d.querySelector('.opt-b').addEventListener('click', function () { choose(i); });
      qo.appendChild(d);
    });
    qs.textContent = 'Choose the word that fills the blank.';
    qn.disabled = true;
    qn.textContent = qi === Q.length - 1 ? 'See how you did' : 'Next question';
    steps();
  }
  function choose(i) {
    var q = Q[qi];
    if (quiz.classList.contains('answered')) return;
    var right = q.opts[i].right;
    results[qi] = right; if (right) score++;
    quiz.classList.add('answered');
    $$('.opt', qo).forEach(function (b, j) {
      b.querySelector('.opt-b').setAttribute('aria-disabled', 'true');
      var o = q.opts[j], mk = b.querySelector('.mark');
      if (o.right) { b.classList.add('is-right'); mk.innerHTML = ICON_OK + 'Right'; }
      else if (j === i) { b.classList.add('is-wrong'); mk.innerHTML = ICON_NO + 'Not this one'; }
    });
    var bl = qq.querySelector('.blank');
    bl.textContent = q.key; bl.classList.add('filled');
    if (!reduced()) bl.classList.add('press');
    qq.insertAdjacentHTML('beforeend', q.cite);
    qs.textContent = right ? 'Right. Each choice now shows the sentence it comes from.' : 'Not this one: the word is ' + q.key + '. Each choice shows the sentence it comes from.';
    qn.disabled = false;
    steps();
  }
  qn.addEventListener('click', function () {
    if (quiz.classList.contains('finished')) { qi = 0; score = 0; results = []; renderQ(); return; }
    if (qi < Q.length - 1) { qi++; renderQ(); qq.setAttribute('tabindex', '-1'); qq.focus({ preventScroll: true }); return; }
    quiz.classList.add('finished');
    $('#quiz-score').textContent = score + ' of ' + Q.length;
    $('#quiz-score-text').textContent = score === Q.length ? 'Every blank right. Each word came from a cited sentence in this answer.' : 'The sentences behind each question are in sections 1, 6 and 7 of this answer.';
    qs.textContent = '';
    qn.textContent = 'Try again';
    qi = Q.length; steps(); $('#quiz-count').textContent = score + ' of ' + Q.length + ' right';
  });
  if (Q && qq) renderQ();

  function makeClock(audio, duration) {
    if (audio && audio.currentSrc) return audio;
    var t = 0, rate = 1, paused = true, last = 0, raf = 0, h = { timeupdate: [], ended: [], play: [], pause: [] };
    function emit(n) { h[n].forEach(function (f) { f(); }); }
    function tick(now) {
      if (paused) return;
      t += (now - last) / 1000 * rate; last = now;
      if (t >= duration) { t = duration; paused = true; emit('timeupdate'); emit('pause'); emit('ended'); return; }
      emit('timeupdate'); raf = requestAnimationFrame(tick);
    }
    return {
      get currentTime() { return t; }, set currentTime(v) { t = Math.max(0, Math.min(duration, v)); emit('timeupdate'); },
      get paused() { return paused; }, get playbackRate() { return rate; }, set playbackRate(v) { rate = v; }, duration: duration,
      play: function () { if (!paused) return Promise.resolve(); paused = false; last = performance.now(); raf = requestAnimationFrame(tick); emit('play'); return Promise.resolve(); },
      pause: function () { if (paused) return; paused = true; cancelAnimationFrame(raf); emit('pause'); },
      addEventListener: function (n, f) { (h[n] = h[n] || []).push(f); }
    };
  }

  var L = (function () {
    var text = $('#listen-text'); if (!text) return null;
    var LS = JSON.parse($('#listen-script').textContent), tr = LS.tracks[0], W = tr.words;
    var sents = $$('.s', text), wEls = $$('.w', text), player = $('#player');
    var before = +player.getAttribute('data-before'), total = +player.getAttribute('data-total');
    var playBtn = $('#pl-play'), status = $('#pl-status');
    var sidIdx = {}; sents.forEach(function (s, i) { sidIdx[s.getAttribute('data-sid')] = i; });
    var firstWord = {}; W.forEach(function (w, i) { if (!(w.sentence_id in firstWord)) firstWord[w.sentence_id] = i; });
    var clock = makeClock(null, tr.duration_seconds);
    var cur = -1;
    function idxAt(t) { var lo = 0, hi = W.length - 1, r = 0; while (lo <= hi) { var m = (lo + hi) >> 1; if (W[m].start <= t) { r = m; lo = m + 1; } else hi = m - 1; } return r; }
    function render() {
      var t = clock.currentTime, i = idxAt(t);
      if (i !== cur) {
        if (wEls[cur]) wEls[cur].classList.remove('is-word');
        cur = i;
        if (wEls[i]) wEls[i].classList.add('is-word');
        var si = sidIdx[W[i].sentence_id];
        sents.forEach(function (s, k) { s.classList.toggle('is-reading', k === si); });
        $('#pl-sent').textContent = 'Sentence ' + (si + 1) + ' of ' + sents.length;
        var b = $('.pl-track i.cur b'); if (b) b.style.width = Math.round(i / W.length * 100) + '%';
      }
      $('#pl-el').textContent = mmss(before + t);
    }
    function setPlaying(on) {
      player.classList.toggle('is-playing', on);
      playBtn.innerHTML = on ? playBtn.getAttribute('data-pause') : playBtn.getAttribute('data-play');
      playBtn.setAttribute('aria-label', on ? 'Pause' : 'Play');
    }
    clock.addEventListener('timeupdate', render);
    clock.addEventListener('play', function () { setPlaying(true); });
    clock.addEventListener('pause', function () { setPlaying(false); });
    clock.addEventListener('ended', function () { status.textContent = 'Section 4 read to the end.'; toast('Section 4 read', 'Next: From barter with herders to running yardage.', 'info'); });
    function seekSentence(si) { si = Math.max(0, Math.min(sents.length - 1, si)); clock.currentTime = W[firstWord[sents[si].getAttribute('data-sid')]].start; status.textContent = 'Sentence ' + (si + 1) + ' of ' + sents.length; }
    function curSentence() { return sidIdx[W[idxAt(clock.currentTime)].sentence_id]; }
    function start() { if (clock.currentTime >= tr.duration_seconds - 0.05) clock.currentTime = 0; clock.play(); status.textContent = 'Reading section 4, sentence ' + (curSentence() + 1) + ' of ' + sents.length; }
    playBtn.addEventListener('click', function () { if (clock.paused) start(); else { clock.pause(); status.textContent = 'Paused'; } });
    $('#pl-prev').addEventListener('click', function () { var si = curSentence(), w0 = W[firstWord[sents[si].getAttribute('data-sid')]].start; seekSentence(clock.currentTime - w0 > 1 ? si : si - 1); });
    $('#pl-next').addEventListener('click', function () { seekSentence(curSentence() + 1); });
    player.addEventListener('keydown', function (e) {
      if (e.target.tagName === 'SELECT' || e.target.tagName === 'INPUT') return;
      if (e.key === 'ArrowLeft') { e.preventDefault(); $('#pl-prev').click(); }
      if (e.key === 'ArrowRight') { e.preventDefault(); $('#pl-next').click(); }
    });
    $('#pl-rate').addEventListener('change', function (e) { clock.playbackRate = +e.target.value; status.textContent = 'Speed ' + e.target.value + '×'; });
    $('#pl-close').addEventListener('click', function () { clock.pause(); sents.forEach(function (s) { s.classList.remove('is-reading'); }); if (wEls[cur]) wEls[cur].classList.remove('is-word'); cur = -1; status.textContent = 'Player closed'; toast('Player closed', 'Listen again from the line under the answer’s title.', 'info'); });
    sents.forEach(function (s) {
      s.addEventListener('click', function (e) {
        if (e.target.closest('.cite')) return;
        var w = e.target.closest('.w'), k = w ? wEls.indexOf(w) : firstWord[s.getAttribute('data-sid')];
        if (k < 0) k = firstWord[s.getAttribute('data-sid')];
        clock.currentTime = W[k].start; if (clock.paused) start();
      });
    });
    clock.currentTime = +text.getAttribute('data-rest-t') || 0;
    render();
    return { start: function () { start(); } };
  })();
  $$('[data-listen]').forEach(function (b) {
    b.addEventListener('click', function () {
      if (!L) return;
      var p = $('#player');
      p.scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'center' });
      $('#pl-play').focus({ preventScroll: true });
      L.start();
    });
  });

  var V = (function () {
    var svg = $('#vid-svg'); if (!svg || !svg.animate) return null;
    var cloth = $('#v-cloth'), ox = $('#v-ox'), drips = $('#v-drips'), range = $('#vid-range'), time = $('#vid-time'), btn = $('#vid-play'), phase = $('#vid-phase');
    ox.style.transformBox = 'fill-box'; ox.style.transformOrigin = '50% 0';
    var DUR = 8000;
    var anims = [
      cloth.animate([{ transform: 'translateY(440px)' }, { transform: 'translateY(440px)', offset: 0.05 }, { transform: 'translateY(0px)', offset: 0.33 }, { transform: 'translateY(0px)' }], { duration: DUR, fill: 'both', easing: 'linear' }),
      ox.animate([{ transform: 'scaleY(0.001)' }, { transform: 'scaleY(0.001)', offset: 0.4 }, { transform: 'scaleY(1)', offset: 0.92 }, { transform: 'scaleY(1)' }], { duration: DUR, fill: 'both', easing: 'linear' }),
      drips.animate([{ opacity: 0 }, { opacity: 0, offset: 0.3 }, { opacity: 1, offset: 0.36 }, { opacity: 1 }], { duration: DUR, fill: 'both' })
    ];
    var raf = null;
    function setT(t) { anims.forEach(function (a) { a.currentTime = t; }); show(t); }
    function show(t) {
      range.value = Math.round(t);
      time.textContent = mmss(t / 1000) + ' / ' + mmss(DUR / 1000);
      phase.textContent = t < 2600 ? 'In the vat' : t < 3400 ? 'Lifted, green' : 'Blue in the air';
    }
    function loop() { var t = anims[0].currentTime || 0; show(t); if (t >= DUR) { stop(); return; } raf = requestAnimationFrame(loop); }
    function stop() { anims.forEach(function (a) { a.pause(); }); cancelAnimationFrame(raf); btn.innerHTML = btn.getAttribute('data-play'); btn.setAttribute('aria-label', 'Play the video'); }
    function play() {
      if ((anims[0].currentTime || 0) >= DUR - 30) setT(0);
      if (reduced()) { setT(DUR); stop(); toast('Video shown at its last frame', 'With reduced motion the cloth shows blue in the air.', 'info'); return; }
      anims.forEach(function (a) { a.play(); }); btn.innerHTML = btn.getAttribute('data-pause'); btn.setAttribute('aria-label', 'Pause the video'); raf = requestAnimationFrame(loop);
    }
    btn.addEventListener('click', function () { if (anims[0].playState === 'running') stop(); else play(); });
    range.addEventListener('input', function () { stop(); setT(+range.value); });
    stop(); setT(DUR);
    return {};
  })();

  var FS = JSON.parse(($('#film-subs') || { textContent: '{"subs":[],"labels":[]}' }).textContent);
  var F = (function () {
    var film = $('#film'); if (!film) return null;
    var scenes = $$('.film-scene', film), sub = $('#film-sub'), range = $('#film-range'), time = $('#film-time'), btn = $('#film-play'), ticks = $$('#film-ticks i'), lab = $('#film-scene-l');
    var strip = $$('#film-strip .fs-b');
    var SCENE = 8000, ready = 7, t = 0, playing = false, last = 0, raf = null;
    function maxT() { return ready * SCENE; }
    function show() {
      var k = Math.min(scenes.length - 1, Math.floor(t / SCENE));
      scenes.forEach(function (s, i) { s.classList.toggle('on', i === k); });
      if (sub.getAttribute('data-k') !== String(k)) { sub.innerHTML = FS.subs[k]; sub.setAttribute('data-k', k); lab.textContent = 'Scene ' + (k + 1) + ' · ' + FS.labels[k]; }
      ticks.forEach(function (x, i) { x.className = (i < ready ? 'ready' : '') + (i === k ? ' cur' : ''); });
      strip.forEach(function (b, i) {
        b.setAttribute('aria-pressed', String(i === k));
        var on = i < ready; b.classList.toggle('forming', !on);
        if (on) b.removeAttribute('aria-disabled'); else b.setAttribute('aria-disabled', 'true');
      });
      range.value = Math.round(t);
      time.textContent = mmss(t / 1000) + ' / ' + mmss(scenes.length * SCENE / 1000);
    }
    function frame(now) { if (!playing) return; t += (now - last); last = now; if (t >= maxT()) { t = Math.min(t, maxT() - 1); pause(); if (ready < scenes.length) toast('The preview ends at scene ' + ready, 'Scene 7 arrives when section 7 is written.', 'info'); } show(); if (playing) raf = requestAnimationFrame(frame); }
    function play() { if (ready === 0) { toast('No scenes yet', 'Scenes arrive as each section is written.', 'info'); return; } if (t >= maxT() - 50) t = 0; if (reduced()) { show(); } playing = true; btn.innerHTML = btn.getAttribute('data-pause'); btn.setAttribute('aria-label', 'Pause the film'); last = performance.now(); raf = requestAnimationFrame(frame); }
    function pause() { playing = false; cancelAnimationFrame(raf); btn.innerHTML = btn.getAttribute('data-play'); btn.setAttribute('aria-label', 'Play the film'); }
    btn.addEventListener('click', function () { if (playing) pause(); else play(); });
    range.addEventListener('input', function () { pause(); t = Math.min(+range.value, maxT() - 1); show(); });
    strip.forEach(function (b, i) { b.addEventListener('click', function () { if (i >= ready) { toast('Scene ' + (i + 1) + ' is arriving', 'It appears when its section is written.', 'info'); return; } pause(); t = i * SCENE; show(); }); });
    show();
    return { setReady: function (n) { ready = n; if (t >= maxT()) t = 0; show(); }, ready: function () { return ready; } };
  })();

  function download(name, text, type) {
    try {
      var blob = new Blob([text], { type: type });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
      toast('Downloaded', name, 'success');
    } catch (e) { toast('The download did not start', 'Try again in a moment.', 'error'); }
  }
  function defsFor() {
    var defs = $('#ai-defs'), parts = [];
    $$('defs > *, symbol', defs).forEach(function (n) { parts.push(n.outerHTML); });
    return '<defs>' + parts.join('') + '</defs>';
  }
  function standalone(inner, extraStyle) {
    return '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1200 800" width="1200" height="800">' + (extraStyle ? '<style>' + extraStyle + '</style>' : '') + defsFor() + inner + '</svg>';
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-dl-ill]');
    if (b && !b.disabled) { download(b.getAttribute('data-name') + '.svg', standalone('<use href="#' + b.getAttribute('data-dl-ill') + '" width="1200" height="800"/><text x="24" y="776" font-family="sans-serif" font-size="18" fill="#fff" fill-opacity=".85">AI illustration</text>'), 'image/svg+xml'); return; }
    var v = e.target.closest('[data-dl-video]');
    if (v) {
      var svg = $('#vid-svg').cloneNode(true);
      var css = '#v-cloth{animation:rise 8s linear infinite}#v-ox{transform-box:fill-box;transform-origin:50% 0;animation:ox 8s linear infinite}#v-drips{animation:dr 8s linear infinite}' +
        '@keyframes rise{0%,5%{transform:translateY(440px)}33%,100%{transform:none}}@keyframes ox{0%,40%{transform:scaleY(.001)}92%,100%{transform:scaleY(1)}}@keyframes dr{0%,30%{opacity:0}36%,100%{opacity:1}}';
      var inner = svg.innerHTML.replace(/ style="[^"]*"/g, '');
      download(v.getAttribute('data-name') + '.svg', standalone(inner + '<text x="24" y="776" font-family="sans-serif" font-size="18" fill="#fff" fill-opacity=".85">AI video</text>', css), 'image/svg+xml');
    }
  });
  function plainSub(h) { var tmp = document.createElement('div'); tmp.innerHTML = h; var c = tmp.querySelector('.cite'); var n = c ? c.textContent : ''; if (c) c.remove(); return { t: tmp.textContent.trim(), n: n }; }
  var vtt = $('#film-vtt');
  if (vtt) vtt.addEventListener('click', function () {
    var out = 'WEBVTT\n\nNOTE AI video. Subtitles are the cited sentences of the answer; numerals point to its source list.\n\n';
    FS.subs.forEach(function (h, i) {
      var p = plainSub(h), a = i * 8, b = a + 8;
      out += (i + 1) + '\n00:' + ('0' + Math.floor(a / 60)).slice(-2) + ':' + ('0' + (a % 60)).slice(-2) + '.000 --> 00:' + ('0' + Math.floor(b / 60)).slice(-2) + ':' + ('0' + (b % 60)).slice(-2) + '.000\n' + p.t + (p.n ? ' [' + p.n + ']' : '') + '\n\n';
    });
    download(vtt.getAttribute('data-name') + '.vtt', out, 'text/vtt');
  });
  var filmDl = $('#film-dl');
  if (filmDl) filmDl.addEventListener('click', function () {
    var syms = ['ai-vat', 'ai-route', 'ai-cloth', 'ai-river', 'ai-bolts', 'ai-mizan', 'ai-saaj'], css = '', inner = '';
    syms.forEach(function (s, i) {
      var p = plainSub(FS.subs[i]);
      var a = (i / 7 * 100).toFixed(2), b = ((i + 1) / 7 * 100).toFixed(2);
      css += '.sc' + i + '{opacity:0;animation:s' + i + ' 56s linear infinite}@keyframes s' + i + '{0%{opacity:0}' + (i === 0 ? '0%,' : (a - 0.5).toFixed(2) + '%{opacity:0}' + a + '%,') + (b - 0.5).toFixed(2) + '%{opacity:1}' + b + '%,100%{opacity:0}}';
      inner += '<g class="sc' + i + '"><use href="#' + s + '" width="1200" height="800"/><rect x="0" y="680" width="1200" height="120" fill="#000" fill-opacity=".45"/><text x="600" y="740" text-anchor="middle" font-family="Georgia,serif" font-size="26" fill="#fbfaf6">' + esc(p.t.slice(0, 110)) + (p.n ? ' [' + p.n + ']' : '') + '</text></g>';
    });
    download(filmDl.getAttribute('data-name') + '.svg', standalone(inner + '<text x="24" y="40" font-family="sans-serif" font-size="18" fill="#fff" fill-opacity=".85">AI video · AI music and sound</text>', css), 'image/svg+xml');
  });

  var G = (function () {
    var wrap = $('#gen'); if (!wrap) return null;
    var secs = $$('.gsec', $('#gen-secs')), bar = $$('#gen-bar i'), go = $('#gen-go'), reset = $('#gen-reset'), toggle = $('#ill-toggle');
    var state = $('#gen-state'), timers = [], running = false;
    var ICON = { done: ICON_OK, writing: '<svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2 12 L2.6 9.4 L9.6 2.4 L11.6 4.4 L4.6 11.4 Z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg>', queued: '<svg viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="5.6" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M7 4 V7.3 L9.2 8.6" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>' };
    var LABEL = { done: 'Written', writing: 'Writing', queued: 'Queued' };
    function on() { return toggle.getAttribute('aria-checked') === 'true'; }
    function later(fn, ms) { var id = setTimeout(fn, reduced() ? Math.min(ms, 40) : ms); timers.push(id); }
    function clear() { timers.forEach(clearTimeout); timers = []; }
    function setSec(sec, st, shown) {
      sec.setAttribute('data-state', st);
      if (st === 'done') sec.removeAttribute('aria-busy'); else sec.setAttribute('aria-busy', 'true');
      var n = +sec.getAttribute('data-n');
      sec.querySelector('.gsec-st').innerHTML = ICON[st] + LABEL[st];
      var ss = $$('.gsec-text .s', sec);
      if (shown === undefined) shown = st === 'done' ? ss.length : 0;
      sec.setAttribute('data-shown', shown);
      ss.forEach(function (s, i) { s.classList.toggle('pending', i >= shown); });
      var bi = bar[n - 1]; bi.className = st === 'done' ? 'done' : st === 'writing' ? 'writing' : '';
      if (st === 'writing') bi.style.setProperty('--w', Math.round(Math.max(shown, 0.4) / ss.length * 100) + '%');
    }
    function job(n, html, thumb) {
      var li = $('#jobs [data-job="' + n + '"]'); if (!li) return;
      li.querySelector('.js').innerHTML = html;
      var th = li.querySelector('.th'); th.classList.toggle('drawing', thumb === 'drawing'); th.classList.toggle('empty', thumb === 'empty');
    }
    function artOf(sec) { return sec.querySelector('figure.ai:not([data-kind]) .ai-art'); }
    function setDraw(sec, p) {
      var art = artOf(sec); if (!art) return;
      var pill = art.querySelector('.ai-job-t'), meter = art.querySelector('.meter b'), dl = sec.querySelector('figure.ai:not([data-kind]) .dl');
      if (p === null) { art.classList.remove('is-drawing'); art.style.removeProperty('--p'); if (dl) dl.disabled = false; return; }
      art.classList.add('is-drawing'); art.style.setProperty('--p', p + '%');
      pill.textContent = 'Drawing · ' + p + '%'; meter.style.width = p + '%';
      if (dl) dl.disabled = true;
    }
    function media(sec, show) { $$('.gsec-media', sec).forEach(function (m) { m.hidden = !show; }); }
    function drawIll(sec, n, done) {
      media(sec, true);
      var steps = 10, k = 0;
      setDraw(sec, 0);
      job(n, '<span class="jm"><b style="width:0%"></b></span><span>Drawing</span>', 'drawing');
      (function step() {
        k++; var p = Math.round(k / steps * 100);
        if (k < steps) { setDraw(sec, p); var jm = $('#jobs [data-job="' + n + '"] .jm b'); if (jm) jm.style.width = p + '%'; later(step, 170); return; }
        setDraw(sec, null);
        job(n, ICON.done + 'Ready', 'ready');
        done();
      })();
    }
    function filmReady(nr) {
      if (F) F.setReady(nr);
      $('#film-meta').textContent = '7 scenes, one a section · 0:56 · ' + (nr < 7 ? nr + ' of 7 scenes ready' : 'ready');
      var fj = $('#jobs [data-job="film"] .js');
      fj.innerHTML = nr < 7 ? '<span class="jm"><b style="width:' + Math.round(nr / 7 * 100) + '%"></b></span><span>' + nr + ' of 7 scenes</span>' : ICON.done + 'Ready, 0:56';
      $('#film-dl').disabled = nr < 7;
      $('#film-note').textContent = nr < 7 ? 'Subtitles are the cited sentences, one from each section. The film can be saved when scene 7 arrives.' : 'Subtitles are the cited sentences, one from each section.';
    }
    function writeSec(i, cb) {
      var sec = secs[i]; if (!sec) { cb(); return; }
      var total = +sec.getAttribute('data-total');
      var shown = sec.getAttribute('data-state') === 'writing' ? +sec.getAttribute('data-shown') : 0;
      setSec(sec, 'writing', shown);
      state.firstChild.nodeValue = 'Writing section ' + (i + 1) + ' of 7';
      $('#gen-sub').textContent = i === 0 ? 'Reading the curated sources' : 'Sections 1 to ' + i + ' are written' + (on() ? ' and illustrated' : '');
      (function next() {
        if (shown < total) { shown++; setSec(sec, 'writing', shown); later(next, 480); return; }
        setSec(sec, 'done');
        if (!on()) { cb(); return; }
        drawIll(sec, i + 1, function () {
          if (i === 0) job('v1', ICON.done + 'Ready', 'ready');
          filmReady(i + 1);
          cb();
        });
      })();
    }
    function finish() {
      running = false; go.textContent = 'Continue writing'; go.disabled = true;
      state.firstChild.nodeValue = 'Answer written';
      $('#gen-sub').textContent = on() ? '7 sections, 7 illustrations, 1 video and the film' : '7 sections';
      if (on()) toast('Film ready', '7 scenes, 0:56, subtitled with the cited sentences.', 'success');
    }
    function runFrom(i) {
      running = true; go.disabled = true; go.textContent = 'Writing';
      (function loop(k) {
        if (k >= secs.length) { finish(); return; }
        writeSec(k, function () { later(function () { loop(k + 1); }, 220); });
      })(i);
    }
    go.addEventListener('click', function () {
      if (running) return;
      var i = secs.findIndex(function (s) { return s.getAttribute('data-state') !== 'done'; });
      if (i < 0) return;
      var sec = secs[i];
      if (sec.getAttribute('data-state') === 'writing' && artOf(sec) && artOf(sec).classList.contains('is-drawing')) {
        running = true; go.disabled = true; go.textContent = 'Writing';
        var total = +sec.getAttribute('data-total'), shown = +sec.getAttribute('data-shown');
        (function next() {
          if (shown < total) { shown++; setSec(sec, 'writing', shown); later(next, 480); return; }
          setSec(sec, 'done');
          var p = parseInt(artOf(sec).style.getPropertyValue('--p'), 10) || 0;
          (function step() {
            p = Math.min(100, p + 8);
            if (p < 100) { setDraw(sec, p); later(step, 150); return; }
            setDraw(sec, null); job(i + 1, ICON.done + 'Ready', 'ready'); filmReady(i + 1); finish();
          })();
        })();
        return;
      }
      runFrom(i);
    });
    reset.addEventListener('click', function () {
      clear(); running = false;
      secs.forEach(function (s) { setSec(s, 'queued'); setDraw(s, null); media(s, false); });
      $$('#jobs li').forEach(function (li) { var j = li.getAttribute('data-job'); if (j !== 'film') { li.querySelector('.js').innerHTML = ICON.queued + 'Queued'; var th = li.querySelector('.th'); th.classList.add('empty'); th.classList.remove('drawing'); } });
      filmReady(0);
      go.disabled = true;
      later(function () { runFrom(0); }, 200);
    });
    toggle.addEventListener('click', function () {
      var v = !on();
      toggle.setAttribute('aria-checked', String(v));
      wrap.classList.toggle('is-off', !v);
      toast(v ? 'Illustrations on' : 'Illustrations off', v ? 'Each section arrives with an AI illustration; the film follows the answer.' : 'The answer is written as usual, with photographs only.', 'info');
    });
    return {};
  })();

  var VF = (function () {
    var fig = $('#vatfig'); if (!fig) return null;
    var btn = $('#vf-dip'), status = $('#vf-status'), frames = $$('.frame', fig), dipLis = $$('.dips li', fig);
    var dips = 1, running = false, timers = [];
    var SAY = { vat: 'In the vat: the dissolved dye soaks into the fibre.', lifted: 'Lifted: the cloth comes out bright green.', air: 'In the air the cloth turns from green to blue.' };
    function setPhase(ph) {
      fig.setAttribute('data-phase', ph);
      frames.forEach(function (f) { if (f.getAttribute('data-frame') === ph) f.setAttribute('aria-current', 'step'); else f.removeAttribute('aria-current'); });
      status.textContent = 'Dip ' + dips + ' of 4. ' + SAY[ph];
    }
    function setDips(n) { dips = n; fig.setAttribute('data-dips', n); dipLis.forEach(function (li) { li.classList.toggle('on', +li.getAttribute('data-n') === n); }); }
    function idle() {
      running = false; fig.classList.remove('run-vat', 'run-lift', 'run-air');
      btn.textContent = dips >= 4 ? 'Start again' : 'Dip again';
      if (dips >= 4) status.textContent = 'Dip 4 of 4: the darkest blue. Start again to replay from the first dip.';
    }
    btn.addEventListener('click', function () {
      if (running) return;
      setDips(dips >= 4 ? 1 : dips + 1);
      if (reduced()) { setPhase('air'); idle(); return; }
      running = true;
      fig.classList.remove('run-vat', 'run-lift', 'run-air'); void fig.offsetWidth;
      setPhase('vat'); fig.classList.add('run-vat');
      timers.push(setTimeout(function () { setPhase('lifted'); fig.classList.add('run-lift'); }, 600));
      timers.push(setTimeout(function () { setPhase('air'); fig.classList.add('run-air'); }, 1100));
      timers.push(setTimeout(idle, 2650));
    });
    return {};
  })();

  $$('.lang-seg button').forEach(function (b) {
    b.addEventListener('click', function () {
      var lang = b.getAttribute('data-lang');
      $$('.lang-seg button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      var demo = $('#lang-demo');
      $$('.lang-panel', demo).forEach(function (p) { closeCtx(p); p.hidden = p.getAttribute('data-lang-panel') !== lang; });
      $('#lang-status').textContent = { en: 'English · as written', hi: 'हिन्दी · translated from English; quotes stay verbatim in English', ur: 'اردو · translated from English; quotes stay verbatim in English' }[lang];
      fitAll(); qmoreAll();
      if (window.innerWidth >= 1200) {
        var panel = $('.lang-panel[data-lang-panel="' + lang + '"]', demo);
        var holder = panel.querySelector('[data-rest-open]');
        var c = holder ? panel.querySelector('.cite[data-sid="' + holder.getAttribute('data-rest-open') + '"]') : null;
        if (c) openCite(c, { focus: false, force: true });
      }
    });
  });
  $$('[data-orig]').forEach(function (b) {
    b.addEventListener('click', function () {
      var t = document.getElementById(b.getAttribute('data-orig'));
      var show = t.hidden;
      t.hidden = !show; b.setAttribute('aria-expanded', String(show));
      b.textContent = show ? b.getAttribute('data-hide') : b.getAttribute('data-show');
      placeOpen();
    });
  });

  var ready = document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve();
  qmoreAll();
  ready.then(function () { fitAll(); qmoreAll(); restOpen(); placeOpen(); });
  window.addEventListener('load', function () { fitAll(); placeOpen(); });
})();

});
