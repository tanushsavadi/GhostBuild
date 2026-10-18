/* GhostBuild phone companion. Static, no build step, no external requests.
 * Polls GET /state at 1 Hz (relative to the page origin, or ?core=http://host:8787), GET /card on card change,
 * POST /session/goal, /ask, /research/request. Pure logic lives in logic.js (GBLogic, unit-tested). Every piece of server text goes through textContent (never innerHTML).
 * Honesty rules: unreachable/stale/non-live data is always labelled and never shown as live. */
(function () {
  'use strict';
  var qs = new URLSearchParams(location.search);
  var FIXTURE = qs.get('fixture');                       // null | "1" | "state_visual" ...
  var CORE = (qs.get('core') || '').replace(/\/+$/, '');
  var POLL_MS = 1000, TIMEOUT_MS = 2500, STALE_MS = 3000;
  var FIXTURES = ['state_fault', 'state_visual', 'state_healthy', 'state_verified', 'state_simulated', 'state_pi_down', 'state_menu',
    'state_playbook_manual', 'state_playbook_measured', 'state_playbook_completed', 'state_playbook_unsupported'];
  var L = window.GBLogic;
  var dev = { force: null, no404: false };               // fixture-mode switches: force 'unreachable' | 'stale'; no404 = /ask and /research answer 404
  var S = { live: null, state: null, okAt: 0, err: null, skew: 0, card: null, cardErr: null, cardFor: null, manifests: {}, guideFor: null, lastGuideView: null, goalBusy: false, askBusy: false, resBusy: false, catalog: [], guideView: null, actionBusy: false, connecting: false };

  var $ = function (id) { return document.getElementById(id); };
  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (k === 'class') el.className = attrs[k]; else if (k === 'text') el.textContent = attrs[k];
      else if (attrs[k] !== null && attrs[k] !== undefined && attrs[k] !== false) el.setAttribute(k, attrs[k]);
    }
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i]; if (c === null || c === undefined || c === false) continue;
      if (Array.isArray(c)) { c.forEach(function (x) { if (x) el.appendChild(typeof x === 'string' ? document.createTextNode(x) : x); }); continue; }
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
      if (path === '/card') return 'fixtures/card_' + ((S.state && S.state.card_id) || 'camera_lens') + '.json';
      if (path === '/state') return 'fixtures/' + (FIXTURE === '1' ? 'state_fault' : FIXTURE) + '.json';
    }
    return CORE + path;
  }
  function getJson(path) {
    var ctl = new AbortController(), t = setTimeout(function () { ctl.abort(); }, TIMEOUT_MS);
    return fetch(url(path), { signal: ctl.signal, cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status + ' on ' + path);
      var d = r.headers.get('Date');
      return r.json().then(function (j) { return { json: j, date: d ? Date.parse(d) : NaN }; });
    }, function (e) { clearTimeout(t); throw new Error(e.name === 'AbortError' ? 'timeout on ' + path : (e.message || 'network error')); });
  }

  // ------------------------------------------------------------------ polling
  var stateRequest = 0;
  function refreshState() {
    var request = ++stateRequest;
    var p = (FIXTURE && dev.force === 'unreachable') ? Promise.reject(new Error('simulated outage (dev bar)')) : getJson('/state');
    return p.then(function (r) {
      if (request !== stateRequest) return;
      if (!r.json || typeof r.json !== 'object' || !r.json.session) throw new Error('GET /state returned an unexpected body');
      S.state = r.json; S.err = null;
      if (!FIXTURE && r.json.session.id === "none" && !S.connecting) { S.connecting = true; postJson("/session/connect", {}).then(function () { S.connecting = false; }); }
      if (!(FIXTURE && dev.force === 'stale')) S.okAt = Date.now();
      if (!isNaN(r.date) && !FIXTURE) S.skew = r.date - Date.now();
      loadCardIfNeeded();
    }).catch(function (e) { if (request === stateRequest) S.err = e.message; }).then(function () { tick(true); });
  }
  function poll() { refreshState().then(function () { setTimeout(poll, POLL_MS); });
  }
  function loadCardIfNeeded() {
    var id = S.state && S.state.card_id;
    if (!id || (S.cardFor === id && S.card) || S.cardLoading) return;
    if (S.cardErrAt && Date.now() - S.cardErrAt < 5000) return;
    S.cardLoading = true;
    getJson('/card').then(function (r) { if (!S.state || S.state.card_id !== id || r.json.card_id !== id) return; S.card = r.json; S.cardFor = id; S.guideView = null; S.cardErr = null; S.manifests = {}; S.cardErrAt = 0; })
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
      // Pi problems are only banner-worthy when the active card depends on telemetry (fault tests or a measured step).
      // A manual playbook works with no Pi at all and never gets a Pi banner.
      if (L.showPiBanners(st, S.card)) {
        var pbk = L.isPlaybookCard(S.card) ? ' Measured steps cannot complete without Pi evidence; manual steps still work.' : '';
        if (hl.pi_link === 'down') b.push(['red', 'PI LINK DOWN', 'No observation from the Pi' + (hl.pi_age_ms != null ? ' for ' + sec(hl.pi_age_ms) : '') + '. Facts below are the last known ones, not live.' + pbk]);
        else if (hl.pi_link === 'stale') b.push(['amber', 'PI DATA STALE', 'Last observation ' + (hl.pi_age_ms != null ? sec(hl.pi_age_ms) : '?') + ' old. Do not trust a recovery until frames resume.' + pbk]);
        if (hl.camera === 'unavailable' || hl.camera === 'frozen') b.push(['amber', 'CAMERA ' + hl.camera.toUpperCase(), 'No measured frames. This is an error, never a success.']);
      }
      if (src === 'simulated') b.push(['red', 'SIMULATED DATA. NOT LIVE', 'Observations come from a simulator. Never present this as a live demo.']);
      else if (src === 'replay') b.push(['red', 'REPLAY. NOT LIVE', 'Observations are replayed from a recording.']);
      if (hud && hud.stale) b.push(['amber', 'G2 IS SHOWING ERROR', 'The HUD frame is backed by data older than the staleness limit.']);
    }
    var box = $('banners');
    memo(box, JSON.stringify(b), function () {
      clear(box);
      b.forEach(function (x) { box.appendChild(h('div', { class: 'banner banner-' + x[0], role: x[0] === 'red' ? 'alert' : null }, x[1], h('small', { text: x[2] }))); });
    });
    var badge = $('src-badge'), s = null, tele = L.usesTelemetry(st, S.card);
    if (st && f.ok) s = (tele && st.health && st.health.pi_link && st.health.pi_link !== 'up') ? '__notlive' : (st.hud && st.hud.source) || st.source;
    // No telemetry in play: nothing is "live" from the Pi, so a pi_live label on a manual step is shown as MANUAL STEPS, not LIVE.
    if (s === 'pi_live' && !tele) s = '__manual';
    if (s === 'manual') s = '__manual';
    var bt = !st || !f.ok ? ['src-none', 'NO LIVE DATA'] : s === '__notlive' ? ['src-none', 'PI NOT LIVE'] : s === '__manual' ? ['src-none', 'MANUAL STEPS'] : s === 'pi_live' ? ['src-live', 'LIVE'] : s === 'simulated' ? ['src-simulated', 'SIMULATED'] : s === 'replay' ? ['src-replay', 'REPLAY'] : ['src-none', 'NO SOURCE'];
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
      if (!hud || hud.mode === 'quiet') { inner.classList.add('g2-empty'); inner.appendChild(h('div', { text: hud ? 'QUIET · DISPLAY RESTING' : 'WAITING FOR YOUR GLASSES' })); return; }
      var cue = hud.cue || { line1: '', line2: '' };
      if (hud.mode === 'menu' && hud.menu) {
        inner.classList.add('g2-menu');
        inner.appendChild(h('div', { class: 'g2-l1', text: hud.menu.prompt }));
        hud.menu.options.forEach(function (o, i) { inner.appendChild(h('div', { class: 'opt', text: (i === hud.menu.selected ? '> ' : '  ') + o })); });
        return;
      }
      if (hud.answer) {
        inner.appendChild(h('div', {class:'g2-answer',text:hud.answer.text}));
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
    // The dim tag line of the glasses (step counter, picture index, non-live source), mirrored.
    var tagEl = $('g2-tag');
    var tp = [];
    if (hud && hud.mode !== 'quiet') {
      var ctr = L.counterText(hud); if (ctr) tp.push(ctr);
      if (hud.answer) tp.push('ANSWER '+(hud.answer.index+1)+'/'+hud.answer.count+' · PRESS: BACK');
      if (hud.image && hud.image.count > 1) tp.push((ctr ? 'PIC ' : '') + (hud.image.index + 1) + '/' + hud.image.count);
      if (hud.source && hud.source !== 'pi_live' && hud.source !== 'manual') tp.push(String(hud.source).toUpperCase());
    }
    memo(tagEl, tp.join('  '), function () { tagEl.hidden = !tp.length; tagEl.textContent = tp.join('  '); });
    var note = document.querySelector('.area-mirror .gesture-note');
    if (note) {
      var gestureNote = 'Press for a picture · Swipe up goes back · Double press exits G2';
      if (hud && hud.answer) gestureNote = 'Swipe to read the answer · Press to return to your step · Double press exits G2';
      else if (hud && hud.menu) gestureNote = 'Swipe to choose an answer · Press to select · Double press exits G2';
      else if (hud && hud.step && hud.step.check === 'manual') gestureNote = 'Press for pictures · Swipe down confirms this step · Swipe up goes back';
      note.textContent = gestureNote;
    }
    memo(meta, key + f.ok, function () {
      clear(meta); if (!hud) return;
      meta.appendChild(h('span', { text: 'seq ' + hud.seq + ' · mode ' + hud.mode + (hud.cue_id ? ' · ' + hud.cue_id : '') + (hud.ttl_ms ? ' · clears in ' + sec(hud.ttl_ms) : '') }));
      if (hud.step) { meta.appendChild(h('br')); meta.appendChild(document.createTextNode('step ' + (hud.step.index + 1) + '/' + hud.step.count + ' ' + hud.step.step_id + ' · ' + (hud.step.check === 'measured' ? 'measured: evidence completes it' : 'manual: you confirm it') + (hud.step.confirmed ? ' · confirmed' : ''))); }
      if (hud.image) { meta.appendChild(h('br')); meta.appendChild(document.createTextNode('image ' + (hud.image.index + 1) + '/' + hud.image.count + ' ' + hud.image.view + ' · ' + hud.image.w + 'x' + hud.image.h + ' · ')); meta.appendChild(lbl(hud.image.provenance)); }
    });
  }

  // ------------------------------------------------------------------ task + health
  function pill(text, kind) { return h('span', { class: 'pill pill-' + kind, text: text }); }
  function renderTask() {
    var dl = $('task'), st = S.state;
    memo(dl, JSON.stringify([st, S.card && S.card.card_id]), function () {
      clear(dl);
      if (!st) { dl.appendChild(h('dd', { class: 'empty', text: 'no state yet' })); return; }
      var hl = st.health || {}, se = st.session || {};
      var row = function (k, v) { dl.appendChild(h('dt', { text: k })); dl.appendChild(h('dd', null, v === null || v === undefined || v === '' ? h('span', { class: 'empty', text: 'none' }) : v)); };
      var ek = { HEALTHY: 'ok', FAULT: 'bad', NO_LINK: 'bad', EXHAUSTED: 'warn', AWAIT_FUNC: 'warn', PLAYBOOK: 'ok' }[st.engine] || 'warn';
      if (st.engine === 'NO_LINK' && !L.usesTelemetry(st, S.card)) ek = 'warn';
      row('Session', se.id + ' · ' + se.phase + (se.goal ? ' · ' + se.goal.toUpperCase() : ''));
      row('Engine', pill(st.engine === 'NO_LINK' && !L.usesTelemetry(st, S.card) ? 'NO TASK RUNNING' : st.engine, ek));
      row('Task', st.card_id ? (S.card && S.card.card_id === st.card_id ? S.card.title + ' (' + st.card_id + ')' : st.card_id) + (st.test ? ' / ' + st.test : '') : null);
      var pb = st.playbook;
      row('Step', pb ? (pb.step_index + 1) + ' of ' + pb.step_count + ' · ' + pb.step_id : st.step_id ? st.step_id + (st.check != null ? ' (check ' + (st.check + 1) + ')' : '') : null);
      if (pb) row('Done so far', pb.confirmed.length + ' confirmed by you · ' + pb.verified.length + ' measured');
      if (!pb) row('Help view', st.help_view);
      // Pi rows only when the link is not down or the card depends on telemetry; a manual playbook shows no Pi at all.
      if (L.showPiHealth(st, S.card)) {
        row('Pi link', h('span', null, pill((hl.pi_link || '?').toUpperCase(), hl.pi_link === 'up' ? 'ok' : hl.pi_link === 'stale' ? 'warn' : 'bad'),
          hl.pi_age_ms != null ? '  ' + hl.pi_age_ms + ' ms old, seq ' + hl.pi_last_seq : ''));
        row('Camera', pill((hl.camera || 'unknown').toUpperCase(), hl.camera === 'ok' ? 'ok' : hl.camera === 'unknown' ? 'warn' : 'bad'));
      }
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
    if (L.isPlaybookCard(c) && st && st.playbook) {
      var i = L.currentStepIndex(st, c), step = c.steps[i];
      var g = step && step.guide_id ? (c.guides || []).filter(function (x) { return x.id === step.guide_id; })[0] : null;
      return { guide: g || null, check: null, active: true, step: step, stepNo: i + 1 };
    }
    var test = (c.tests || []).filter(function (t) { return st && t.id === st.test; })[0] || (c.tests || [])[0];
    var chk = test && st && st.check != null ? test.checks[st.check] : null;
    var active = !!chk, ref = chk || (test && test.checks.filter(function (k) { return k.guide_id; })[0]);
    var g2 = ref && ref.guide_id ? (c.guides || []).filter(function (x) { return x.id === ref.guide_id; })[0] : (c.guides || [])[0];
    return { guide: g2, check: ref, active: active };
  }
  function renderGuides(force) {
    var box = $('guide'), note = $('guide-note'), st = S.state;
    var a = activeGuide();
    var owner = a && a.guide ? a.guide.id + '/' + (a.step && a.step.id || '') : null;
    if (S.guideFor !== owner) { S.guideFor = owner; S.guideView = null; S.lastGuideView = null; }
    var shown = st && st.hud && st.hud.image && a && a.guide && st.hud.image.guide_id === a.guide.id ? st.hud.image.view : null;
    if (shown) S.lastGuideView = shown;
    var selectedView = S.guideView || S.lastGuideView || (a && a.guide && a.guide.views[0].view);
    var mf = a && a.guide ? S.manifests[a.guide.id] : undefined;
    var key = JSON.stringify([S.card && S.card.card_id, a && a.step, a && a.guide, a && a.active, a && a.stepNo, selectedView, S.cardErr, mf]);
    if (a && a.guide && S.manifests[a.guide.id] === undefined) loadManifest(a.guide.id);
    memo(box, key, function () {
      clear(box); clear(note);
      if (S.cardErr) note.appendChild(h('span', { text: 'GET /card failed: ' + S.cardErr + '. Guide pictures need the card.' }));
      else if (!S.card) note.textContent = st ? 'loading card...' : 'waiting for core';
      else if (a && a.step) note.textContent = 'Step ' + a.stepNo + ': ' + a.step.title + (a.guide ? '.' : '. This step has no guide pictures.');
      else if (!a || !a.guide) note.textContent = 'The card has no guide for this check.';
      else note.textContent = a.active ? 'Active check ' + (st.check + 1) + ': ' + a.check.action.line1 + ' / ' + a.check.action.line2 + '. ' + a.check.why
        : 'No active fault: showing "' + a.guide.title + '" for reference only.';
      if (!a || !a.guide) return;
      var selected = selectedView;
      if (!a.guide.views.some(function (v) { return v.view === selected; })) selected = a.guide.views[0].view;
      var tabs = h('div', { class: 'guide-tabs', role: 'tablist', 'aria-label': 'Guide pictures' });
      a.guide.views.forEach(function (v) {
        var tab = h('button', { type: 'button', role: 'tab', 'aria-selected': v.view === selected ? 'true' : 'false', text: v.title });
        tab.addEventListener('click', function () { S.guideView = v.view; renderGuides(); }); tabs.appendChild(tab);
      });
      box.appendChild(tabs);
      a.guide.views.filter(function (v) { return v.view === selected; }).forEach(function (v) {
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
              h('span', { class: 'lbl l-INFERRED on-glasses', text: 'ON GLASSES NOW', hidden: shown !== v.view })),
            h('div', { class: 'gv-d', text: v.depicts }),
            v.fov_note ? h('div', { class: 'gv-d', text: 'Field of view: ' + v.fov_note }) : null,
            h('div', { class: 'gv-d', text: 'Glasses text fallback: ' + v.fallback.line1 + (v.fallback.line2 ? ' / ' + v.fallback.line2 : '') }),
            cap, mf === false ? h('div', { class: 'gv-d', text: 'placeholder status unknown (manifest not served)' }) : null)));
      });
    });
    Array.prototype.forEach.call(box.querySelectorAll('.on-glasses'), function (badge) { badge.hidden = !shown || shown !== selectedView; });
    renderSources(a);
  }
  // Sources: kind badge + link, and every cite of the card (location, quote, deep link). Video cites show their timestamp.
  function citeRow(ct, cur) {
    var href = safeHref(ct.url);
    var locEl = L.isTimestampLoc(ct.loc) ? h('span', { class: 'ts', text: ct.loc }) : h('span', { text: ct.loc });
    return h('li', { class: 'cite' + (cur ? ' here' : '') },
      h('span', { class: 'cite-w', text: ct.where + ' → ' }),
      href ? h('a', { href: href, target: '_blank', rel: 'noopener noreferrer' }, locEl) : locEl,
      href ? null : h('span', { class: 'meta', text: ' (no link)' }),
      ct.quote ? h('div', { class: 'cite-q', text: '“' + ct.quote + '”' }) : null,
      href ? h('div', { class: 'cite-u', text: ct.url }) : null);
  }
  function renderSources(a) {
    var ul = $('sources'), c = S.card, pv = $('sources-prov');
    var curId = a && a.step ? a.step.id : null;
    memo(pv, JSON.stringify([c && c.provenance]), function () {
      clear(pv);
      if (!c) return;
      pv.appendChild(document.createTextNode('Card provenance: ')); pv.appendChild(lbl(c.provenance));
      var n = L.provenanceNote(c.provenance); if (n) pv.appendChild(h('div', { text: n }));
    });
    memo(ul, JSON.stringify([c && c.sources, c && L.collectCites(c), curId]), function () {
      clear(ul);
      if (!c) { ul.appendChild(h('li', { class: 'empty', text: 'no card loaded' })); return; }
      var cites = L.collectCites(c);
      (c.sources || []).forEach(function (s) {
        var href = safeHref(s.url), mine = cites[s.id] || [];
        ul.appendChild(h('li', null, lbl(s.kind), ' ', href ? h('a', { href: href, target: '_blank', rel: 'noopener noreferrer', text: s.title }) : h('span', { text: s.title + (s.file ? ' (' + s.file + ')' : '') }),
          mine.length ? h('ul', { class: 'cites' }, mine.map(function (ct) { return citeRow(ct, curId && ct.stepId === curId); })) : h('div', { class: 'meta', text: 'not cited by any step or check' })));
      });
      if (!(c.sources || []).length) ul.appendChild(h('li', { class: 'empty', text: 'card lists no sources' }));
    });
  }

  // ------------------------------------------------------------------ playbook panel
  function cueText(q) { return q ? q.line1 + (q.line2 ? ' / ' + q.line2 : '') : ''; }
  function renderPlaybook() {
    var sec_ = $('sec-playbook'), c = S.card, st = S.state, pb = st && st.playbook;
    var show = !!(pb && st);
    var key = JSON.stringify([show, S.live && S.live.unreviewed_cards, pb, c && c.card_id, c && c.steps, c && c.sources, S.cardErr, fresh().ok]);
    memo(sec_, key, function () {
      sec_.hidden = !show; if (!show) return;
      var head = $('pb-head'), ol = $('pb-steps'), cur = $('pb-current'), cnt = $('pb-count');
      clear(head); clear(ol); clear(cur);
      cnt.textContent = 'step ' + (pb.step_index + 1) + ' of ' + pb.step_count;
      if (S.cardErr || !c || !L.isPlaybookCard(c) || c.card_id !== pb.card_id) {
        head.appendChild(h('div', { class: 'meta', text: S.cardErr ? 'GET /card failed: ' + S.cardErr + '. The step list needs the card; only the counts below come from /state.' : 'loading the card for ' + pb.card_id + '...' }));
        ol.appendChild(h('li', { class: 'pb-step cur' }, h('span', { class: 'pb-n', text: String(pb.step_index + 1) }), h('div', { class: 'pb-b' }, h('div', { class: 'pb-t', text: pb.step_id }))));
        return;
      }
      var idx = L.currentStepIndex(st, c), list = c.steps;
      head.appendChild(h('div', { class: 'pb-title', text: c.title }));
      if (S.live && (S.live.unreviewed_cards || []).indexOf(c.card_id) >= 0) head.appendChild(h('div', { class: 'unreviewed' }, h('b', { text: 'AI-RESEARCHED · NOT HUMAN-REVIEWED' }), h('div', { class: 'meta', text: S.live.note + ' The sources are listed with each step.' })));
      head.appendChild(h('div', { class: 'meta' }, 'Provenance: ', lbl(c.provenance)));
      var nConf = pb.confirmed.length, nVer = pb.verified.length;
      if (nConf + nVer >= list.length && list.length) head.appendChild(h('div', { class: 'res supported compact' },
        h('div', { class: 'st', text: 'ALL STEPS MARKED DONE' }),
        h('div', { text: nConf + ' confirmed by you (HUMAN CONFIRMED), ' + nVer + ' by measured evidence. A step you confirmed is your word, not a check by GhostBuild.' })));
      var notLive = st.hud && st.hud.source && st.hud.source !== 'pi_live' && st.hud.source !== 'manual' ? String(st.hud.source).toUpperCase() : null;
      var branching = list.some(function (x) { return x.kind === 'question'; });
      if (branching && (pb.observations || []).length) head.appendChild(h('div', { class: 'meta' }, h('b', { text: 'What you reported: ' }), pb.observations.join(' · '), ' ', lbl('HUMAN CONFIRMED')));
      list.forEach(function (stp, i) {
        var stat = L.stepStatus(stp, pb), isCur = i === idx;
        if (branching && !isCur && stat.kind === 'pending') return;  // a branching guide lists the route taken, not every branch
        var badge = stat.kind === 'confirmed' ? h('span', { class: 'lbl l-HUMAN', text: 'HUMAN CONFIRMED' })
          : stat.kind === 'measured' ? h('span', { class: 'lbl l-MEASURED', text: 'MEASURED' + (notLive ? ' · ' + notLive : '') })
          : h('span', { class: 'lbl l-PENDING', text: 'pending' });
        ol.appendChild(h('li', { class: 'pb-step' + (isCur ? ' cur' : '') + (stat.kind !== 'pending' ? ' done' : ''), 'aria-current': isCur ? 'step' : null },
          h('span', { class: 'pb-n', text: String(i + 1) }),
          h('div', { class: 'pb-b' },
            h('div', { class: 'pb-t' }, stp.title, ' ', badge, isCur ? h('span', { class: 'lbl l-NOW', text: 'YOU ARE HERE' }) : null),
            stat.kind === 'pending' ? h('div', { class: 'pb-r', text: L.stepRule(stp) }) : null)));
      });
      var stp = list[idx]; if (!stp) return;
      var by = {}; (c.sources || []).forEach(function (x) { by[x.id] = x; });
      var primary = stp.instruction || stp.cue;
      cur.appendChild(h('h3', { text: 'Step ' + (idx + 1) + ': ' + (stp.instruction ? stp.instruction.line1 : stp.title) }));
      cur.appendChild(h('div', { class: 'cue' }, primary.line1, primary.line2 ? h('br') : null, primary.line2 || null));
      cur.appendChild(h('div', { class: 'meta', text: 'Completion: ' + L.stepRule(stp) + '.' }));
      // Questions and notes stay in the adjacent step conversation, preserving this workspace.
      cur.appendChild(h('p', { class: 'detail', text: stp.detail || 'The card has no longer explanation for this step.' }));
      if (stp.kind === 'question' && (stp.choices || []).length) {
        var qb = h('div', { class: 'choice-grid' });
        stp.choices.forEach(function (ch) {
          var b = h('button', { type: 'button', class: 'secondary', text: ch.label });
          b.disabled = !!FIXTURE;  // this panel re-renders only when the step changes: check connection at click time
          b.addEventListener('click', function () { if (fresh().ok && !S.actionBusy) sendAction('choose', ch.id); });
          qb.appendChild(b);
        });
        cur.appendChild(qb);
        cur.appendChild(h('div', { class: 'meta', text: 'Or just say it. Your answer chooses the next check; it is recorded as what you reported, not as a measurement.' }));
      }
      if (stp.risk === 'hazard') cur.appendChild(h('div', { class: 'warn' }, h('b', { text: 'SAFETY STEP ' }), 'GhostBuild asks you to confirm this one twice. Follow the warning below exactly.'));
      (stp.warnings || []).forEach(function (w) { cur.appendChild(h('div', { class: 'warn' }, h('b', { text: 'WARNING ' }), w)); });
      if ((stp.tools || []).length) cur.appendChild(h('div', { class: 'meta' }, h('b', { text: 'You need: ' }), stp.tools.join(', ')));
      if (stp.expected) cur.appendChild(h('div', { class: 'expected' }, h('b', { text: 'How you know it worked: ' }), stp.expected));
      if ((stp.cites || []).length) cur.appendChild(h('ul', { class: 'cites' }, stp.cites.map(function (ct) {
        var src = by[ct.source]; return citeRow({ where: src ? src.title : ct.source, loc: ct.loc, quote: ct.quote, url: ct.url || (src && src.url) }, false);
      })));
      var wy = h('dl', { class: 'kv wy' });
      if (stp.why) { wy.appendChild(h('dt', { text: 'Why' })); wy.appendChild(h('dd', { text: cueText(stp.why) })); }
      if (stp.where) { wy.appendChild(h('dt', { text: 'Where' })); wy.appendChild(h('dd', { text: cueText(stp.where) })); }
      if (wy.children.length) cur.appendChild(wy);
      if ((stp.faq || []).length) {
        cur.appendChild(h('h3', { text: 'Questions people ask' }));
        stp.faq.forEach(function (f) { cur.appendChild(h('details', { class: 'faq' }, h('summary', { text: f.q }), h('div', { text: cueText(f.a) }))); });
      }
      if ((stp.troubleshoot || []).length) {
        cur.appendChild(h('h3', { text: 'If it does not work, CHECK' }));
        var tl = h('ul', { class: 'trbl' });
        stp.troubleshoot.forEach(function (k) {
          var cs = (k.cites || []).map(function (ct) {
            var src = by[ct.source]; return citeRow({ where: src ? src.title : ct.source, loc: ct.loc, quote: ct.quote, url: ct.url }, false);
          });
          tl.appendChild(h('li', null, h('div', { class: 'pb-t', text: cueText(k.action) }), h('div', { class: 'meta', text: k.why }), cs.length ? h('ul', { class: 'cites' }, cs) : null));
        });
        cur.appendChild(tl);
      }
      cur.appendChild(h('div', { class: 'meta', text: stp.guide_id ? 'The picture for this step is directly below.' : 'This step has no guide pictures.' }));
    });
  }

  // ------------------------------------------------------------------ shared POST helper
  // Resolves {status, text, json}; status 0 = network failure. Never throws for HTTP errors (callers report them honestly).
  function postJson(path, body) {
    var ctl = new AbortController(), t = setTimeout(function () { ctl.abort(); }, 8000);
    return fetch(CORE + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctl.signal }).then(function (r) {
      return r.text().then(function (txt) { var j = null; try { j = JSON.parse(txt); } catch (e) { /* non-JSON body */ } return { status: r.status, ok: r.ok, text: txt, json: j }; }).finally(function () { clearTimeout(t); });
    }, function () { clearTimeout(t); return { status: 0, ok: false, text: '', json: null }; });
  }
  function fixtureJson(name) { return fetch('fixtures/' + name + '.json').then(function (r) { return r.json(); }); }
  function sessionReady() { var f = fresh(); return !!(S.state && f.ok && S.state.session && S.state.session.id); }

  // ------------------------------------------------------------------ goal box
  function renderGoalHint() {
    var btn = $('goal-send'), hint = $('goal-hint'), f = fresh();
    btn.disabled = !sessionReady() || S.goalBusy;
    var t = !S.state ? 'Connecting to your workspace…' : !f.ok ? 'Connection lost. Your progress is kept; reconnect to continue.' : 'Pick a ready guide or describe any physical task. If there is no ready guide, GhostBuild researches one now (a few minutes) and starts it for you.';
    memo(hint, t, function () { hint.textContent = t; });
  }
  function showResolution(r, note) {
    var box = $('goal-result'); clear(box);
    var kind = r.status === 'supported' ? 'supported' : r.status === 'ambiguous' ? 'ambiguous' : 'unsupported';
    var el = h('div', { class: 'res ' + kind },
      h('div', { class: 'st', text: r.status.toUpperCase() + ' · ' + String(r.mode).toUpperCase() + (r.task_title ? ' · ' + r.task_title : '') }),
      r.cue ? h('div', { class: 'cue' }, r.cue.line1, r.cue.line2 ? h('br') : null, r.cue.line2 || null) : null,
      h('div', { text: r.detail || '' }));
    if (r.status === 'supported') { document.body.classList.remove('goal-open'); window.dispatchEvent(new CustomEvent('ghostbuild:answer', {detail: {text: r.detail}})); }
    if (r.research_queued) el.appendChild(h('div', { class: 'queued', text: L.NOT_AVAILABLE }));
    if (note) el.appendChild(h('div', { class: 'meta', text: note }));
    if (r.alternatives && r.alternatives.length) {
      el.appendChild(h('div', { class: 'meta', text: r.status === 'supported' ? 'Other supported tasks:' : 'Supported right now (tap to fill the goal box):' }));
      var chips = h('div', { class: 'chips' });
      r.alternatives.forEach(function (alt) { chips.appendChild(h('button', { type: 'button', text: alt })); });
      Array.prototype.forEach.call(chips.children, function (b) { b.addEventListener('click', function () { $('goal-text').value = b.textContent; $('goal-text').focus(); }); });
      el.appendChild(chips);
    }
    if (r.status !== 'supported') {
      var sv = h('button', { type: 'button', class: 'ghost', text: 'Request async research instead' });
      sv.addEventListener('click', function () { document.querySelector('.area-research').open = true; $('research-text').value = $('goal-text').value; $('creao-goal').value = $('goal-text').value; var cm = document.querySelector('input[name=cintent][value=' + r.mode + ']'); if (cm) cm.checked = true; var m = document.querySelector('input[name=rmode][value=' + r.mode + ']'); if (m) m.checked = true; $('research-text').focus(); });
      el.appendChild(sv);
    }
    box.appendChild(el);
  }
  function showGoalError(msg) { var box = $('goal-result'); clear(box); box.appendChild(h('div', { class: 'res err', role: 'alert' }, h('div', { class: 'st', text: 'NOT SENT / FAILED' }), h('div', { text: msg }))); }
  $('goal-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    if (!sessionReady() || S.goalBusy) return;
    window.dispatchEvent(new Event('ghostbuild:input'));
    var text = $('goal-text').value.trim(), mode = L.inferMode(text);
    var body = { v: 2, session_id: S.state.session.id, mode: mode, via: 'phone_text', text: text ? text : null };
    S.goalBusy = true; renderGoalHint();
    var p;
    if (FIXTURE) {
      var pbFx = FIXTURE.indexOf('state_playbook') === 0;
      var shelf = /shelf|flat.?pack|assemble|bookcase/i.test(text);
      var cam = /camera|lens|view|pi\b|inspection|black|dark/i.test(text) || (mode === 'build' && /station|setup|set up/i.test(text));
      var name = pbFx ? (shelf ? 'goal_resolution_supported_shelf' : cam ? 'goal_resolution_supported' : 'goal_resolution_unsupported_research') : 'goal_resolution_' + (cam ? 'supported' : 'unsupported');
      p = fixtureJson(name).then(function (j) { j.mode = mode; showResolution(j, 'FIXTURE RESPONSE: no backend was contacted.'); });
    } else {
      p = postJson('/session/goal', body).then(function (r) {
        if (!r.ok) throw new Error(r.status === 0 ? 'could not reach core' : 'HTTP ' + r.status + ' ' + r.text.slice(0, 200));
        if (!r.json || !r.json.status) throw new Error('core answered with an unexpected body');
        showResolution(r.json);
      });
    }
    p.catch(function (e) { showGoalError(e.message); }).then(function () { S.goalBusy = false; renderGoalHint(); });
  });

  // ------------------------------------------------------------------ ask box: POST /ask {session_id, text} -> {answer:{line1,line2}|null, text, intent}
  function renderAskHint() {
    var btn = $('ask-send'), hint = $('ask-hint'), f = fresh();
    btn.disabled = !sessionReady() || S.askBusy;
    var t = !S.state ? 'Waiting for core.' : !f.ok ? 'Core is not answering; questions cannot be sent.' : 'Answers come from the loaded card. Asking never confirms a step.';
    memo(hint, t, function () { hint.textContent = t; });
  }
  function showAsk(r, note) {
    if (r.pending) { var pb_ = $('ask-result'); clear(pb_); pb_.appendChild(h('div', { class: 'res ambiguous' }, h('div', { class: 'st', text: 'THINKING' }), h('p', { class: 'detail', text: 'Your answer will appear here. The step and its picture stay in place.' }))); window.dispatchEvent(new Event('ghostbuild:asked')); return; }
    if (['where', 'how', 'correct'].indexOf(r.intent) >= 0) S.guideView = r.intent;
    if (['parts', 'picture', 'goto'].indexOf(r.intent) >= 0) S.guideView = null;
    var box = $('ask-result'); clear(box);
    var el = h('div', { class: 'res ' + (r.answer ? 'supported' : 'ambiguous') },
      h('div', { class: 'st', text: r.cached ? 'SAVED ANSWER' : 'YOUR ANSWER' }),
      h('p', { class: 'detail', text: r.text }));
    if (r.answer) { el.appendChild(h('div', { class: 'meta', text: 'On your glasses' })); el.appendChild(h('div', { class: 'cue' }, r.answer.line1, r.answer.line2 ? h('br') : null, r.answer.line2 || null)); }
    else el.appendChild(h('div', { class: 'meta', text: 'No short cue was returned, so this is phone text only.' }));
    el.appendChild(h('div', { class: 'meta', text: note || (r.label ? 'Source: ' + r.label + ' · Current step only.' : 'From the loaded guide. Unknown facts are left unanswered.') }));
    box.appendChild(el);
    window.dispatchEvent(new CustomEvent('ghostbuild:answer', {detail: r}));
  }
  function showAskError(msg) { var box = $('ask-result'); clear(box); box.appendChild(h('div', { class: 'res err', role: 'alert' }, h('div', { class: 'st', text: 'NO ANSWER' }), h('div', { text: msg }))); }
  window.addEventListener('ghostbuild:voice-result', function (ev) {
    var box = $('ask-result'); clear(box);
    box.appendChild(h('div', {class:'res supported'}, h('div', {class:'st',text:'YOUR SPECIALIST'}), h('p',{class:'detail',text:ev.detail.text})));
  });
  function fixtureAsk(text) {
    // FIXTURE ONLY: word-overlap match against the loaded card's FAQ so the page can be demonstrated with no backend.
    var words = String(text).toLowerCase().split(/\W+/).filter(function (w) { return w.length > 2; }), best = null, bs = 0;
    ((S.card && S.card.steps) || []).forEach(function (stp) {
      (stp.faq || []).forEach(function (f) { var sc = words.filter(function (w) { return f.q.toLowerCase().indexOf(w) >= 0; }).length; if (sc > bs) { bs = sc; best = f; } });
    });
    return best ? { answer: best.a, text: best.q + ': ' + cueText(best.a), intent: 'faq' } : { answer: null, text: 'FIXTURE: no FAQ in this card matches that question.', intent: 'unknown' };
  }
  $('ask-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    var text = $('ask-text').value.trim();
    if (!sessionReady() || S.askBusy) return;
    window.dispatchEvent(new Event('ghostbuild:input'));
    if (!text) { showAskError('Type a question first.'); return; }
    S.askBusy = true; renderAskHint();
    var p;
    if (FIXTURE) {
      p = Promise.resolve(dev.no404 ? { status: 404, ok: false, text: 'Not Found', json: null } : { status: 200, ok: true, json: fixtureAsk(text) });
    } else p = postJson('/ask', { session_id: S.state.session.id, text: text });
    p.then(function (r) {
      if (!r.ok) return showAskError(L.askError(r.status, r.text));
      var n = L.normalizeAsk(r.json);
      if (!n.ok) return showAskError(n.error);
      return (FIXTURE ? Promise.resolve() : refreshState()).then(function () {
        showAsk(n, FIXTURE ? 'FIXTURE RESPONSE: no backend was contacted.' : null);
        if (!n.pending) window.dispatchEvent(new Event('ghostbuild:asked'));
      });
    }).then(function () { S.askBusy = false; renderAskHint(); });
  });

  // ------------------------------------------------------------------ research box: POST /research/request {session_id, mode, text} -> GoalResolution
  function renderResearchHint() {
    var btn = $('research-send'), hint = $('research-hint'), f = fresh();
    btn.disabled = !sessionReady() || S.resBusy;
    var t = !S.state ? 'Waiting for core.' : !f.ok ? 'Core is not answering; nothing can be saved.' : 'Saving a request does not make it available. It is picked up later and reviewed by a human first.';
    memo(hint, t, function () { hint.textContent = t; });
  }
  function showResearch(res, note) {
    var box = $('research-result'); clear(box);
    var o = L.researchOutcome(res);
    if (o.kind === 'error') return showResearchError(o.note);
    var el = h('div', { class: 'res ' + (o.kind === 'queued' ? 'ambiguous' : o.kind === 'supported' ? 'supported' : 'unsupported') },
      h('div', { class: 'queued', text: o.headline }),
      h('div', { text: o.note }));
    if (res.alternatives && res.alternatives.length) el.appendChild(h('div', { class: 'meta', text: 'Supported right now: ' + res.alternatives.join(' · ') }));
    if (note) el.appendChild(h('div', { class: 'meta', text: note }));
    box.appendChild(el);
  }
  function showResearchError(msg) { var box = $('research-result'); clear(box); box.appendChild(h('div', { class: 'res err', role: 'alert' }, h('div', { class: 'st', text: 'NOT SAVED' }), h('div', { text: msg }))); }
  $('research-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    var text = $('research-text').value.trim(), mode = document.querySelector('input[name=rmode]:checked').value;
    if (!sessionReady() || S.resBusy) return;
    if (!text) { showResearchError('Describe what should be researched first.'); return; }
    S.resBusy = true; renderResearchHint();
    var p;
    if (FIXTURE) {
      p = dev.no404 ? Promise.resolve({ status: 404, ok: false, text: 'Not Found', json: null })
        : fixtureJson('goal_resolution_unsupported_research').then(function (j) { j.mode = mode; return { status: 200, ok: true, json: j }; });
    } else p = postJson('/research/request', { session_id: S.state.session.id, mode: mode, text: text });
    p.then(function (r) {
      if (!r.ok) return showResearchError(L.researchError(r.status, r.text));
      showResearch(r.json, FIXTURE ? 'FIXTURE RESPONSE: no backend was contacted.' : null);
    }).then(function () { S.resBusy = false; renderResearchHint(); });
  });

  // ------------------------------------------------------------------ CREAO research runs (hidden unless GET /research/status says enabled)
  // Admin token and reviewer name live only in these inputs/variables: never stored, never logged, never put in a URL.
  var C = { enabled: false, checked: false, runs: [], selected: null, detail: null, busy: false, approving: false, lastErr: null };
  function creaoUrl(path) {
    if (FIXTURE) return 'fixtures/' + ({ '/research/status': 'research_status_enabled', '/research/runs': 'research_runs' }[path] || ('research_run_' + path.split('/').pop())) + '.json';
    return CORE + path;
  }
  function creaoGet(path) {
    var ctl = new AbortController(), t = setTimeout(function () { ctl.abort(); }, 4000);
    return fetch(creaoUrl(path), { signal: ctl.signal, cache: 'no-store' }).then(function (r) {
      clearTimeout(t); if (!r.ok) throw new Error('HTTP ' + r.status); return r.json();
    }, function (e) { clearTimeout(t); throw e; });
  }
  function creaoCheck() {
    // fixtures: the CREAO box is only shown with &creao=1 so the existing fixture screens stay unchanged
    if (FIXTURE && qs.get('creao') !== '1') { C.checked = true; return; }
    creaoGet('/research/status').then(function (j) { C.enabled = L.creaoEnabled(j); }, function () { C.enabled = false; })
      .then(function () { C.checked = true; renderCreao(); if (C.enabled) creaoPoll(); else setTimeout(creaoCheck, 30000); });
  }
  function creaoPoll() {
    if (!C.enabled) return;
    creaoGet('/research/runs').then(function (j) {
      C.runs = (j && j.runs) || [];
      if (C.selected) return creaoGet('/research/runs/' + encodeURIComponent(C.selected)).then(function (d) { C.detail = d; }, function () { /* keep the last detail */ });
    }).catch(function () { /* transient; shown as stale by the next success */ })
      .then(function () { renderCreao(); setTimeout(creaoPoll, L.anyActive(C.runs) ? 2000 : 8000); });
  }
  function renderCreao() {
    var box = $('creao-box');
    box.hidden = !C.enabled;
    if (!C.enabled) return;
    var hint = $('creao-hint'), btn = $('creao-send');
    btn.disabled = C.busy;
    memo(hint, String(C.busy), function () { hint.textContent = 'Starts a CREAO run. Limits: one active run, one new run per 10 s, 20 per core process.'; });
    var ul = $('creao-runs');
    memo(ul, JSON.stringify([C.runs, C.selected]), function () {
      clear(ul);
      if (!C.runs.length) ul.appendChild(h('li', { class: 'empty', text: 'no runs yet' }));
      C.runs.forEach(function (r) {
        var st = L.runStatus(r);
        var li = h('li', { class: r.run_id === C.selected ? 'sel' : '', tabindex: '0', role: 'button' },
          h('span', { class: 'goal', text: r.goal }), h('span', { class: 'pill pill-' + st.kind, text: st.label }));
        var pick = function () { C.selected = r.run_id; C.detail = null; renderCreao(); creaoGet('/research/runs/' + encodeURIComponent(r.run_id)).then(function (d) { C.detail = d; renderCreao(); }, function () {}); };
        li.addEventListener('click', pick); li.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });
        ul.appendChild(li);
      });
    });
    renderDraft();
  }
  function renderDraft() {
    var box = $('creao-draft'), rec = C.detail;
    memo(box, JSON.stringify([rec, C.approving]), function () {
      clear(box);
      if (!rec) return;
      var st = L.runStatus(rec);
      var el = h('div', { class: 'draft' });
      el.appendChild(h('div', { class: 'banner-draft', text: st.label }));
      el.appendChild(h('div', { class: 'meta', text: 'Run ' + rec.run_id + (rec.creao_run_id ? ' · CREAO run ' + rec.creao_run_id : '') }));
      if (rec.error) el.appendChild(h('div', { class: 'res err', role: 'alert' }, h('div', { class: 'st', text: 'ERROR' }), h('div', { text: rec.error })));
      var vErr = rec.validation_errors || [];
      if (rec.status === 'invalid' && vErr.length) {
        el.appendChild(h('div', { class: 'verr' }, h('b', { text: 'Validation errors (' + vErr.length + ')' }), h('ul', null, vErr.slice(0, 12).map(function (e) { return h('li', { text: e }); }))));
      }
      var v = L.draftView(rec.draft);
      if (v) {
        el.appendChild(h('h4', { text: v.title }));
        el.appendChild(h('div', null, lbl(v.provenance), ' ', h('span', { class: 'meta', text: v.mode.toUpperCase() + ' · ' + v.cardId + ' · DRAFT: not reviewed by a human' })));
        el.appendChild(h('ol', null, v.steps.map(function (s) {
          return h('li', null, h('b', { text: s.title }), ' ', h('span', { class: 'pill', text: s.check }), h('div', { class: 'cue', text: s.cue }),
            s.detail ? h('div', { class: 'meta', text: s.detail }) : null,
            s.warnings.map(function (w) { return h('div', { class: 'warn' }, h('b', { text: 'WARNING ' }), w); }));
        })));
        el.appendChild(h('h4', { text: 'Sources' }));
        el.appendChild(h('ul', null, v.sources.map(function (so) {
          return h('li', null, lbl(so.kind), ' ', so.url ? h('a', { href: so.url, target: '_blank', rel: 'noopener noreferrer', text: so.title }) : h('span', { text: so.title }));
        })));
        if (v.timestamps.length) el.appendChild(h('ul', null, v.timestamps.map(function (t) {
          var loc = h('span', { class: 'ts', text: t.loc });
          return h('li', null, t.step + ' → ', t.url ? h('a', { href: t.url, target: '_blank', rel: 'noopener noreferrer' }, loc) : loc);
        })));
        if (v.uncertainties.length) {
          el.appendChild(h('h4', { text: 'Uncertainties' }));
          el.appendChild(h('ul', null, v.uncertainties.map(function (u) { return h('li', { text: u }); })));
        }
        if (v.references.length) {
          el.appendChild(h('h4', { text: 'Visual references' }));
          el.appendChild(h('div', { class: 'meta', text: L.REFERENCE_ONLY }));
          v.references.forEach(function (r) {
            el.appendChild(h('div', { class: 'refonly' }, h('b', { text: r.view.toUpperCase() + ' · ' + L.REFERENCE_ONLY }), h('div', { text: r.description || '(link only)' }),
              r.url ? h('a', { href: r.url, target: '_blank', rel: 'noopener noreferrer', text: r.url }) : null));
          });
        }
        el.appendChild(h('div', { class: v.validationOk ? 'meta' : 'verr', text: v.validationOk ? 'Validation: OK' : 'Validation errors: ' + v.validationErrors.join(' | ') }));
        if (!v.hasPictures) el.appendChild(h('div', { class: 'meta', text: 'No pictures: this card shows text cues on the glasses.' }));
        if (rec.status === 'draft_ready' && !rec.approved_by) el.appendChild(approveBlock(rec));
      }
      box.appendChild(el);
    });
  }
  function approveBlock(rec) {
    var who = h('input', { type: 'text', id: 'creao-reviewer', maxlength: '80', autocomplete: 'off', placeholder: 'reviewer name' });
    var tok = h('input', { type: 'password', id: 'creao-token', autocomplete: 'off', placeholder: 'admin token (kept in memory only)' });
    var out = h('div', { id: 'creao-approve-out', 'aria-live': 'polite' });
    var btn = h('button', { type: 'button', text: 'Approve this draft' });
    btn.addEventListener('click', function () {
      var chk = L.canApprove(rec, who.value, tok.value);
      if (!chk.ok) { out.textContent = chk.why; return; }
      if (C.approving) return;
      C.approving = true; btn.disabled = true; out.textContent = 'Approving...';
      var p = FIXTURE ? Promise.resolve({ status: 200, ok: true, json: { approved: true, fixture: true } })
        : fetch(CORE + '/cards/drafts/' + encodeURIComponent(rec.draft_id) + '/approve', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-GhostBuild-Token': tok.value }, body: JSON.stringify({ reviewer: who.value.trim() }) })
          .then(function (r) { return r.text().then(function (t) { var j = null; try { j = JSON.parse(t); } catch (e) { /* not JSON */ } return { status: r.status, ok: r.ok, text: t, json: j }; }); }, function () { return { status: 0, ok: false, text: '' }; });
      p.then(function (r) {
        C.approving = false; btn.disabled = false; tok.value = '';
        if (!r.ok) { out.textContent = L.approveError(r.status, r.text); return; }
        out.textContent = FIXTURE ? 'FIXTURE RESPONSE: nothing was approved.' : 'Approved by ' + who.value.trim() + '. The task is now in the task list on the glasses and here.';
        if (!FIXTURE) { loadCatalog(); C.detail = null; }
      });
    });
    return h('div', { class: 'approve' }, h('div', { class: 'meta', text: 'Approving means you reviewed this draft against its sources. The admin token and your name are not stored.' }), who, tok, btn, out);
  }
  $('creao-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    if (C.busy) return;
    var checked = document.querySelector('input[name=cintent]:checked');
    var res = L.buildRunBody({ goal: $('creao-goal').value, device: $('creao-device').value, model: $('creao-model').value, intent: checked && checked.value,
      docUrls: $('creao-docs').value, videoUrls: $('creao-videos').value, followUp: $('creao-follow').value, sessionId: S.state && S.state.session && S.state.session.id !== 'none' ? S.state.session.id : '' });
    var msg = $('creao-msg'); clear(msg);
    if (!res.ok) { msg.appendChild(h('div', { class: 'res err', role: 'alert' }, h('div', { class: 'st', text: 'NOT STARTED' }), h('div', { text: res.errors.join(' ') }))); return; }
    C.busy = true; renderCreao();
    var p = FIXTURE ? Promise.resolve({ status: 202, ok: true, json: { run_id: 'r-fixture' } })
      : postJson('/research/run', res.body);
    p.then(function (r) {
      if (!r.ok) { msg.appendChild(h('div', { class: 'res err', role: 'alert' }, h('div', { class: 'st', text: 'NOT STARTED' }), h('div', { text: L.runError(r.status, r.text) }))); return; }
      msg.appendChild(h('div', { class: 'res ambiguous' }, h('div', { class: 'queued', text: 'Run started' }), h('div', { text: 'Run ' + r.json.run_id + (FIXTURE ? ' (FIXTURE RESPONSE: no backend was contacted)' : '') + '. This takes minutes; the result will be a draft.' })));
      if (!FIXTURE) creaoGet('/research/runs').then(function (j) { C.runs = j.runs || []; C.selected = r.json.run_id; renderCreao(); }, function () {});
    }).then(function () { C.busy = false; renderCreao(); });
  });
  creaoCheck();

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
    var cb404 = h('input', { type: 'checkbox' }); cb404.addEventListener('change', function () { dev.no404 = cb404.checked; });
    bar.appendChild(h('label', null, cb404, 'simulate 404 on /ask + /research'));
  }

  // The companion uses the same card engine; the explicit confirm control is separate from pictures.
  function renderWorkspace() {
    var st = S.state, pb = st && st.playbook, active = st && st.session.phase === 'task';
    document.body.classList.toggle('has-task', !!active);
    $('new-task').hidden = !active;
    if (active) {
      var title = S.card && S.card.title || 'Your task';
      $('workspace-title').textContent = title;
      $('workspace-subtitle').textContent = pb ? (pb.confirmed.length + pb.verified.length) + ' of ' + pb.step_count + ' steps complete. Take it one step at a time.' : 'Guidance from your reviewed task. Evidence stays clearly labeled.';
    }
    var box = $('phone-controls'), hud = st && st.hud;
    var key = JSON.stringify([hud && hud.seq, active, S.actionBusy, fresh().ok]);
    memo(box, key, function () {
      clear(box); if (!active || !hud) return;
      function add(action, text, cls, enabled) {
        var btn = h('button', {type:'button', class:cls, text:text});
        btn.disabled = !fresh().ok || S.actionBusy || enabled === false || !!FIXTURE;
        btn.addEventListener('click', function () { sendAction(action); }); box.appendChild(btn);
      }
      if (hud.answer) {
        add('answer_previous','Previous answer page','secondary',hud.answer.index>0);
        add('answer_next','Next answer page','secondary',hud.answer.index+1<hud.answer.count);
        add('press','Back to my step','secondary');
        return;
      }
      if (hud.mode === 'menu' && pb) { add('previous', 'Back', 'secondary'); box.appendChild(h('p', {class:'meta', text:'Answer the question above (buttons in the step), on the glasses (swipe, press) or by voice.'})); return; }
      add('previous', 'Back', 'secondary');
      var explicitPicture = !!(st && st.help_view);
      add(explicitPicture ? 'previous' : 'press', explicitPicture ? 'Back to step' : 'Show parts / picture', 'secondary');
      if (hud.mode === 'visual' && explicitPicture) add('next_view', 'Next picture', 'secondary');
      if (pb && (hud.mode === 'step' || (hud.mode === 'visual' && !explicitPicture))) add('confirm', 'I completed this step', 'confirm', hud.step && hud.step.check === 'manual');
      if (pb && hud.step && hud.step.check === 'measured') box.appendChild(h('p', {class:'meta', text:'Waiting for measured evidence. A tap or spoken command cannot complete this check.'}));
    });
  }
  function sendAction(action, choice) {
    if (!sessionReady() || S.actionBusy) return;
    window.dispatchEvent(new Event('ghostbuild:input'));
    S.actionBusy = true; renderWorkspace();
    var body = {session_id:S.state.session.id, seq_seen:S.state.hud.seq, action:action};
    if (choice) body.choice = choice;
    postJson('/session/action', body).then(function (r) {
      $('control-result').textContent = r.ok ? (action === 'confirm' ? 'Step confirmed by you.' : action === 'choose' ? 'Noted. Moving to the check that fits.' : 'Updated.') : r.status === 0 ? 'Connection lost. Try again when connected.' : L.detailOf ? L.detailOf(r.text) : 'Display changed. Review the current step and try again.';
      if (r.ok && r.json) { S.state.hud = r.json; if (r.json.image) S.guideView = r.json.image.view; return refreshState(); }
    }).finally(function () { S.actionBusy = false; renderWorkspace(); });
  }
  $('new-task').addEventListener('click', function () { window.dispatchEvent(new Event('ghostbuild:input')); document.body.classList.add('goal-open'); $('h-goal').scrollIntoView({behavior:'smooth', block:'center'}); $('goal-text').focus(); });
  Array.prototype.forEach.call(document.querySelectorAll('[data-question]'), function (btn) {
    btn.addEventListener('click', function () { $('ask-text').value = btn.getAttribute('data-question'); $('ask-form').requestSubmit(); });
  });
  function loadCatalog() {
    if (FIXTURE) { $('task-catalog').textContent = 'Fixture preview. Open the live companion to choose a task.'; return; }
    getJson('/catalog').then(function (r) {
      S.catalog = r.json.tasks || []; renderCatalog();
    }).catch(function () { $('task-catalog').textContent = 'Prepared guides will appear when connected.'; setTimeout(loadCatalog, 5000); });
  }
  function renderCatalog() {
    var box = $('task-catalog'); clear(box);
    S.catalog.forEach(function (task) {
      var btn = h('button', {type:'button'}, h('span', {text:task.title}), h('small', {text: task.steps ? task.steps + ' STEPS  ↗' : 'EVIDENCE CHECK  ↗'}));
      btn.addEventListener('click', function () { $('goal-text').value = task.title; $('goal-form').requestSubmit(); }); box.appendChild(btn);
    });
    if (!box.children.length) box.appendChild(h('p',{class:'meta',text:'No prepared guide yet. Describe your task above and it can be researched.'}));
  }
  window.addEventListener('ghostbuild:assistant', function (e) { S.assistant = e.detail; tick(true); });
  var helpPanelKey = '';
  window.addEventListener('ghostbuild:step-help', function (e) {
    var d=e.detail, current=d.current, key=JSON.stringify(d);
    if (!current || key===helpPanelKey) return;
    helpPanelKey=key;
    if (d.pending) { showAsk({pending:true}); return; }
    if (d.message) {
      var box=$('ask-result');clear(box);
      box.appendChild(h('div',{class:'res supported'}, h('div',{class:'st',text:d.message.cached?'SAVED ANSWER':'YOUR ANSWER'}), h('p',{class:'detail',text:d.message.text}), h('div',{class:'meta',text:d.message.grounding==='guide'?'From the guide':d.message.grounding==='general'?'General knowledge · check the manual':'Check the source'})));
    } else clear($('ask-result'));
  });
  function stepNotes(card, stp) {
    var list = window.GBAssistant ? window.GBAssistant.notesFor(card.card_id, stp.id) : [];
    if (!list.length) return null;
    var box = h('div', { class: 'step-notes' }, h('h4', { text: 'Extra help on this step' }));
    list.forEach(function (n) { box.appendChild(h('div', { class: 'note' }, h('div', { class: 'nt', text: n.title }), h('div', { class: 'meta', text: 'You asked: ' + n.question }), h('div', { text: n.answer }), h('div', { class: 'meta', text: n.grounding === 'guide' ? 'From the guide' : n.grounding === 'general' ? 'General knowledge, not from the guide' : 'Not sure. Check the source' }))); });
    return box;
  }
  // ------------------------------------------------------------------ live research panel: GET /research/live
  function fmtClock(sec) { return Math.floor(sec / 60) + ':' + ('0' + (sec % 60)).slice(-2); }
  function renderLive() {
    var box = $('live-research'), a = S.live && S.live.active;
    box.hidden = !a;
    if (!a) return;
    var p = a.progress || null, pct = p ? Math.round(p.fraction * 100) : 0;
    $('live-time').textContent = fmtClock(a.elapsed_s || 0); $('live-goal').textContent = a.goal;
    $('live-fill').style.width = pct + '%';
    box.querySelector('.live-track').setAttribute('aria-valuenow', String(pct));
    $('live-left').textContent = L.waitText(p);
    box.classList.toggle('over', !!(p && p.over));
    var ol = $('live-stages');
    if (p && ol.children.length !== p.stages.length) { clear(ol); p.stages.forEach(function (t) { ol.appendChild(h('li', { text: t })); }); }
    if (p) Array.prototype.forEach.call(ol.children, function (li, i) { li.className = i < p.stage ? 'done' : i === p.stage ? 'now' : ''; });
  }
  function pollLive() {
    if (FIXTURE) return;
    getJson('/research/live').then(function (r) {
      var wasActive = !!(S.live && S.live.active); S.live = r.json; renderLive();
      if (wasActive && !S.live.active) loadCatalog();
    }).catch(function () {}).then(function () { setTimeout(pollLive, S.live && S.live.active ? 1000 : 4000); });
  }
  pollLive();
  loadCatalog();
  function tick(poll) { renderWorkspace(); renderStatus(); renderMirror(); renderTask(); renderPlaybook(); renderTimeline(); renderGuides(); renderGoalHint(); renderAskHint(); renderResearchHint(); }
  window.GBWorkspace = {refresh:refreshState};
  devbar(); tick(); poll(); setInterval(tick, 500);
})();
