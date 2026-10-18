/* Conversation panel: the assistant's questions and answers, quick replies, spoken replies and per-step notes.
 * Standalone (like audio.js): own fetch, polls GET /assistant/state, never writes server text with innerHTML.
 * Exposes window.GBAssistant { state(), notesFor(cardId, stepId) } and fires 'ghostbuild:assistant' when something changed. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  if (!$('sec-chat')) return;
  var core = (new URLSearchParams(location.search).get('core') || '').replace(/\/+$/, '');
  var S = { st: null, spokenAt: 0, firstLoad: true, sending: false, session: null };
  var GROUND = { guide: 'From the guide', general: 'General knowledge, not from the guide', unsure: 'Not sure. Check the source' };

  function h(tag, cls, text) { var el = document.createElement(tag); if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }
  function get(path) { return fetch(core + path, { cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error(String(r.status)); return r.json(); }); }
  function post(path, body) {
    return fetch(core + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { return r.text().then(function (t) { var j = null; try { j = JSON.parse(t); } catch (e) { /* not JSON */ } return { ok: r.ok, status: r.status, json: j }; }); });
  }

  function render() {
    var st = S.st, sec = $('sec-chat');
    var msgs = (st && st.messages) || [];
    sec.hidden = !(st && st.enabled && (msgs.length || st.pending));
    if (sec.hidden) return;
    var log = $('chat-log'); clear(log);
    msgs.forEach(function (m) {
      var b = h('div', 'bubble ' + m.role);
      b.appendChild(h('div', 'bubble-text', m.text));
      if (m.role === 'assistant' && m.kind === 'step' && m.grounding) b.appendChild(h('div', 'bubble-tag g-' + m.grounding, GROUND[m.grounding] || m.grounding));
      log.appendChild(b);
    });
    $('chat-typing').hidden = !st.pending;
    var last = msgs[msgs.length - 1], chips = $('chat-chips'); clear(chips);
    if (last && last.role === 'assistant' && last.quick_replies && last.quick_replies.length && !st.pending) {
      last.quick_replies.forEach(function (q) { var c = h('button', 'qchip', q); c.type = 'button'; c.addEventListener('click', function () { send(q); }); chips.appendChild(c); });
    }
    log.scrollTop = log.scrollHeight;
    var phase = S.session && S.session.phase;
    $('chat-input').placeholder = st.intake && st.intake.active ? 'Your answer…' : phase === 'task' ? 'Ask about this step…' : 'Say or type what you need…';
  }

  function speakNew() {
    var st = S.st; if (!st) return;
    var tts = $('tts-enabled');
    (st.messages || []).forEach(function (m) {
      if (m.at <= S.spokenAt) return;
      S.spokenAt = Math.max(S.spokenAt, m.at);
      if (!S.firstLoad && m.role === 'assistant' && m.speak && tts && tts.checked && !tts.disabled) window.dispatchEvent(new CustomEvent('ghostbuild:answer', { detail: { text: m.text, from: 'assistant' } }));
    });
    S.firstLoad = false;
  }

  function send(text) {
    text = String(text || '').trim();
    if (!text || S.sending || !S.session || !S.session.id) return;
    S.sending = true;
    var phase = S.session.phase, mode = window.GBLogic ? window.GBLogic.inferMode(text) : 'build';
    var p = phase === 'task' ? post('/ask', { session_id: S.session.id, text: text }) : post('/session/goal', { v: 2, session_id: S.session.id, mode: mode, via: 'phone_text', text: text });
    p.then(function () { $('chat-input').value = ''; return refresh(); }).finally(function () { S.sending = false; });
  }

  function refresh() {
    return Promise.all([get('/assistant/state'), get('/session')]).then(function (r) {
      var changed = JSON.stringify(r[0]) !== JSON.stringify(S.st) || JSON.stringify(r[1]) !== JSON.stringify(S.session);
      S.st = r[0]; S.session = r[1];
      if (changed) { render(); speakNew(); window.dispatchEvent(new CustomEvent('ghostbuild:assistant', { detail: S.st })); }
    }).catch(function () { /* the panel simply stays as it was while core is unreachable */ });
  }
  function loop() { refresh().then(function () { setTimeout(loop, S.st && S.st.pending ? 700 : 2500); }); }

  $('chat-form').addEventListener('submit', function (ev) { ev.preventDefault(); send($('chat-input').value); });
  window.addEventListener('ghostbuild:asked', function () { refresh(); });  // app.js tells us a question was just sent
  window.GBAssistant = {
    state: function () { return S.st; },
    notesFor: function (cardId, stepId) { return ((S.st && S.st.notes) || []).filter(function (n) { return n.card_id === cardId && n.step_id === stepId; }); },
  };
  loop();
})();
