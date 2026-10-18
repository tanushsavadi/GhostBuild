/** Browser lifecycle fakes only: no microphone, live provider, or physical G2 evidence. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import test from 'node:test';
import vm from 'node:vm';

const root = process.env.GB_AUDIO_ROOT || path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const sources = ['audio-utils.js', 'audio.js'].map(name => [name, readFileSync(path.join(root, 'web', name), 'utf8')]);
const flush = () => new Promise(resolve => setImmediate(resolve));
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => {resolve = yes; reject = no;});
  return {promise, resolve, reject};
}
class Events {
  constructor() {this.listeners = new Map();}
  addEventListener(type, listener) {
    const list = this.listeners.get(type) || [];
    list.push(listener); this.listeners.set(type, list);
  }
  dispatchEvent(event) {
    for (const listener of this.listeners.get(event.type) || []) listener.call(this, event);
    return true;
  }
  emit(type, detail) {this.dispatchEvent({type, detail});}
}

async function browser({permissionPending = false, sessionPending = false} = {}) {
  const elements = Object.fromEntries(['ptt', 'voice-status', 'voice-consent', 'tts-enabled', 'tts-volume', 'audio-stop', 'audio-badge'].map(id => {
    const element = new Events();
    Object.assign(element, {checked:false, disabled:false, textContent:'', value:'0.8', classList:{toggle(){}}});
    return [id, element];
  }));
  const document = Object.assign(new Events(), {hidden:false, getElementById:id => elements[id]});
  const window = Object.assign(new Events(), {isSecureContext:true});
  const permission = deferred(), session = deferred();
  const track = {stops:0, stop() {this.stops++;}};
  const stream = {getTracks:() => [track]};
  const calls = [], sockets = [], contexts = [], timers = new Map();
  let now = 0, timerId = 0, micCalls = 0;
  class FakeSocket {
    constructor(url) {this.url = url; this.readyState = 0; this.bufferedAmount = 0; this.sent = []; this.closes = 0; sockets.push(this);}
    open() {this.readyState = 1; this.onopen?.({});}
    send(message) {assert.equal(this.readyState, 1); this.sent.push(message);}
    close() {this.closes++; this.readyState = 3;}
    message(value) {this.onmessage?.({data:JSON.stringify(value)});}
    controls() {return this.sent.filter(value => typeof value === 'string').map(value => JSON.parse(value));}
  }
  class FakeContext {
    constructor() {this.sampleRate = 16000; this.destination = {}; this.closed = 0; this.processors = []; contexts.push(this);}
    resume() {return Promise.resolve();}
    close() {this.closed++; return Promise.resolve();}
    createMediaStreamSource(actualStream) {assert.equal(actualStream, stream); return {connect(){}};}
    createGain() {return {gain:{value:1}, connect(){}};}
    createScriptProcessor() {
      const processor = {onaudioprocess:null, disconnected:0, connect(){}, disconnect(){this.disconnected++;}};
      this.processors.push(processor); return processor;
    }
  }
  window.AudioContext = FakeContext;
  const sandbox = {
    window, document, location:{search:'', origin:'https://phone.test'}, URL, URLSearchParams,
    AbortController, Uint8Array, DataView, Number, JSON,
    CustomEvent:class {constructor(type, init = {}) {this.type = type; this.detail = init.detail;}},
    WebSocket:FakeSocket,
    navigator:{mediaDevices:{getUserMedia() {micCalls++; return permissionPending ? permission.promise : Promise.resolve(stream);}}},
    setTimeout(callback, delay) {const id = ++timerId; timers.set(id, {callback, at:now + delay}); return id;},
    clearTimeout(id) {timers.delete(id);},
    fetch(url, options = {}) {
      calls.push({url, options});
      if (url.endsWith('/voice/status')) return Promise.resolve({ok:true, json:async () => ({stt:true, tts:false})});
      if (url.endsWith('/session')) {
        if (!sessionPending) return Promise.resolve({ok:true, json:async () => ({id:'session-test'})});
        options.signal.addEventListener('abort', () => session.reject(new Error('aborted')), {once:true});
        return session.promise;
      }
      throw new Error('Unexpected network request in lifecycle fake: ' + url);
    },
  };
  const scope = vm.createContext(sandbox);
  for (const [filename, source] of sources) vm.runInContext(source, scope, {filename});
  await flush();
  async function advance(ms) {
    const target = now + ms;
    while (true) {
      const due = [...timers.entries()].filter(([, timer]) => timer.at <= target).sort((a, b) => a[1].at - b[1].at)[0];
      if (!due) break;
      now = due[1].at; timers.delete(due[0]); due[1].callback(); await flush();
    }
    now = target; await flush();
  }
  async function start() {
    elements['voice-consent'].checked = true; elements['voice-consent'].emit('change');
    elements.ptt.emit('click'); await flush();
  }
  async function listen() {
    await start(); assert.equal(sockets.length, 1); sockets[0].open(); await flush();
    assert.equal(elements['audio-badge'].textContent, 'Listening');
  }
  function feed(samples = new Float32Array(2048).fill(0.25)) {
    contexts.at(-1).processors.at(-1).onaudioprocess({inputBuffer:{getChannelData:() => samples}});
  }
  return {elements, document, window, permission, stream, track, calls, sockets, contexts, timers, advance, start, listen, feed,
    micCalls:() => micCalls, pcm16:window.GBAudio.pcm16};
}

test('no consent never opens the microphone or speech socket', async () => {
  const b = await browser();
  assert.equal(b.elements.ptt.disabled, true);
  b.elements.ptt.emit('click'); await flush();
  assert.equal(b.micCalls(), 0); assert.equal(b.sockets.length, 0);
  assert.equal(b.calls.length, 1); // capability check only
});

test('hung session lookup closes the microphone and cancels setup at twelve seconds', async () => {
  const b = await browser({sessionPending:true}); await b.start();
  assert.equal(b.micCalls(), 1); assert.equal(b.track.stops, 0);
  await b.advance(11999); assert.equal(b.track.stops, 0);
  await b.advance(1);
  assert.equal(b.track.stops, 1); assert.equal(b.contexts[0].closed, 1);
  assert.equal(b.calls.find(call => call.url.endsWith('/session')).options.signal.aborted, true);
  assert.equal(b.sockets.length, 0); assert.equal(b.timers.size, 0);
  assert.match(b.elements['voice-status'].textContent, /timed out/i);
  assert.equal(b.elements.ptt.textContent, 'Start talking');
});

test('permission granted after cancellation immediately stops its late microphone track', async () => {
  const b = await browser({permissionPending:true}); await b.start();
  b.elements.ptt.emit('click'); // cancel while permission prompt remains unresolved
  b.permission.resolve(b.stream); await flush();
  assert.equal(b.track.stops, 1); assert.equal(b.contexts.length, 0);
  assert.equal(b.sockets.length, 0); assert.equal(b.timers.size, 0);
  assert.equal(b.elements['audio-badge'].textContent, 'Off');
});

test('backgrounding closes capture, audio context and socket with an explicit abort', async () => {
  const b = await browser(); await b.listen(); b.feed();
  const ws = b.sockets[0], processor = b.contexts[0].processors[0];
  assert.deepEqual(ws.controls(), [{type:'start', consent:true}]);
  b.document.hidden = true; b.document.emit('visibilitychange'); await flush();
  assert.equal(b.track.stops, 1); assert.equal(b.contexts[0].closed, 1);
  assert.equal(processor.disconnected, 1); assert.equal(processor.onaudioprocess, null);
  assert.equal(ws.closes, 1); assert.deepEqual(ws.controls().at(-1), {type:'abort', reason:'background'});
  assert.equal(b.timers.size, 0); assert.equal(b.elements.ptt.textContent, 'Start talking');
});

test('text input cancels pending transcription and ignores a late provider result', async () => {
  const b = await browser(); await b.listen(); b.feed();
  const ws = b.sockets[0], lateMessage = ws.onmessage, results = [];
  b.window.addEventListener('ghostbuild:voice-result', event => results.push(event.detail));
  b.elements.ptt.emit('click'); // stop and send; socket must remain open for final result
  assert.equal(b.track.stops, 1); assert.equal(ws.closes, 0);
  assert.deepEqual(ws.controls().at(-1), {type:'end'});
  assert.equal(b.elements['audio-badge'].textContent, 'Thinking');
  b.window.emit('ghostbuild:input');
  assert.deepEqual(ws.controls().at(-1), {type:'abort', reason:'text_input'});
  assert.equal(ws.closes, 1); assert.equal(b.timers.size, 0);
  lateMessage({data:JSON.stringify({type:'done', transcript:'done', text:'late answer', ignored:false})});
  assert.deepEqual(results, []); assert.equal(b.elements['audio-badge'].textContent, 'Off');
});

test('consent revocation stops an already active microphone', async () => {
  const b = await browser(); await b.listen();
  b.elements['voice-consent'].checked = false; b.elements['voice-consent'].emit('change');
  assert.equal(b.track.stops, 1); assert.equal(b.sockets[0].closes, 1);
  assert.equal(b.elements.ptt.disabled, true);
  assert.deepEqual(b.sockets[0].controls().at(-1), {type:'abort', reason:'consent_revoked'});
});

test('completed PTT sends PCM16, stops capture and publishes the actual documented phone answer', async () => {
  const b = await browser(), results = [];
  b.window.addEventListener('ghostbuild:voice-result', event => results.push(event.detail));
  await b.listen(); b.feed();
  const ws = b.sockets[0];
  const pcm = ws.sent.find(value => typeof value !== 'string');
  assert.equal(pcm.byteLength, 4096);
  assert.equal(new DataView(pcm.buffer).getInt16(0, true), 8191);
  b.elements.ptt.emit('click');
  ws.message({type:'done', origin:'fake_test', transcript:'why?', text:'Documented current step', ignored:false});
  assert.equal(ws.closes, 1); assert.equal(b.track.stops, 1); assert.equal(b.timers.size, 0);
  assert.equal(results.length, 1); assert.equal(results[0].text, 'Documented current step');
  assert.equal(results[0].origin, 'fake_test'); // local fixture never claims live speech
});

test('empty capture never sends an end command and provider failure restores touch/text state', async () => {
  const b = await browser(); await b.listen();
  b.elements.ptt.emit('click');
  assert.equal(b.sockets[0].controls().some(control => control.type === 'end'), false);
  assert.equal(b.track.stops, 1); assert.match(b.elements['voice-status'].textContent, /no audio/i);
  const c = await browser(); await c.listen();
  c.sockets[0].message({type:'unavailable'});
  assert.equal(c.track.stops, 1); assert.equal(c.sockets[0].closes, 1);
  assert.equal(c.elements.ptt.textContent, 'Start talking');
  assert.match(c.elements['voice-status'].textContent, /touch and text/i);
});

test('PCM conversion clamps finite values, writes little endian, resamples and rejects invalid rates', async () => {
  const b = await browser();
  function decode(bytes) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    return Array.from({length:bytes.length / 2}, (_, i) => view.getInt16(i * 2, true));
  }
  assert.deepEqual(decode(b.pcm16(new Float32Array([-2, -1, -0.5, 0, 0.5, 1, 2, NaN]), 16000)), [-32768, -32768, -16384, 0, 16383, 32767, 32767, 0]);
  assert.deepEqual(decode(b.pcm16(new Float32Array([1, 1, 1, -1, -1, -1]), 48000)), [32767, -32768]);
  assert.equal(b.pcm16(new Float32Array(441), 44100).length, 320);
  for (const rate of [8000, NaN, Infinity, 0]) assert.equal(b.pcm16(new Float32Array([1]), rate).length, 0);
});
