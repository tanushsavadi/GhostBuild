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
    if (state && state.session && state.session.phase !== 'task') return false;
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
  /** The words decide build vs fix; core retries the other mode if nothing matches, so this is only a hint. */
  function inferMode(text) {
    return /\b(fix|broken|black|dark|blank|not working|doesn't|does not|won't|wrong|lost|repair|problem|stuck|covered|dead|no picture|isn't|stopped)\b/i.test(String(text || '')) ? 'fix' : 'build';
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
    var result = { ok: true, answer: a ? { line1: a.line1, line2: typeof a.line2 === 'string' ? a.line2 : '' } : null, text: j.text, intent: typeof j.intent === 'string' ? j.intent : 'unknown' };
    if (typeof j.label === 'string') result.label = j.label;
    return result;
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

  // ---------------------------------------------------------------- CREAO research runs (only when GET /research/status says enabled)
  var REFERENCE_ONLY = 'reference only — no picture on glasses';
  /** Nothing CREAO-related is shown unless core reports it enabled. */
  function creaoEnabled(status) { return !!status && typeof status === 'object' && status.enabled === true; }
  function parseUrls(text) {
    return String(text || '').split(/[\s,]+/).map(function (x) { return x.trim(); }).filter(Boolean);
  }
  function isHttpUrl(u) { return /^https?:\/\/[^\s/$.?#][^\s]*$/i.test(String(u || '')); }
  /** form: {goal, device, model, intent, docUrls, videoUrls, followUp} (URL fields are free text). -> {ok, errors, body} */
  function buildRunBody(form) {
    var errors = [], f = form || {};
    var goal = String(f.goal || '').trim();
    if (!goal) errors.push('Describe the goal first.');
    if (goal.length > 300) errors.push('The goal is limited to 300 characters.');
    var doc = parseUrls(f.docUrls), vid = parseUrls(f.videoUrls);
    doc.concat(vid).forEach(function (u) { if (!isHttpUrl(u)) errors.push('Only http(s) links are accepted: ' + u.slice(0, 60)); });
    if (doc.length > 5 || vid.length > 5) errors.push('At most 5 documentation links and 5 video links.');
    var body = { goal: goal };
    ['device', 'model', 'intent'].forEach(function (k) { var v = String(f[k] || '').trim(); if (v) body[k] = v; });
    var fu = String(f.followUp || '').trim(); if (fu) body.follow_up = fu;
    if (doc.length) body.doc_urls = doc;
    if (vid.length) body.video_urls = vid;
    if (f.sessionId) body.session_id = f.sessionId;
    return { ok: errors.length === 0, errors: errors, body: body };
  }
  /** Status chip for a run record. A draft is never described as approved or available; approved_by is the only exception. */
  function runStatus(rec) {
    var st = rec && rec.status;
    if (st === 'draft_ready' && rec.approved_by) return { kind: 'ok', label: 'APPROVED by ' + rec.approved_by, active: false };
    if (st === 'draft_ready') return { kind: 'warn', label: 'DRAFT — needs human approval', active: false };
    if (st === 'queued') return { kind: 'warn', label: 'queued', active: true };
    if (st === 'running') return { kind: 'warn', label: 'running' + (rec.creao_status ? ' (' + rec.creao_status + ')' : ''), active: true };
    if (st === 'invalid') return { kind: 'bad', label: 'INVALID — cannot be approved', active: false };
    if (st === 'failed') return { kind: 'bad', label: 'FAILED', active: false };
    return { kind: 'warn', label: String(st || 'unknown'), active: false };
  }
  function anyActive(runs) { return (runs || []).some(function (r) { return runStatus(r).active; }); }
  /** Preview model of GET /research/runs/{id}.draft. Visual references are always reference-only. */
  function draftView(draft) {
    if (!draft || typeof draft !== 'object') return null;
    var refs = (draft.visual_references || []).map(function (v) { return { view: v.view, url: isHttpUrl(v.url) ? v.url : null, description: v.description || '', note: REFERENCE_ONLY }; });
    var valErrors = (draft.validation && draft.validation.errors) || [];
    return {
      title: draft.title || '', cardId: draft.card_id || '', mode: draft.goal_mode || '', provenance: draft.provenance || '',
      steps: (draft.steps || []).map(function (st, i) { return { n: i + 1, title: st.title, cue: [st.cue && st.cue.line1, st.cue && st.cue.line2].filter(Boolean).join(' / '), check: st.check === 'measured' ? 'MEASURED' : 'you confirm it', detail: st.detail || '', warnings: st.warnings || [] }; }),
      sources: (draft.sources || []).map(function (so) { return { kind: so.kind, title: so.title, url: isHttpUrl(so.url) ? so.url : null }; }),
      timestamps: collectTimestamps(draft),
      uncertainties: draft.uncertainties || [],
      references: refs,
      hasPictures: !!draft.pictures_on_glasses,
      validationOk: !!(draft.validation && draft.validation.ok) && valErrors.length === 0,
      validationErrors: valErrors,
    };
  }
  /** [{source, loc, url, step}] for every step cite whose loc is a timestamp. */
  function collectTimestamps(draft) {
    var out = [];
    (draft.steps || []).forEach(function (st) { (st.cites || []).forEach(function (c) { if (isTimestampLoc(c.loc)) out.push({ source: c.source, loc: c.loc, url: isHttpUrl(c.url) ? c.url : null, step: st.title }); }); });
    return out;
  }
  /** Approve only with an approved-able draft, a reviewer name and a token (both kept in memory by the page). */
  function canApprove(rec, reviewer, token) {
    if (!rec || rec.status !== 'draft_ready' || !rec.draft_id || rec.approved_by) return { ok: false, why: rec && rec.approved_by ? 'Already approved.' : 'Only a valid draft can be approved.' };
    if (!rec.draft || !rec.draft.validation || rec.draft.validation.ok !== true) return { ok: false, why: 'The draft does not validate.' };
    if (!String(reviewer || '').trim()) return { ok: false, why: 'Enter your name as reviewer.' };
    if (!String(token || '').trim()) return { ok: false, why: 'Enter the admin token.' };
    return { ok: true, why: '' };
  }
  function runError(status, body) {
    if (status === 503) return 'CREAO is disabled on this core (set GB_CREAO=1 and CREAO_API_KEY on the backend). Nothing was started.';
    if (status === 429) return 'Not started: ' + (detailOf(body) || 'rate limit') + '.';
    if (status === 422) return 'Not started: ' + (detailOf(body) || 'invalid request') + '.';
    if (status === 0) return 'Could not reach core. Nothing was started.';
    return 'Not started: HTTP ' + status + (body ? ' ' + String(body).slice(0, 160) : '') + '.';
  }
  function approveError(status, body) {
    if (status === 401) return 'NOT APPROVED: the admin token was rejected.';
    if (status === 503) return 'NOT APPROVED: approval is disabled on this core (GB_ADMIN_TOKEN is not set).';
    if (status === 409) return 'NOT APPROVED: ' + (detailOf(body) || 'refused') + '.';
    if (status === 422) return 'NOT APPROVED: a reviewer name is required.';
    if (status === 0) return 'NOT APPROVED: could not reach core.';
    return 'NOT APPROVED: HTTP ' + status + (body ? ' ' + String(body).slice(0, 160) : '') + '.';
  }
  function detailOf(body) {
    try { var j = typeof body === 'string' ? JSON.parse(body) : body; if (j && typeof j.detail === 'string') return j.detail.slice(0, 240); } catch (e) { /* not JSON */ }
    return '';
  }

  return {
    isPlaybookCard: isPlaybookCard, cardUsesTelemetry: cardUsesTelemetry, usesTelemetry: usesTelemetry,
    showPiHealth: showPiHealth, showPiBanners: showPiBanners, currentStepIndex: currentStepIndex,
    stepStatus: stepStatus, stepRule: stepRule, inferMode: inferMode, counterText: counterText, collectCites: collectCites,
    provenanceNote: provenanceNote, isTimestampLoc: isTimestampLoc,
    normalizeAsk: normalizeAsk, askError: askError, researchOutcome: researchOutcome, researchError: researchError,
    NOT_AVAILABLE: NOT_AVAILABLE,
    REFERENCE_ONLY: REFERENCE_ONLY, creaoEnabled: creaoEnabled, parseUrls: parseUrls, isHttpUrl: isHttpUrl, buildRunBody: buildRunBody,
    runStatus: runStatus, anyActive: anyActive, draftView: draftView, collectTimestamps: collectTimestamps, canApprove: canApprove,
    runError: runError, approveError: approveError,
  };
});
