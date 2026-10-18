/* Guide Studio: inspect a compiled guide (sources -> steps -> G2 frames) and hand it to the runtime.
 * Reads GET /studio/guides, /cards/{id}, /studio/preview/{id}, /state; opens a guide with the companion's own
 * POST /session/connect + /session/goal (+ /discovery/* for product manuals). Server text only via textContent. */
(function () {
  'use strict';
  var S = window.GBStudio, Q = new URLSearchParams(location.search);
  var CORE = (Q.get('core') || '').replace(/\/+$/, '');
  var st = { guides: [], live: null, card: null, prev: null, guide: null, step: null, pic: 0, poll: null };
  function $(id) { return document.getElementById(id); }
  function h(tag, attrs) {
    var n = document.createElement(tag), kids = Array.prototype.slice.call(arguments, 2);
    Object.keys(attrs || {}).forEach(function (k) { if (k === 'text') n.textContent = attrs[k]; else if (attrs[k] != null) n.setAttribute(k, attrs[k]); });
    kids.forEach(function (c) { if (c != null) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); return n; }
  function url(p) { return CORE + p; }
  function getJson(p) { return fetch(url(p), { cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error(p + ' ' + r.status); return r.json(); }); }
  function postJson(p, body) {
    return fetch(url(p), { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok) throw new Error((j && j.detail) || (p + ' ' + r.status)); return j; }); });
  }
  function chip(text, cls) { return h('span', { class: 'chip-s ' + (cls || ''), text: text }); }
  function link(href, text) { return h('a', { href: href, target: '_blank', rel: 'noopener noreferrer', text: text }); }

  // ------------------------------------------------------------ guides + live compile status
  function loadGuides() {
    return getJson('/studio/guides').then(function (d) {
      st.guides = d.guides || []; st.live = d.live; setChip(true); renderChips(); renderLive();
    }).catch(function () { setChip(false); });
  }
  function setChip(ok) { var c = $('link-chip'); c.className = 'chip ' + (ok ? 'chip-ok' : 'chip-bad'); c.textContent = ok ? 'CORE CONNECTED' : 'CORE UNREACHABLE'; }
  function renderChips() {
    var box = clear($('guide-chips'));
    st.guides.filter(function (g) { return g.sources.length && (g.cited || g.quoted); }).forEach(function (g) {
      var b = h('button', { type: 'button', class: 'gchip' + (st.guide && st.guide.card_id === g.card_id ? ' on' : '') },
        h('b', { text: g.title }), h('small', { text: (S.host(g.sources[0].url) || '') + ' · ' + g.steps + ' steps' + (g.questions ? ' · ' + g.questions + ' questions' : '') }));
      b.addEventListener('click', function () { select(g.card_id); });
      box.appendChild(b);
    });
    if (!box.children.length) box.appendChild(h('p', { class: 'meta', text: 'No source-grounded guide is loaded on this backend.' }));
  }
  function renderLive() {
    var v = S.liveView(st.live), box = clear($('live'));
    box.className = 'live-box live-' + v.state;
    if (v.state === 'running') {
      box.appendChild(h('div', { class: 'live-head' }, h('span', { class: 'spin', 'aria-hidden': 'true' }), h('strong', { text: 'Compiling “' + v.goal + '”' }), h('span', { class: 'live-time', text: v.elapsed + ' s' })));
      var bar = h('div', { class: 'live-track', role: 'progressbar', 'aria-valuenow': String(Math.round(v.fraction * 100)) }, h('i', { style: 'width:' + Math.round(v.fraction * 100) + '%' }));
      box.appendChild(bar); box.appendChild(h('p', { class: 'meta', text: v.stage + ' · progress is an estimate from past runs, not a measurement' }));
    } else box.appendChild(h('p', { class: 'meta', text: v.text + (v.state === 'done' && v.goal ? ' “' + v.goal + '”.' : '') }));
  }

  // ------------------------------------------------------------ URL input
  $('src-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var raw = $('src-url').value.trim(), m = S.matchUrl(st.guides, raw), out = clear($('src-result'));
    if (!m.valid) { out.appendChild(h('p', { class: 'err', text: 'Enter a full http(s) link to a manufacturer page or manual PDF.' })); return; }
    if (m.exact.length) {
      out.appendChild(h('p', { class: 'ok' }, h('b', { text: 'Found. ' }), document.createTextNode(m.exact.length + ' compiled guide' + (m.exact.length > 1 ? 's use' : ' uses') + ' this exact source: “' + m.exact[0].source.title + '”.')));
      select(m.exact[0].card_id); return;
    }
    if (m.site.length) out.appendChild(h('p', { class: 'warn', text: 'No guide was compiled from this exact page yet. Guides from the same site (' + S.host(raw) + '):' }));
    else out.appendChild(h('p', { class: 'warn', text: 'No loaded guide was compiled from ' + S.host(raw) + ' yet.' }));
    m.site.forEach(function (x) { var b = h('button', { type: 'button', class: 'ghost', text: x.title }); b.addEventListener('click', function () { select(x.card_id); }); out.appendChild(b); });
    var lv = S.liveView(st.live);
    out.appendChild(h('p', { class: 'meta', text: lv.state === 'off' ? 'Compiling a new source needs live research on the backend (GB_LIVE_RESEARCH=1), which is off here. Nothing was sent anywhere.'
      : 'Describe the task in the companion to compile it from official sources; progress appears above.' }));
  });

  // ------------------------------------------------------------ select a guide
  function select(id) {
    st.guide = st.guides.filter(function (g) { return g.card_id === id; })[0] || null;
    renderChips();
    $('open-result').textContent = '';
    return Promise.all([getJson('/cards/' + encodeURIComponent(id)), getJson('/studio/preview/' + encodeURIComponent(id))]).then(function (r) {
      st.card = r[0]; st.prev = r[1]; st.step = firstInteresting(st.card); st.pic = 0;
      if (Q.get('step')) st.step = Q.get('step');
      $('studio').hidden = false; renderPipeline(); renderRoute(); renderStep();
      history.replaceState(null, '', '?guide=' + encodeURIComponent(id) + (CORE ? '&core=' + encodeURIComponent(CORE) : ''));
    }).catch(function (e) { clear($('src-result')).appendChild(h('p', { class: 'err', text: 'Could not load this guide: ' + e.message })); });
  }
  function firstInteresting(card) {
    var s = card.steps.filter(function (x) { return x.guide_id && x.cites && x.cites.length; })[0];
    return (s || card.steps[0]).id;
  }
  function renderPipeline() {
    var g = st.guide, b = (st.prev && st.prev.build) || null, box = clear($('pipeline')); box.hidden = false;
    var srcN = b && b.sources ? b.sources.length : g.sources.length;
    var read = b && b.sources ? b.sources.reduce(function (a, s) { return a + (s.blocks || 0); }, 0) + ' text blocks read' : g.sources.map(function (s) { return s.kind; }).filter(function (k, i, a) { return a.indexOf(k) === i; }).join(' · ');
    var stages = [
      ['Sources', srcN + (srcN === 1 ? ' document' : ' documents'), read],
      ['Compiled', g.steps + ' steps', g.quoted ? g.quoted + ' quote their source verbatim' : g.cited + ' cite a manual page'],
      ['Decisions', g.questions ? g.questions + ' questions' : 'One route', (g.questions ? g.endings + ' endings · ' : 'no branches · ') + (g.hazards ? g.hazards + ' safety steps' : 'no safety stops')],
      ['Pictures', g.pictures + ' views', 'from the cited sources'],
      ['G2 frames', st.prev.steps.length + st.prev.steps.reduce(function (a, s) { return a + s.pictures.length; }, 0) + ' frames', 'from the same HUD writer']
    ];
    stages.forEach(function (x) { box.appendChild(h('div', { class: 'stage' }, h('b', { text: x[0] }), h('div', { class: 'n', text: x[1] }), h('div', { class: 's', text: x[2] }))); });
    var lab = h('div', { class: 'pipe-labels' });
    S.guideLabels(g).forEach(function (l) { lab.appendChild(chip(l, /NOT HUMAN/.test(l) ? 'amber' : '')); });
    if (b) lab.appendChild(chip('BUILD RECORD: ' + (b.rounds || 1) + ' ROUND · ' + ((b.errors || []).length) + ' VALIDATION ERRORS' + (b.total_s ? ' · ' + Math.round(b.total_s) + ' S' : ''), 'dim'));
    box.appendChild(lab);
    if (b && b.notes && b.notes.length) {
      var d = h('details', { class: 'gaps' }, h('summary', { text: 'What the sources did not cover (' + b.notes.length + ')' }));
      b.notes.forEach(function (n) { d.appendChild(h('p', { class: 'meta', text: n.replace(/^uncovered:\s*/, '') })); });
      box.appendChild(d);
    }
  }
  function renderRoute() {
    var ol = clear($('route')), rs = S.routes(st.card), alt = S.branchOnly(st.card);
    $('route-count').textContent = st.card.steps.length + ' steps';
    rs.forEach(function (r) {
      var li = h('li', { class: 'r r-' + r.kind + (r.risk === 'hazard' ? ' r-hazard' : '') + (alt[r.id] ? ' r-alt' : '') + (r.id === st.step ? ' on' : '') });
      var b = h('button', { type: 'button' }, h('span', { class: 'rn', text: r.kind === 'question' ? '?' : r.kind === 'stop' ? '■' : r.kind === 'outcome' ? '◆' : String(r.n) }), h('span', { class: 'rt', text: r.title }));
      if (r.risk === 'hazard') b.appendChild(chip('SAFETY', 'red'));
      b.addEventListener('click', function () { st.step = r.id; st.pic = 0; renderRoute(); renderStep(); });
      li.appendChild(b);
      if (r.kind === 'question') { var ul = h('ul', { class: 'r-to' }); r.to.forEach(function (t) { ul.appendChild(h('li', { text: t.label + ' → ' + (t.title || 'end') })); }); li.appendChild(ul); }
      ol.appendChild(li);
    });
  }
  function stepOf(id) { return st.card.steps.filter(function (s) { return s.id === id; })[0]; }
  function renderStep() {
    var s = stepOf(st.step) || st.card.steps[0], i = st.card.steps.indexOf(s), r = S.routes(st.card)[i];
    $('step-eyebrow').textContent = 'STEP ' + (i + 1) + ' OF ' + st.card.steps.length + ' · ' + (s.kind || 'action').toUpperCase();
    $('h-step').textContent = s.title;
    var chips = clear($('step-chips'));
    chips.appendChild(chip(s.kind === 'stop' ? 'STOP SAFELY · GUIDE ENDS' : s.kind === 'outcome' ? 'RESULT · GUIDE ENDS' : s.kind === 'question' ? 'YOU ANSWER' : s.verify ? 'MEASURED: EVIDENCE COMPLETES IT' : 'MANUAL: YOU CONFIRM IT', s.kind === 'stop' ? 'red' : 'dim'));
    if (s.risk === 'hazard') chips.appendChild(chip('SAFETY STEP · CONFIRM TWICE', 'red'));
    else if (s.risk === 'caution') chips.appendChild(chip('CAUTION', 'amber'));
    if (s.expected) chips.appendChild(chip('EXPECT: ' + s.expected, 'dim'));
    $('step-detail').textContent = s.detail || '';
    var w = clear($('step-warn')); (s.warnings || []).forEach(function (x) { w.appendChild(h('p', { class: 'warnline', text: '⚠ ' + x })); });
    var c = clear($('step-choices'));
    if (r.to.length && s.kind === 'question') {
      c.appendChild(h('h3', { text: 'Decision' }));
      r.to.forEach(function (t) { var b = h('button', { type: 'button', class: 'branch' }, h('b', { text: t.label }), h('span', { text: '→ ' + (t.title || 'end') })); b.addEventListener('click', function () { if (t.to) { st.step = t.to; st.pic = 0; renderRoute(); renderStep(); } }); c.appendChild(b); });
    } else if (r.ends) c.appendChild(h('p', { class: 'meta', text: s.kind === 'stop' ? 'The guide stops safely here.' : 'This route ends here.' }));
    else if (r.to[0]) c.appendChild(h('p', { class: 'meta', text: 'Next: ' + r.to[0].title }));
    renderEvidence(s); renderPic(s, i); renderFrames(i);
  }
  function renderEvidence(s) {
    var box = clear($('step-evidence')), ev = S.evidence(st.card, s);
    if (!ev.length) { box.appendChild(h('p', { class: 'meta', text: 'No source citation on this step (' + (st.card.provenance || 'authored') + ').' })); return; }
    ev.forEach(function (e) {
      var card = h('div', { class: 'cite' });
      if (e.quote) card.appendChild(h('blockquote', { text: '“' + e.quote + '”' }));
      var meta = h('div', { class: 'cite-meta' });
      if (e.kind) meta.appendChild(chip(e.kind));
      if (e.quote) meta.appendChild(chip('QUOTED FROM SOURCE', 'dim'));
      meta.appendChild(h('span', { text: e.title + (e.page ? ' · page ' + e.page : e.loc && e.loc !== 'quoted passage' ? ' · ' + e.loc : '') }));
      card.appendChild(meta);
      if (e.url) card.appendChild(h('div', { class: 'cite-link' }, link(e.url, 'Open the source' + (e.page ? ' at page ' + e.page : '') + ' ↗'), h('span', { class: 'meta', text: ' ' + e.host })));
      box.appendChild(card);
    });
  }
  function previewOf(i) { return (st.prev && st.prev.steps[i]) || { pictures: [] }; }
  function renderPic(s, i) {
    var box = clear($('pic')), pics = previewOf(i).pictures, prov = $('pic-prov');
    if (!pics.length) { prov.textContent = ''; prov.hidden = true; box.appendChild(h('p', { class: 'meta', text: 'This step has no picture in the guide. The glasses show its text only.' })); return; }
    var p = pics[Math.min(st.pic, pics.length - 1)];
    prov.hidden = false; prov.textContent = p.provenance; prov.className = 'pill pill-prov';
    if (pics.length > 1) {
      var tabs = h('div', { class: 'tabs', role: 'tablist' });
      pics.forEach(function (x, k) { var b = h('button', { type: 'button', role: 'tab', 'aria-selected': String(k === st.pic), class: k === st.pic ? 'on' : '', text: x.title || x.view }); b.addEventListener('click', function () { st.pic = k; renderStep(); }); tabs.appendChild(b); });
      box.appendChild(tabs);
    }
    if (p.phone_available || p.available) {
      var fig = h('figure', { class: 'pic' }), im = h('img', { alt: p.depicts || p.title, src: url(p.phone_url) });
      im.onerror = function () { fig.replaceChild(h('p', { class: 'err', text: 'Picture failed to load from the core.' }), im); };
      fig.appendChild(im); fig.appendChild(h('figcaption', { text: p.depicts || '' })); box.appendChild(fig);
    } else box.appendChild(h('div', { class: 'pic-missing' }, h('b', { text: 'Picture not cached on this backend' }), h('p', { class: 'meta', text: 'Third-party source photos stay local to the machine that compiled the guide. The glasses fall back to the step text. ' + (p.depicts || '') })));
    if (p.reference_url) box.appendChild(h('p', { class: 'cite-link' }, link(p.reference_url, 'See it in the original ' + (S.pageOf({ url: p.reference_url }) ? '(page ' + S.pageOf({ url: p.reference_url }) + ')' : 'source') + ' ↗')));
  }
  function mirror(frame, label) {
    var t = S.frameText(frame), g = h('div', { class: 'g2 g2-s' }), inner = h('div', { class: 'g2-inner' });
    if (t.kind === 'menu') { inner.classList.add('g2-menu'); inner.appendChild(h('div', { class: 'g2-l1', text: t.l1 })); t.options.forEach(function (o) { inner.appendChild(h('div', { class: 'opt', text: o })); }); }
    else if (t.kind === 'empty') { inner.classList.add('g2-empty'); inner.appendChild(h('div', { text: t.l1 })); }
    else {
      if (t.image) { inner.classList.add('g2-vis'); var box = h('div', { class: 'g2-img' }), im = h('img', { alt: 'G2 picture ' + t.image.view, src: url(t.image.url) + '?v=' + String(t.image.sha256 || '').slice(0, 10) }); im.onerror = function () { box.remove(); }; box.appendChild(im); inner.appendChild(box); }
      inner.appendChild(h('div', { class: 'g2-l1', text: t.l1 })); if (t.l2) inner.appendChild(h('div', { class: 'g2-l2', text: t.l2 }));
    }
    g.appendChild(inner); if (t.tag) g.appendChild(h('div', { class: 'g2-tag', text: t.tag }));
    return h('figure', { class: 'g2-fig' }, g, h('figcaption', { class: 'meta', text: label }));
  }
  function renderFrames(i) {
    var box = clear($('g2-frames')), p = previewOf(i);
    if (p.frame) box.appendChild(mirror(p.frame, 'When the step opens · mode ' + p.frame.mode + (p.frame.image ? ' · picture ' + p.frame.image.w + '×' + p.frame.image.h : '')));
    var k = Math.min(st.pic, p.pictures.length - 1);
    if (k >= 0 && p.pictures[k] && p.pictures[k].frame && p.pictures[k].frame.mode === 'visual') box.appendChild(mirror(p.pictures[k].frame, 'Press on the glasses → ' + p.pictures[k].title + ' picture (' + (k + 1) + ' of ' + p.pictures.length + ')'));
    $('g2-note').textContent = 'Browser rendering of the real HudFrames the runtime emits (same PlaybookEngine + HUD writer, private session). Not a capture from G2 hardware.';
  }

  // ------------------------------------------------------------ wearable handoff
  $('open-g2').addEventListener('click', function () {
    var g = st.guide, out = $('open-result'), btn = $('open-g2'); if (!g) return;
    btn.disabled = true; out.textContent = 'Opening on the runtime…';
    var sid;
    postJson('/session/connect').then(function (s) {
      sid = s.id;
      return g.open === 'product' ? openProduct(g, sid) : postJson('/session/goal', { session_id: sid, mode: g.goal_mode, via: 'phone_text', text: g.title }).then(function (res) {
        if (res.status !== 'supported' || res.card_id !== g.card_id) throw new Error('the runtime answered ' + res.status + (res.card_id ? ' (' + res.card_id + ')' : ''));
      });
    }).then(function () {
      out.textContent = '“' + g.title + '” is now the active task on the runtime. Connected glasses show it now.';
      $('runtime').hidden = false; pollRuntime();
    }).catch(function (e) { out.textContent = 'Not opened: ' + e.message; })
      .finally(function () { btn.disabled = false; });
  });
  /* A product manual opens the way the companion does it: look up its official link, pick the product, answer its configuration. */
  function settled(sid, n) {
    return getJson('/discovery/state?session_id=' + encodeURIComponent(sid)).then(function (d) {
      return d.phase === 'searching' && n > 0 ? new Promise(function (r) { setTimeout(r, 400); }).then(function () { return settled(sid, n - 1); }) : d;
    });
  }
  function openProduct(g, sid) {
    var urls = g.sources.map(function (s) { return s.url; }).filter(Boolean);
    function tryUrl(i) {
      if (i >= urls.length) return Promise.reject(new Error('product lookup did not find this manual; continue in the companion'));
      return postJson('/session/goal', { session_id: sid, mode: g.goal_mode, via: 'phone_text', text: urls[i] }).then(function () { return settled(sid, 25); }).then(function (d) {
        var art = /choosing|confirming/.test(d.phase) && S.pickId(g.card_id, (d.candidates || []).map(function (c) { return c.record.article; }));
        return art ? postJson('/discovery/select', { session_id: sid, article: art }) : tryUrl(i + 1);
      });
    }
    return tryUrl(0).then(function (d) {
      if (d.phase === 'configuring' && d.config_question) {
        var opt = S.pickId(g.card_id, d.config_question.options.map(function (o) { return o.id; }));
        if (!opt) throw new Error('choose the configuration in the companion');
        return postJson('/discovery/config', { session_id: sid, option: opt });
      }
      return d;
    }).then(function (d) { if (d.card_id !== g.card_id) throw new Error(d.card_id ? 'the runtime reopened ' + d.card_id + ' (the configuration it remembers for this product); change it in the companion' : 'no guide started; continue in the companion'); });
  }
  function pollRuntime() {
    clearTimeout(st.poll);
    getJson('/state').then(function (s) {
      var box = clear($('runtime-frame'));
      box.appendChild(mirror(s.hud, 'Live from the core · seq ' + (s.hud ? s.hud.seq : '–') + ' · ' + (s.card_id || '')));
    }).catch(function () { clear($('runtime-frame')).appendChild(h('p', { class: 'err', text: 'Core unreachable.' })); })
      .finally(function () { st.poll = setTimeout(pollRuntime, 1000); });
  }

  // ------------------------------------------------------------ boot
  loadGuides().then(function () { if (Q.get('guide')) select(Q.get('guide')); if (Q.get('url')) { $('src-url').value = Q.get('url'); $('src-form').requestSubmit(); } });
  setInterval(function () { getJson('/studio/guides').then(function (d) { st.live = d.live; renderLive(); setChip(true); }).catch(function () { setChip(false); }); }, 3000);
})();
