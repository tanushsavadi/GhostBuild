/* Guide Studio pure logic: source matching, route map, step evidence, live-compile view, G2 frame text. No DOM or network. */
(function (root) {
  'use strict';
  function normUrl(u) {
    var m = /^\s*(https?):\/\/([^\/?#\s]+)([^?#\s]*)/i.exec(String(u || ''));
    if (!m) return null;
    var host = m[2].toLowerCase().replace(/^www\./, '').replace(/:\d+$/, '');
    var path = decodeURIComponent(m[3] || '/').replace(/\/+$/, '').toLowerCase();
    return host + (path || '');
  }
  function host(u) { var n = normUrl(u); return n ? n.split('/')[0] : null; }
  /** Which loaded guides are built from this URL: exact source page, or only the same site. */
  function matchUrl(guides, url) {
    var n = normUrl(url), out = { valid: !!n, exact: [], site: [] };
    if (!n) return out;
    var h = n.split('/')[0];
    (guides || []).forEach(function (g) {
      var hit = null, near = null;
      (g.sources || []).forEach(function (s) {
        var sn = normUrl(s.url);
        if (!sn) return;
        if (sn === n) hit = hit || s;
        else if (sn.split('/')[0] === h) near = near || s;
      });
      if (hit) out.exact.push({ card_id: g.card_id, title: g.title, source: hit });
      else if (near) out.site.push({ card_id: g.card_id, title: g.title, source: near });
    });
    return out;
  }
  function pageOf(cite) {
    var m = /[#&]page=(\d+)/.exec((cite && cite.url) || '') || /\bpage\s+(\d+)/i.exec((cite && cite.loc) || '');
    return m ? Number(m[1]) : null;
  }
  function stepById(card, id) { return ((card && card.steps) || []).filter(function (s) { return s.id === id; })[0] || null; }
  /** Where each step can lead. Same rules as PlaybookEngine: outcome/stop finish; `next` jumps; otherwise the following step. */
  function routes(card) {
    var steps = (card && card.steps) || [];
    return steps.map(function (s, i) {
      var to = [];
      if (s.kind === 'question') (s.choices || []).forEach(function (c) { var t = stepById(card, c.next); to.push({ label: c.label, to: c.next || null, title: t ? t.title : null }); });
      else if (s.kind === 'outcome' || s.kind === 'stop') { /* the runtime finishes the guide here */ }
      else { var nx = s.next ? stepById(card, s.next) : steps[i + 1]; if (nx) to.push({ label: 'then', to: nx.id, title: nx.title }); }
      return { id: s.id, n: i + 1, title: s.title, kind: s.kind || 'action', risk: s.risk || 'low', to: to, ends: !to.length };
    });
  }
  /** Steps that only a branch reaches (not the plain step-after-step line): shown indented as alternatives. */
  function branchOnly(card) {
    var steps = (card && card.steps) || [], seq = {}, viaChoice = {};
    steps.forEach(function (s, i) {
      if (s.kind === 'question') (s.choices || []).forEach(function (c) { if (c.next) viaChoice[c.next] = 1; });
      else if (s.kind !== 'outcome' && s.kind !== 'stop' && i + 1 < steps.length) seq[s.next || steps[i + 1].id] = 1;
    });
    var out = {}; Object.keys(viaChoice).forEach(function (id) { if (!seq[id]) out[id] = 1; }); return out;
  }
  /** The evidence behind one step: each cite joined with its source record. */
  function evidence(card, step) {
    var src = {}; ((card && card.sources) || []).forEach(function (s) { src[s.id] = s; });
    return ((step && step.cites) || []).map(function (c) {
      var s = src[c.source] || {};
      return { quote: c.quote || null, loc: c.loc || null, url: c.url || s.url || null, page: pageOf(c), title: s.title || c.source, kind: s.kind || null, host: host(c.url || s.url) };
    });
  }
  /** Honest provenance words for a whole guide. Nothing is called reviewed unless the card says a person reviewed it. */
  function guideLabels(g) {
    var out = [];
    if (g.provenance) out.push(g.provenance);
    if (g.ai_compiled) out.push('AI-COMPILED · NOT HUMAN-REVIEWED');
    if (g.quoted && g.quoted === g.steps) out.push('EVERY STEP QUOTES ITS SOURCE');
    else if (g.cited) out.push(g.cited + '/' + g.steps + ' STEPS CITE A PAGE');
    return out;
  }
  function liveView(live) {
    live = live || {};
    if (live.active) {
      var p = live.active.progress || {};
      return { state: 'running', goal: live.active.goal, fraction: p.fraction || 0, stage: (p.stages || [])[p.stage] || live.active.status || 'Researching', elapsed: live.active.elapsed_s || 0, estimate: true };
    }
    if (!live.enabled) return { state: 'off', text: 'Live compiling is off on this backend (GB_LIVE_RESEARCH=0). Guides below were compiled earlier from their sources.' };
    if (live.last) return { state: live.last.ok ? 'done' : 'failed', goal: live.last.goal, card_id: live.last.card_id || null, text: live.last.ok ? 'Compiled' : 'No reliable guide: ' + (live.last.error || live.last.status || 'refused') };
    return { state: 'idle', text: 'Ready to compile a new task from official sources.' };
  }
  /** Text the glasses mirror shows for a HudFrame (same rules as the companion mirror). */
  function frameText(f) {
    if (!f || f.mode === 'quiet') return { kind: 'empty', l1: 'QUIET · DISPLAY RESTING' };
    var cue = f.cue || { line1: '', line2: '' }, tag = [];
    if (f.step) tag.push((f.step.index + 1) + '/' + f.step.count);
    if (f.image && f.image.count > 1) tag.push('PIC ' + (f.image.index + 1) + '/' + f.image.count);
    if (f.mode === 'menu' && f.menu) return { kind: 'menu', l1: f.menu.prompt, options: f.menu.options.map(function (o, i) { return (i === f.menu.selected ? '> ' : '  ') + o; }), tag: tag.join('  ') };
    return { kind: f.mode === 'visual' && f.image ? 'visual' : 'text', l1: cue.line1, l2: cue.line2 || '', image: f.mode === 'visual' ? f.image : null, tag: tag.join('  ') };
  }
  /** For a product guide: the shortlist candidate / configuration option whose id is part of the card id. */
  function pickId(cardId, ids) { return (ids || []).filter(function (id) { return id && String(cardId).indexOf(String(id)) >= 0; })[0] || null; }
  var api = { normUrl: normUrl, host: host, matchUrl: matchUrl, pageOf: pageOf, routes: routes, branchOnly: branchOnly, evidence: evidence, guideLabels: guideLabels, liveView: liveView, frameText: frameText, pickId: pickId };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GBStudio = api;
})(typeof window !== 'undefined' ? window : globalThis);
