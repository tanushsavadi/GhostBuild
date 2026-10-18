/* GhostBuild phone page: pure logic (no DOM, no network). Loaded by index.html as window.GBLogic and by node tests
 * (g2/tools/web-logic.test.mjs). Rules it encodes:
 *  - a card "uses telemetry" if it has fault tests or any step with a `verify` check; only then do Pi problems matter
 *  - a manual playbook never shows a Pi banner (works with no Pi at all)
 *  - step badges: HUMAN CONFIRMED (wearer) / MEASURED (evidence) / pending; never anything stronger
 *  - an unavailable endpoint is reported as unavailable, never as an answer. Research is only ever "saved", never "available". */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api; else root.GBLogic = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function steps(card) { return (card && Array.isArray(card.steps)) ? card.steps : []; }
  function isPlaybookCard(card) { return steps(card).length > 0; }
  function cardUsesTelemetry(card) {
    if (!card) return false;
    if (Array.isArray(card.tests) && card.tests.length > 0) return true;
    return steps(card).some(function (s) { return !!s.verify; });
  }
  /** Without the card yet (still loading) a non-playbook engine implies a fault/telemetry card; PLAYBOOK implies none until the card says so. */
  function usesTelemetry(state, card) {
    if (card) return cardUsesTelemetry(card);
    return !!state && state.engine !== 'PLAYBOOK' && !(state.playbook);
  }
  /** Pi health rows are shown when the link is not down, or when the card actually depends on it. */
  function showPiHealth(state, card) {
    var link = state && state.health && state.health.pi_link;
    return link !== 'down' || usesTelemetry(state, card);
  }
  /** Red/amber Pi banners only for cards that depend on telemetry. A manual playbook never gets one. */
  function showPiBanners(state, card) { return usesTelemetry(state, card); }

  /** Index of the current step: trust step_id when it disagrees with step_index (cards can be re-approved mid-session). */
  function currentStepIndex(state, card) {
    var pb = state && state.playbook, list = steps(card);
    if (!pb || !list.length) return -1;
    if (list[pb.step_index] && list[pb.step_index].id === pb.step_id) return pb.step_index;
    for (var i = 0; i < list.length; i++) if (list[i].id === pb.step_id) return i;
    return Math.min(Math.max(0, pb.step_index), list.length - 1);
  }

  /** {kind, label}: kind in confirmed | measured | pending | current. `sourceLabel` is REPLAY/SIMULATED when evidence is not live. */
  function stepStatus(step, pb) {
    var id = step.id;
    var confirmed = !!(pb && (pb.confirmed || []).indexOf(id) >= 0);
    var verified = !!(pb && (pb.verified || []).indexOf(id) >= 0);
    if (verified) return { kind: 'measured', label: 'MEASURED' };
    if (confirmed) return { kind: 'confirmed', label: 'HUMAN CONFIRMED' };
    return { kind: 'pending', label: 'pending' };
  }
  /** How a step gets completed, shown next to a pending step. */
  function stepRule(step) {
    return step.verify ? 'completes only on measured evidence' : 'you confirm it (swipe down on the glasses)';
  }

  /** The glasses' small counter, mirrored: 1-based `n/m`, a bullet for a measured step, OK when confirmed. */
  function counterText(hud) {
    var s = hud && hud.step;
    if (!s || !(s.count >= 1)) return '';
    var n = Math.min(Math.max(0, Math.trunc(s.index)), Math.trunc(s.count) - 1) + 1;
    return (s.check === 'measured' ? '● ' : '') + n + '/' + Math.trunc(s.count) + (s.confirmed ? ' OK' : '');
  }

  /** source id -> [{where, loc, quote, url, stepId}] from every cite on the card (fault checks and step troubleshoot). */
  function collectCites(card) {
    var out = {};
    function add(list, where, stepId) {
      (list || []).forEach(function (c) {
        (out[c.source] = out[c.source] || []).push({ where: where, loc: c.loc, quote: c.quote || null, url: c.url || null, stepId: stepId || null });
      });
    }
    ((card && card.tests) || []).forEach(function (t) {
      (t.checks || []).forEach(function (k) { add(k.cites, 'check: ' + (k.action && k.action.line1), null); });
    });
    steps(card).forEach(function (s) {
      (s.troubleshoot || []).forEach(function (k) { add(k.cites, s.title + ': ' + (k.action && k.action.line1), s.id); });
    });
    return out;
  }

  /** Plain-language provenance. Never upgrades: AI extraction is always described as reviewed-by-a-human, authored data as authored. */
  function provenanceNote(label) {
    if (label === 'AI-EXTRACTED · HUMAN-REVIEWED') return 'Extracted from the sources below by an AI at build time, then reviewed by a human before it could reach the glasses.';
    if (label === 'AUTHORED DEMO METADATA') return 'Written by the team as demo data. It is not extracted from the sources below and has not been checked against them.';
    if (label === 'AUTHORED PROJECT SPEC') return 'Written by the team as a project spec.';
    if (label === 'MANUFACTURER DOC') return 'Taken from manufacturer documentation.';
    return '';
  }

  function isTimestampLoc(loc) { return /^t=\d{1,2}:\d{2}(:\d{2})?$/.test(String(loc || '')) || /(^|\s)t=\d+s?\b/.test(String(loc || '')); }

  // ---------------------------------------------------------------- /ask
  /** POST /ask response contract: {answer:{line1,line2}|null, text:string, intent:string}. */
  function normalizeAsk(j) {
    if (!j || typeof j !== 'object' || typeof j.text !== 'string') return { ok: false, error: 'core answered /ask with an unexpected body' };
    var a = j.answer;
    if (a !== null && a !== undefined && (typeof a !== 'object' || typeof a.line1 !== 'string')) return { ok: false, error: 'core answered /ask with an unexpected answer shape' };
    return { ok: true, answer: a ? { line1: a.line1, line2: typeof a.line2 === 'string' ? a.line2 : '' } : null, text: j.text, intent: typeof j.intent === 'string' ? j.intent : 'unknown' };
  }
  function askError(status, body) {
    if (status === 404) return 'ASK NOT AVAILABLE: this core has no POST /ask (HTTP 404). Nothing was answered and nothing was sent to the glasses.';
    if (status === 0) return 'ASK FAILED: could not reach core. Nothing was answered.';
    return 'ASK FAILED: HTTP ' + status + (body ? ' ' + String(body).slice(0, 160) : '') + '. Nothing was answered.';
  }

  // ---------------------------------------------------------------- /research/request
  var NOT_AVAILABLE = 'saved for async research — not available now';
  /** GoalResolution from /research/request (or an unsupported /session/goal). Never implies availability. */
  function researchOutcome(res) {
    if (!res || typeof res !== 'object' || !res.status) return { kind: 'error', headline: 'unexpected response', note: 'core answered with an unexpected body' };
    if (res.status === 'supported') return { kind: 'supported', headline: 'ALREADY SUPPORTED', note: 'A reviewed card already matches this request (' + (res.task_title || res.card_id || 'card') + '). Use the goal box above to start it; no research was needed.' };
    if (res.research_queued) return { kind: 'queued', headline: NOT_AVAILABLE, note: 'Nothing is available for this request yet. A human must review any research result before it can reach the glasses.' };
    return { kind: 'not_queued', headline: 'NOT SAVED — not available now', note: 'Core did not save this request for research. Nothing is available for it.' };
  }
  function researchError(status, body) {
    if (status === 404) return 'RESEARCH NOT AVAILABLE: this core has no POST /research/request (HTTP 404). Nothing was saved.';
    if (status === 0) return 'RESEARCH FAILED: could not reach core. Nothing was saved.';
    return 'RESEARCH FAILED: HTTP ' + status + (body ? ' ' + String(body).slice(0, 160) : '') + '. Nothing was saved.';
  }

  return {
    isPlaybookCard: isPlaybookCard, cardUsesTelemetry: cardUsesTelemetry, usesTelemetry: usesTelemetry,
    showPiHealth: showPiHealth, showPiBanners: showPiBanners, currentStepIndex: currentStepIndex,
    stepStatus: stepStatus, stepRule: stepRule, counterText: counterText, collectCites: collectCites,
    provenanceNote: provenanceNote, isTimestampLoc: isTimestampLoc,
    normalizeAsk: normalizeAsk, askError: askError, researchOutcome: researchOutcome, researchError: researchError,
    NOT_AVAILABLE: NOT_AVAILABLE,
  };
});
