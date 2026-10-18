/* PCM conversion only. No recording or network state. */
(function (root) {
  'use strict';
  function pcm16(samples, inputRate) {
    if (!samples || !samples.length || !Number.isFinite(inputRate) || inputRate < 16000) return new Uint8Array(0);
    var ratio = inputRate / 16000, count = Math.floor(samples.length / ratio);
    var out = new Uint8Array(count * 2), view = new DataView(out.buffer);
    for (var i = 0; i < count; i++) {
      var start = Math.floor(i * ratio), end = Math.min(samples.length, Math.floor((i + 1) * ratio)), sum = 0;
      for (var j = start; j < end; j++) sum += Number.isFinite(samples[j]) ? samples[j] : 0;
      var value = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)));
      view.setInt16(i * 2, value < 0 ? value * 32768 : value * 32767, true);
    }
    return out;
  }
  root.GBAudio = { pcm16: pcm16 };
})(typeof window !== 'undefined' ? window : globalThis);
