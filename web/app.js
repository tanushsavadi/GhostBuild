/* GhostBuild phone companion. Static, no build step, no external requests.
 * Polls GET /state at 1 Hz (relative to the page origin, or ?core=http://host:8787), GET /card on card change,
 * POST /session/goal. Every piece of server text goes through textContent (never innerHTML).
 * Honesty rules: unreachable/stale/non-live data is always labelled and never shown as live. */
(function () {
  'use strict';
  var qs = new URLSearchParams(location.search);
  var FIXTURE = qs.get('fixture');                       // null | "1" | "state_visual" ...
  var CORE = (qs.get('core') || '').replace(/\/+$/, '');
  var POLL_MS = 1000, TIMEOUT_MS = 2500, STALE_MS = 3000;
  var FIXTURES = ['state_fault', 'state_visual', 'state_healthy', 'state_verified', 'state_simulated', 'state_pi_down', 'state_menu'];
  var dev = { force: null };                             // fixture-mode switches: 'unreachable' | 'stale'
  var S = { state: null, okAt: 0, err: null, skew: 0, card: null, cardErr: null, cardFor: null, manifests: {}, goalBusy: false };

  var $ = function (id) { return document.getElementById(id); };
  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (k === 'class') el.className = attrs[k]; else if (k === 'text') el.textContent = attrs[k];
      else if (attrs[k] !== null && attrs[k] !== undefined && attrs[k] !== false) el.setAttribute(k, attrs[k]);
    }
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i]; if (c === null || c === undefined || c === false) continue;
      el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return el;
  }
  function memo(el, key, fn) { if (el._k === key) return; el._k = key; fn(el); }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }

  // ------------------------------------------------------------------ URLs
  function url(path) {
    if (FIXTURE) {
      if (path.indexOf('/guides/') === 0) return '../knowledge' + path;
      if (path === '/card') return 'fixtures/card_camera_lens.json';
      if (path === '/state') return 'fixtures/' + (FIXTURE === '1' ? 'state_fault' : FIXTURE) + '.json';
    }
    return CORE + path;
  }
  function getJson(path) {
    var ctl = new AbortController(), t = setTimeout(function () { ctl.abort(); }, TIMEOUT_MS);
    return fetch(url(path), { signal: ctl.signal, cache: 'no-store' }).then(function (r) {
      clearTimeout(t);
      if (!r.ok) throw new Error('HTTP ' + r.status + ' on ' + path);
      var d = r.headers.get('Date');
      return r.json().then(function (j) { return { json: j, date: d ? Date.parse(d) : NaN }; });
    }, function (e) { clearTimeout(t); throw new Error(e.name === 'AbortError' ? 'timeout on ' + path : (e.message || 'network error')); });
  }

  // ------------------------------------------------------------------ polling
  function poll() {
    var p = (FIXTURE && dev.force === 'unreachable') ? Promise.reject(new Error('simulated outage (dev bar)')) : getJson('/state');
    p.then(function (r) {
      if (!r.json || typeof r.json !== 'object' || !r.json.session) throw new Error('GET /state returned an unexpected body');
      S.state = r.json; S.err = null;
      if (!(FIXTURE && dev.force === 'stale')) S.okAt = Date.now();
      if (!isNaN(r.date) && !FIXTURE) S.skew = r.date - Date.now();
      loadCardIfNeeded();
    }).catch(function (e) { S.err = e.message; }).then(function () { tick(true); setTimeout(poll, POLL_MS); });
  }
  function loadCardIfNeeded() {
    var id = S.state && S.state.card_id;
    if (!id || (S.cardFor === id && S.card) || S.cardLoading) return;
    if (S.cardErrAt && Date.now() - S.cardErrAt < 5000) return;
    S.cardLoading = true;
    getJson('/card').then(function (r) { S.card = r.json; S.cardFor = id; S.cardErr = null; S.manifests = {}; S.cardErrAt = 0; })
      .catch(function (e) { S.cardErr = e.message; S.cardErrAt = Date.now(); })
      .then(function () { S.cardLoading = false; renderGuides(); });
  }
  function loadManifest(gid) {
    if (S.manifests[gid] !== undefined) return;
    S.manifests[gid] = null;
    getJson('/guides/' + gid + '/manifest.json').then(function (r) {
      var m = {}; (r.json.views || []).forEach(function (v) { m[v.view] = v; }); S.manifests[gid] = m; renderGuides(true);
    }).catch(function () { S.manifests[gid] = false; renderGuides(true); });
  }

  // ------------------------------------------------------------------ derived freshness
  function fresh() {
    var age = Date.now() - S.okAt;
    if (!S.state) return { kind: S.err ? 'unreachable' : 'connecting', age: age, ok: false };
    if (S.err) return { kind: age > STALE_MS ? 'unreachable' : 'retry', age: age, ok: age <= STALE_MS };
    if (age > STALE_MS) return { kind: 'stale', age: age, ok: false };
    return { kind: 'fresh', age: age, ok: true };
  }
  function coreNow() {
    if (FIXTURE && S.state) {
      var m = 0; (S.state.events || []).forEach(function (e) { if (e.at > m) m = e.at; });
      return (m || Date.now()) + 3000;
    }
    return Date.now() + S.skew;
  }
  function sec(ms) { return (ms / 1000).toFixed(ms < 10000 ? 1 : 0) + ' s'; }
  function rel(ms) {
    if (ms < 1200) return 'just now'; var s = Math.round(ms / 1000);
    if (s < 90) return s + ' s ago'; var m = Math.round(s / 60); if (m < 90) return m + ' min ago';
    return Math.round(m / 60) + ' h ago';
  }

  // ------------------------------------------------------------------ labels / badges
  function lblClass(l) {
    if (l === 'MEASURED LIVE') return 'l-MEASURED'; if (l === 'INFERRED') return 'l-INFERRED'; if (l === 'COMMANDED') return 'l-COMMANDED';
    if (l === 'DETERMINISTIC') return 'l-DETERMINISTIC'; if (l === 'HUMAN CONFIRMED') return 'l-HUMAN'; if (l === 'MANUFACTURER DOC') return 'l-DOC';
    if (l === 'REPLAY') return 'l-REPLAY'; if (l === 'SIMULATED') return 'l-SIMULATED'; if (l.indexOf('AI-EXTRACTED') === 0) return 'l-AI';
    return 'l-AUTH';
  }
  function lbl(l) { return h('span', { class: 'lbl ' + lblClass(String(l)), text: String(l) }); }
  function safeHref(u) { return /^https?:\/\//i.test(u || '') ? u : null; }

  // ------------------------------------------------------------------ banners, chip, source badge
  function renderStatus() {
    var f = fresh(), st = S.state, b = [];
    document.body.classList.toggle('stale', !f.ok);
    var chip = $('link-chip'), cls, txt;
    if (f.kind === 'fresh') { cls = 'chip-ok'; txt = 'updated ' + sec(f.age) + ' ago'; }
    else if (f.kind === 'retry') { cls = 'chip-warn'; txt = 'retrying, ' + sec(f.age) + ' old'; }
    else if (f.kind === 'connecting') { cls = 'chip-wait'; txt = 'connecting...'; }
    else { cls = 'chip-bad'; txt = (f.kind === 'unreachable' ? 'NO LINK' : 'STALE') + (S.okAt ? ' \u00b7 ' + sec(f.age) + ' old' : ' \u00b7 no data'); }
    memo(chip, cls + txt, function () { chip.className = 'chip ' + cls; chip.textContent = txt; });

    if (FIXTURE) b.push(['amber', 'FIXTURE MODE: canned data, not a live system', 'dev.html is showing files from web/fixtures. Nothing here came from the Pi or the glasses.']);
    if (f.kind === 'unreachable' || f.kind === 'stale') {
      b.push(['red', 'CORE ' + (f.kind === 'stale' ? 'DATA STALE' : 'UNREACHABLE') + '. NOTHING BELOW IS LIVE',
        (S.okAt ? 'Last good /state ' + sec(f.age) + ' ago. ' : 'No /state received yet. ') + (S.err ? 'Error: ' + S.err + '. ' : '') + 'Check the laptop running core and the Wi-Fi.']);
    } else if (st) {
      var hl = st.health || {}, hud = st.hud, src = (hud && hud.source) || st.source;
      if (hl.pi_link === 'down') b.push(['red', 'PI LINK DOWN', 'No observation from the Pi' + (hl.pi_age_ms != null ? ' for ' + sec(hl.pi_age_ms) : '') + '. Facts below are the last known ones, not live.']);
      else if (hl.pi_link === 'stale') b.push(['amber', 'PI DATA STALE', 'Last observation ' + (hl.pi_age_ms != null ? sec(hl.pi_age_ms) : '?') + ' old. Do not trust a recovery until frames resume.']);
      if (hl.camera === 'unavailable' || hl.camera === 'frozen') b.push(['amber', 'CAMERA ' + hl.camera.toUpperCase(), 'No measured frames. This is an error, never a success.']);
      if (src === 'simulated') b.push(['red', 'SIMULATED DATA. NOT LIVE', 'Observations come from a simulator. Never present this as a live demo.']);
      else if (src === 'replay') b.push(['red', 'REPLAY. NOT LIVE', 'Observations are replayed from a recording.']);
      if (hud && hud.stale) b.push(['amber', 'G2 IS SHOWING ERROR', 'The HUD frame is backed by data older than the staleness limit.']);
    }
    var box = $('banners');
    memo(box, JSON.stringify(b), function () {
      clear(box);
      b.forEach(function (x) { box.appendChild(h('div', { class: 'banner banner-' + x[0], role: x[0] === 'red' ? 'alert' : null }, x[1], h('small', { text: x[2] }))); });
    });
    var badge = $('src-badge'), s = null;
    if (st && f.ok) s = (st.health && st.health.pi_link && st.health.pi_link !== 'up') ? '__notlive' : (st.hud && st.hud.source) || st.source;
    var bt = !st || !f.ok ? ['src-none', 'NO LIVE DATA'] : s === '__notlive' ? ['src-none', 'PI NOT LIVE'] : s === 'pi_live' ? ['src-live', 'LIVE'] : s === 'simulated' ? ['src-simulated', 'SIMULATED'] : s === 'replay' ? ['src-replay', 'REPLAY'] : ['src-none', 'NO SOURCE'];
    if (FIXTURE && bt[0] !== 'src-none') bt = ['src-replay', 'FIXTURE \u00b7 ' + bt[1]];
    memo(badge, bt.join(), function () { badge.className = 'src ' + bt[0]; badge.textContent = bt[1]; });
  }

  // ------------------------------------------------------------------ G2 mirror
  function renderMirror() {
    var st = S.state, f = fresh(), inner = $('g2-inner'), veil = $('g2-veil'), meta = $('g2-meta');
    var hud = st && st.hud;
    var vt = null;
    if (!st) vt = ['NO DATA YET', 'waiting for GET /state'];
    else if (!f.ok) vt = ['NOT LIVE', 'core ' + (f.kind === 'stale' ? 'stale' : 'unreachable') + ', last frame ' + sec(f.age) + ' old'];
    else if (hud && hud.stale) vt = ['STALE', 'the glasses show ERROR, not this frame'];
    memo(veil, JSON.stringify(vt), function () {
      veil.hidden = !vt; clear(veil); if (vt) veil.appendChild(h('div', { text: vt[0] }, h('small', { text: vt[1] })));
    });
    $('g2').classList.toggle('dead', !!vt);
    var key = JSON.stringify(hud || null);
    memo(inner, key, function () {
      clear(inner); inner.className = 'g2-inner';
      if (!hud || hud.mode === 'quiet') { inner.classList.add('g2-empty'); inner.appendChild(h('div', { text: hud ? 'QUIET: glasses blank (healthy)' : 'no HUD frame yet' })); return; }
      var cue = hud.cue || { line1: '', line2: '' };
      if (hud.mode === 'menu' && hud.menu) {
        inner.classList.add('g2-menu');
        inner.appendChild(h('div', { class: 'g2-l1', text: hud.menu.prompt }));
        hud.menu.options.forEach(function (o, i) { inner.appendChild(h('div', { class: 'opt', text: (i === hud.menu.selected ? '> ' : '  ') + o })); });
        return;
      }
      if (hud.mode === 'visual' && hud.image) {
        inner.classList.add('g2-vis');
        var box = h('div', { class: 'g2-img' });
        var im = h('img', { alt: 'guide image ' + hud.image.view, src: url(hud.image.url) + '?v=' + String(hud.image.sha256 || '').slice(0, 10) });
        im.onerror = function () { box.remove(); inner.insertBefore(h('div', { class: 'g2-l2', text: '[image failed: text fallback]' }), inner.firstChild); };
        box.appendChild(im); inner.appendChild(box);
      }
      inner.appendChild(h('div', { class: 'g2-l1', text: cue.line1 }));
      if (cue.line2) inner.appendChild(h('div', { class: 'g2-l2', text: cue.line2 }));
    });
    memo(meta, key + f.ok, function () {
      clear(meta); if (!hud) return;
      meta.appendChild(h('span', { text: 'seq ' + hud.seq + ' · mode ' + hud.mode + (hud.cue_id ? ' · ' + hud.cue_id : '') + (hud.ttl_ms ? ' · clears in ' + sec(hud.ttl_ms) : '') }));
      if (hud.image) { meta.appendChild(h('br')); meta.appendChild(document.createTextNode('image ' + (hud.image.index + 1) + '/' + hud.image.count + ' ' + hud.image.view + ' · ' + hud.image.w + 'x' + hud.image.h + ' · ')); meta.appendChild(lbl(hud.image.provenance)); }
    });
  }

  // ------------------------------------------------------------------ task + health
  function pill(text, kind) { return h('span', { class: 'pill pill-' + kind, text: text }); }
  function renderTask() {
    var dl = $('task'), st = S.state;
    memo(dl, JSON.stringify(st), function () {
      clear(dl);
      if (!st) { dl.appendChild(h('dd', { class: 'empty', text: 'no state yet' })); return; }
      var hl = st.health || {}, se = st.session || {};
      var row = function (k, v) { dl.appendChild(h('dt', { text: k })); dl.appendChild(h('dd', null, v === null || v === undefined || v === '' ? h('span', { class: 'empty', text: 'none' }) : v)); };
      var ek = { HEALTHY: 'ok', FAULT: 'bad', NO_LINK: 'bad', EXHAUSTED: 'warn', AWAIT_FUNC: 'warn' }[st.engine] || 'warn';
      row('Session', se.id + ' · ' + se.phase + (se.goal ? ' · ' + se.goal.toUpperCase() : ''));
      row('Engine', pill(st.engine, ek));
      row('Task', st.card_id ? st.card_id + (st.test ? ' / ' + st.test : '') : null);
      row('Step', st.step_id ? st.step_id + (st.check != null ? ' (check ' + (st.check + 1) + ')' : '') : null);
      row('Help view', st.help_view);
      row('Pi link', h('span', null, pill((hl.pi_link || '?').toUpperCase(), hl.pi_link === 'up' ? 'ok' : hl.pi_link === 'stale' ? 'warn' : 'bad'),
        hl.pi_age_ms != null ? '  ' + hl.pi_age_ms + ' ms old, seq ' + hl.pi_last_seq : ''));
      row('Camera', pill((hl.camera || 'unknown').toUpperCase(), hl.camera === 'ok' ? 'ok' : hl.camera === 'unknown' ? 'warn' : 'bad'));
      row('Source', (st.source || '-') + (hl.source && hl.source !== st.source ? ' (health: ' + hl.source + ')' : ''));
      row('G2 clients', String(hl.g2_clients != null ? hl.g2_clients : '?'));
      row('Core uptime', hl.uptime_s != null ? Math.round(hl.uptime_s) + ' s' : null);
    });
  }

  // ------------------------------------------------------------------ timeline
  function renderTimeline() {
    var ol = $('timeline'), st = S.state, f = fresh();
    var now = coreNow(), key = JSON.stringify(st && st.events) + Math.floor(now / 1000) + f.ok;
    memo(ol, key, function () {
      clear(ol);
      var ev = (st && st.events) || [];
      if (!ev.length) { ol.appendChild(h('li', { class: 'empty', text: st ? 'no evidence yet (healthy and quiet)' : 'no data' })); return; }
      ev.slice().sort(function (a, b) { return b.at - a.at; }).slice(0, 80).forEach(function (e, i) {
        var d = new Date(e.at), clock = isNaN(d) ? '' : d.toLocaleTimeString([], { hour12: false });
        var ev2 = e.evidence && Object.keys(e.evidence).length ? Object.keys(e.evidence).map(function (k) { return k + '=' + e.evidence[k]; }).join('  ') : '';
        ol.appendChild(h('li', { class: i === 0 ? 'first' : '' }, lbl(e.label), h('span', { class: 'when', text: rel(Math.max(0, now - e.at)) + ' · ' + clock }),
          h('span', { class: 'txt', text: e.text }), ev2 ? h('span', { class: 'ev', text: ev2 }) : null));
      });
    });
  }

  // ------------------------------------------------------------------ guides + sources
  function activeGuide() {
    var c = S.card, st = S.state; if (!c) return null;
    var test = (c.tests || []).filter(function (t) { return st && t.id === st.test; })[0] || (c.tests || [])[0];
    var chk = test && st && st.check != null ? test.checks[st.check] : null;
    var active = !!chk, ref = chk || (test && test.checks.filter(function (k) { return k.guide_id; })[0]);
    var g = ref && ref.guide_id ? (c.guides || []).filter(function (x) { return x.id === ref.guide_id; })[0] : (c.guides || [])[0];
    return { guide: g, check: ref, active: active };
  }
  function renderGuides(force) {
    var box = $('guide'), note = $('guide-note'), st = S.state;
    var a = activeGuide();
    var shown = st && st.hud && st.hud.image ? st.hud.image.view : null;
    var mf = a && a.guide ? S.manifests[a.guide.id] : undefined;
    var key = JSON.stringify([a && a.guide, a && a.active, shown, S.cardErr, mf]);
    if (a && a.guide && S.manifests[a.guide.id] === undefined) loadManifest(a.guide.id);
    memo(box, key, function () {
      clear(box); clear(note);
      if (S.cardErr) note.appendChild(h('span', { text: 'GET /card failed: ' + S.cardErr + '. Guide pictures need the card.' }));
      else if (!S.card) note.textContent = st ? 'loading card...' : 'waiting for core';
      else if (!a || !a.guide) note.textContent = 'The card has no guide for this check.';
      else note.textContent = a.active ? 'Active check ' + (st.check + 1) + ': ' + a.check.action.line1 + ' / ' + a.check.action.line2 + '. ' + a.check.why
        : 'No active fault: showing "' + a.guide.title + '" for reference only.';
      if (!a || !a.guide) return;
      a.guide.views.forEach(function (v) {
        var gid = a.guide.id, m = mf && mf[v.view];
        var img = h('img', { alt: v.title + ': ' + v.depicts, loading: 'lazy', src: url('/guides/' + gid + '/' + v.view + '.phone.png') });
        var cap = h('div', { class: 'gv-d' });
        img.onerror = function () {
          if (!img._tried) { img._tried = 1; img.className = 'g2only'; img.src = url('/guides/' + gid + '/' + v.view + '.png'); cap.textContent = 'High-res phone image not served; showing the 288x144 glasses image.'; return; }
          img.remove(); cap.textContent = 'IMAGE UNAVAILABLE. Glasses fall back to text: ' + v.fallback.line1 + ' / ' + v.fallback.line2;
        };
        box.appendChild(h('div', { class: 'gv' + (shown === v.view ? ' cur' : '') }, img,
          h('div', { class: 'gv-b' },
            h('div', { class: 'gv-t' }, v.title, lbl(v.provenance), m && m.placeholder ? h('span', { class: 'lbl l-PLACEHOLDER', text: 'PLACEHOLDER SCHEMATIC, NOT RIG PHOTO' }) : null,
              shown === v.view ? h('span', { class: 'lbl l-INFERRED', text: 'ON GLASSES NOW' }) : null),
            h('div', { class: 'gv-d', text: v.depicts }),
            v.fov_note ? h('div', { class: 'gv-d', text: 'Field of view: ' + v.fov_note }) : null,
            h('div', { class: 'gv-d', text: 'Glasses text fallback: ' + v.fallback.line1 + (v.fallback.line2 ? ' / ' + v.fallback.line2 : '') }),
            cap, mf === false ? h('div', { class: 'gv-d', text: 'placeholder status unknown (manifest not served)' }) : null)));
      });
    });
    renderSources(a);
  }
  function renderSources(a) {
    var ul = $('sources'), c = S.card;
    memo(ul, JSON.stringify([c && c.sources, a && a.check && a.check.cites]), function () {
      clear(ul);
      if (!c) { ul.appendChild(h('li', { class: 'empty', text: 'no card loaded' })); return; }
      var cited = {}; ((a && a.check && a.check.cites) || []).forEach(function (x) { cited[x.source] = x.loc + (x.quote ? ': "' + x.quote + '"' : ''); });
      (c.sources || []).forEach(function (s) {
        var href = safeHref(s.url);
        ul.appendChild(h('li', null, lbl(s.kind), ' ', href ? h('a', { href: href, target: '_blank', rel: 'noopener noreferrer', text: s.title }) : h('span', { text: s.title + (s.file ? ' (' + s.file + ')' : '') }),
          cited[s.id] ? h('div', { class: 'meta', text: 'cited for this check: ' + cited[s.id] }) : null));
      });
      if (!(c.sources || []).length) ul.appendChild(h('li', { class: 'empty', text: 'card lists no sources' }));
    });
  }

  // ------------------------------------------------------------------ goal box
  function renderGoalHint() {
    var f = fresh(), btn = $('goal-send'), hint = $('goal-hint');
    var ok = !!(S.state && f.ok && S.state.session && S.state.session.id) && !S.goalBusy;
    btn.disabled = !ok;
    var t = !S.state ? 'Waiting for core.' : !f.ok ? 'Core is not answering; the goal cannot be sent.' : 'Session ' + S.state.session.id + '. Choosing a goal never completes a repair.';
    memo(hint, t, function () { hint.textContent = t; });
  }
  function showResolution(r, note) {
    var box = $('goal-result'); clear(box);
    var kind = r.status === 'supported' ? 'supported' : r.status === 'ambiguous' ? 'ambiguous' : 'unsupported';
    var el = h('div', { class: 'res ' + kind },
      h('div', { class: 'st', text: r.status.toUpperCase() + ' · ' + String(r.mode).toUpperCase() + (r.task_title ? ' · ' + r.task_title : '') }),
      r.cue ? h('div', { class: 'cue' }, r.cue.line1, r.cue.line2 ? h('br') : null, r.cue.line2 || null) : null,
      h('div', { text: r.detail || '' }));
    if (note) el.appendChild(h('div', { class: 'meta', text: note }));
    if (r.alternatives && r.alternatives.length) {
      el.appendChild(h('div', { class: 'meta', text: 'Supported right now:' }));
      var chips = h('div', { class: 'chips' });
      r.alternatives.forEach(function (alt) { chips.appendChild(h('button', { type: 'button', text: alt, onclick: null })); });
      Array.prototype.forEach.call(chips.children, function (b) { b.addEventListener('click', function () { $('goal-text').value = b.textContent; }); });
      el.appendChild(chips);
    }
    box.appendChild(el);
  }
  function showGoalError(msg) { var box = $('goal-result'); clear(box); box.appendChild(h('div', { class: 'res err', role: 'alert' }, h('div', { class: 'st', text: 'NOT SENT / FAILED' }), h('div', { text: msg }))); }
  $('goal-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    if (!S.state || S.goalBusy) return;
    var mode = document.querySelector('input[name=mode]:checked').value, text = $('goal-text').value.trim();
    var body = { v: 2, session_id: S.state.session.id, mode: mode, via: 'phone_text', text: text ? text : null };
    S.goalBusy = true; renderGoalHint();
    var p;
    if (FIXTURE) {
      var ok = /camera|lens|view|pi\b|inspection|black|dark/i.test(text) || (mode === 'build' && /station|setup|set up/i.test(text));
      p = fetch('fixtures/goal_resolution_' + (ok ? 'supported' : 'unsupported') + '.json').then(function (r) { return r.json(); }).then(function (j) { j.mode = mode; showResolution(j, 'FIXTURE RESPONSE: no backend was contacted.'); });
    } else {
      p = fetch(CORE + '/session/goal', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(function (r) {
        return r.text().then(function (t) {
          if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + t.slice(0, 200));
          var j; try { j = JSON.parse(t); } catch (e) { throw new Error('core answered with non-JSON'); }
          if (!j || !j.status) throw new Error('core answered with an unexpected body');
          showResolution(j);
        });
      });
    }
    p.catch(function (e) { showGoalError(e.message); }).then(function () { S.goalBusy = false; renderGoalHint(); });
  });

  // ------------------------------------------------------------------ dev bar
  function devbar() {
    if (!FIXTURE) return;
    var bar = $('devbar'); bar.hidden = false;
    bar.appendChild(h('b', { text: 'fixture:' }));
    var cur = FIXTURE === '1' ? 'state_fault' : FIXTURE;
    FIXTURES.forEach(function (n) { bar.appendChild(h('a', { href: '?fixture=' + n, class: n === cur ? 'cur' : '', text: n.replace('state_', '') })); });
    var mk = function (val, label) {
      var cb = h('input', { type: 'checkbox' }); cb.addEventListener('change', function () { dev.force = cb.checked ? val : null; tick(true); });
      bar.appendChild(h('label', null, cb, label));
    };
    mk('unreachable', 'simulate core outage'); mk('stale', 'simulate stale (>3 s)');
  }

  function tick(poll) { renderStatus(); renderMirror(); renderTask(); renderTimeline(); renderGuides(); renderGoalHint(); }
  devbar(); tick(); poll(); setInterval(tick, 500);
})();
