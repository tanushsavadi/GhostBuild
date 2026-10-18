/* Optional phone PTT + ElevenLabs spoken replies. Explicit consent, foreground only, no recording storage. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  if (!$('ptt')) return;
  var core = (new URLSearchParams(location.search).get('core') || '').replace(/\/+$/, '');
  var phase = 'idle', generation = 0, stream = null, context = null, processor = null, socket = null;
  var cap = null, replyTimer = null, startupTimer = null, setupAbort = null, player = null, audioUrl = null, speechFetch = null, speechGeneration = 0;
  var available = {stt:false,tts:false}, bytesSent = 0;
  var text = function (s) { $('voice-status').textContent = s; };
  function refresh() {
    var secureMic = !!(window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    $('ptt').disabled = (!available.stt || !secureMic || !$('voice-consent').checked) && phase === 'idle';
    $('ptt').textContent = phase === 'listening' ? 'Stop & send' : phase === 'starting' ? 'Cancel microphone request' : phase === 'thinking' ? 'Cancel transcription' : 'Start talking';
    $('ptt').classList.toggle('listening', phase === 'listening');
    $('audio-badge').textContent = phase === 'idle' ? ($('tts-enabled').checked ? 'Replies on' : 'Off') : phase === 'thinking' ? 'Thinking' : phase === 'starting' ? 'Opening mic' : 'Listening';
    $('tts-enabled').disabled = !available.tts;
  }
  function stopPlayback() {
    speechGeneration++;
    if (speechFetch) speechFetch.abort(); speechFetch = null;
    if (player) { player.pause(); player.src = ''; player = null; }
    if (audioUrl) URL.revokeObjectURL(audioUrl); audioUrl = null;
  }
  function closeMic() {
    if (startupTimer) clearTimeout(startupTimer); startupTimer = null;
    if (setupAbort) setupAbort.abort(); setupAbort = null;
    if (cap) clearTimeout(cap); cap = null;
    if (processor) { processor.onaudioprocess = null; try { processor.disconnect(); } catch (_) {} processor = null; }
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); }); stream = null;
    if (context) { var old = context; context = null; old.close().catch(function () {}); }
  }
  function closeSocket() {
    if (replyTimer) clearTimeout(replyTimer); replyTimer = null;
    if (socket) { var old = socket; socket = null; old.onopen = old.onmessage = old.onclose = old.onerror = null; old.close(); }
  }
  function abort(reason) {
    generation++; closeMic();
    if (socket && socket.readyState === 1) socket.send(JSON.stringify({type:'abort',reason:reason || 'user_cancel'}));
    closeSocket(); phase = 'idle'; refresh();
  }
  async function start() {
    if (phase !== 'idle' || !$('voice-consent').checked || !available.stt) return;
    stopPlayback(); phase = 'starting'; var gen = ++generation; bytesSent = 0; refresh();
    startupTimer = setTimeout(function () { if (gen === generation) { abort('startup_timeout'); text('Microphone setup timed out. Use text or try again.'); } },12000);
    text('Opening microphone. Audio goes to ElevenLabs only for this turn.');
    try {
      var mic = await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true},video:false});
      if (gen !== generation) { mic.getTracks().forEach(function (t) { t.stop(); }); return; }
      stream = mic;
      context = new (window.AudioContext || window.webkitAudioContext)({sampleRate:16000});
      await context.resume(); if (gen !== generation) return;
      setupAbort = new AbortController();
      var session = await fetch(core + '/session', {cache:'no-store',signal:setupAbort.signal}).then(function (r) { if (!r.ok) throw new Error(); return r.json(); });
      if (gen !== generation) return;
      var endpoint = new URL(core + '/ws/voice', location.origin); endpoint.protocol = endpoint.protocol === 'https:' ? 'wss:' : 'ws:';
      endpoint.searchParams.set('session_id', session.id);
      socket = new WebSocket(endpoint.href); var ws = socket;
      var openTimer = setTimeout(function () { if (socket === ws) { abort('socket_timeout'); text('Voice connection timed out. Use text or touch.'); } }, 6000);
      ws.onopen = function () {
        clearTimeout(openTimer); if (gen !== generation || socket !== ws) return;
        if (startupTimer) clearTimeout(startupTimer); startupTimer = null;
        ws.send(JSON.stringify({type:'start',consent:true}));
        var source = context.createMediaStreamSource(stream), gain = context.createGain(); gain.gain.value = 0;
        processor = context.createScriptProcessor(2048,1,1);
        processor.onaudioprocess = function (e) {
          if (phase !== 'listening' || socket !== ws || ws.readyState !== 1) return;
          if (ws.bufferedAmount > 128000) { abort('network_backpressure'); text('Audio connection is too slow. Use text.'); return; }
          var pcm = window.GBAudio.pcm16(e.inputBuffer.getChannelData(0), context.sampleRate);
          bytesSent += pcm.length; ws.send(pcm);
        };
        source.connect(processor); processor.connect(gain); gain.connect(context.destination);
        phase = 'listening'; text('Listening · tap Stop & send when done. Maximum 10 seconds.'); refresh(); cap = setTimeout(finish,10000);
      };
      ws.onmessage = function (e) {
        if (gen !== generation || socket !== ws) return;
        var ev; try { ev = JSON.parse(e.data); } catch (_) { return; }
        if (ev.type === 'done') {
          closeMic(); closeSocket(); phase = 'idle'; refresh();
          text(ev.ignored ? 'Task changed while you spoke. Please ask again.' : ev.transcript ? 'You said: “' + ev.transcript + '”' : 'No speech detected. Try again or type your question.');
          if (ev.text && !ev.ignored) {
            window.dispatchEvent(new CustomEvent('ghostbuild:voice-result',{detail:ev}));
            window.dispatchEvent(new CustomEvent('ghostbuild:answer',{detail:{text:ev.text}}));
          }
        } else if (ev.type === 'unavailable' || ev.type === 'consent_required' || ev.type === 'busy') {
          abort('provider_unavailable'); text('Voice unavailable. Your guide still works with touch and text.');
        }
      };
      ws.onclose = ws.onerror = function () { clearTimeout(openTimer); if (socket === ws) { abort('connection_lost'); text('Voice connection lost. Use text or touch.'); } };
    } catch (_) { if (gen === generation) { abort('microphone_failed'); text('Microphone unavailable or permission denied. Use text or touch.'); } }
  }
  function finish() {
    if (phase !== 'listening') return;
    closeMic();
    if (!socket || socket.readyState !== 1 || bytesSent === 0) { abort('empty_audio'); text('No audio received. Try again or type.'); return; }
    socket.send(JSON.stringify({type:'end'})); phase = 'thinking'; text('Thinking · tap Cancel to stop.'); refresh();
    replyTimer = setTimeout(function () { abort('reply_timeout'); text('Voice timed out. Please use text or try again.'); },12000);
  }
  // Full answers are spoken in sentence-sized parts (the backend takes <=500 chars per request), at most 4 parts;
  // any new input, mute, or a newer answer bumps speechGeneration and stops the rest.
  function speechParts(s) {
    var t = String(s || '').replace(/\s+/g,' ').trim(), out = [];
    while (t && out.length < 4) {
      if (t.length <= 480) { out.push(t); break; }
      var cut = t.lastIndexOf('. ',480); if (cut < 160) cut = t.lastIndexOf(' ',480); if (cut < 1) cut = 479;
      out.push(t.slice(0,cut + 1).trim()); t = t.slice(cut + 1).trim();
    }
    return out;
  }
  function releasePlayer() {
    if (player) { player.pause(); player.src = ''; player = null; }
    if (audioUrl) URL.revokeObjectURL(audioUrl); audioUrl = null;
  }
  async function speakPart(part, gen) {
    speechFetch = new AbortController();
    var timer = setTimeout(function () { if (gen === speechGeneration && speechFetch) speechFetch.abort(); },12000);
    try {
      var response = await fetch(core + '/voice/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:part,consent:true}),signal:speechFetch.signal});
      if (!response.ok) throw new Error();
      var blob = await response.blob(); if (gen !== speechGeneration || !$('tts-enabled').checked) return false;
      audioUrl = URL.createObjectURL(blob); player = new Audio(audioUrl); player.volume = Number($('tts-volume').value);
      var ended = new Promise(function (resolve) { player.onended = resolve; player.onerror = resolve; });
      await player.play(); await ended;
      if (gen !== speechGeneration) return false;
      releasePlayer(); return true;
    } catch (_) { if (gen === speechGeneration) text('Spoken reply unavailable or blocked by browser. Read the answer above.'); return false; }
    finally { clearTimeout(timer); }
  }
  async function speak(s) {
    if (!$('tts-enabled').checked || !available.tts || phase !== 'idle' || !s) return;
    stopPlayback(); var gen = speechGeneration, parts = speechParts(s);
    for (var i = 0; i < parts.length; i++) {
      if (gen !== speechGeneration || !$('tts-enabled').checked) return;
      if (!(await speakPart(parts[i], gen))) return;
    }
  }
  $('ptt').addEventListener('click',function () { if (phase === 'idle') start(); else if (phase === 'listening') finish(); else { abort('user_cancel'); text('Microphone off.'); } });
  $('voice-consent').addEventListener('change',function () { if (!$('voice-consent').checked) { abort('consent_revoked'); text('Microphone off.'); } refresh(); });
  $('tts-enabled').addEventListener('change',function () { if (!$('tts-enabled').checked) stopPlayback(); refresh(); });
  $('tts-volume').addEventListener('input',function () { if (player) player.volume = Number(this.value); if (Number(this.value) === 0) stopPlayback(); });
  $('audio-stop').addEventListener('click',function () { abort('user_mute'); stopPlayback(); $('voice-consent').checked = false; $('tts-enabled').checked = false; refresh(); text('Audio off. Continue with text or touch.'); });
  window.addEventListener('ghostbuild:input',function () { stopPlayback(); if (phase !== 'idle') abort('text_input'); });
  window.addEventListener('ghostbuild:answer',function (e) { speak(e.detail && e.detail.text); });
  document.addEventListener('visibilitychange',function () { if (document.hidden) { abort('background'); stopPlayback(); } });
  window.addEventListener('pagehide',function () { abort('exit'); stopPlayback(); });
  if (new URLSearchParams(location.search).has('fixture')) { text('Fixture preview. Voice is off.'); refresh(); return; }
  fetch(core + '/voice/status',{cache:'no-store'}).then(function (r) {return r.json();}).then(function (v) {
    available = v; refresh();
    text(!v.stt ? 'Voice is off on the backend. Touch and text are ready.' : !window.isSecureContext ? 'Phone microphone needs HTTPS. Use G2 hold-to-talk or text here.' : 'Audio is off. Enable consent to talk; spoken replies are optional.');
  }).catch(function () { text('Optional voice unavailable. Touch and text still work.'); refresh(); });
  refresh();
})();
