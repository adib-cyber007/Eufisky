// Run with node --test tests/audio.test.cjs; no browser or packages required.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { runInNewContext } = require("node:vm");

function setup() {
  const speech = { speaking: false, cancel() {}, speak(utterance) { this.utterance = utterance; } };
  const window = { speechSynthesis: speech };
  runInNewContext(readFileSync("app/web/static/js/audio.js", "utf8"), {
    window, SpeechSynthesisUtterance: function(text) { this.text = text; },
  });
  const frames = [];
  const audio = new window.EufiskyAudio((frame) => frames.push(new Int16Array(frame)), () => {});
  return { audio, frames, speech };
}

test("128-sample worklet blocks preserve duration and waveform at 44.1 and 48 kHz", () => {
  for (const rate of [44100, 48000]) {
    const signal = Float32Array.from({ length: rate }, (_, i) => 0.4 * Math.sin(2 * Math.PI * 440 * i / rate));
    const { audio, frames } = setup();
    for (let i = 0; i < signal.length; i += 128) audio.consume(signal.subarray(i, i + 128), rate);
    assert.equal(frames.length, 10); // exactly one second, not 9 frames + a missing tail
    assert.equal(audio.pending.length, 0);
    const contiguous = setup().audio.downsample(signal, rate);
    const actual = frames.flatMap((frame) => Array.from(frame));
    assert.equal(contiguous.length, 16000);
    actual.forEach((sample, i) => assert.ok(Math.abs(sample / 32768 - contiguous[i]) < 0.0001));
  }
});

test("PCM playback doesn't discard microphone words; system speech sends clocked silence", () => {
  const { audio, frames, speech } = setup();
  audio.context = { currentTime: 0 };
  audio.playAt = 10;
  audio.consume(new Float32Array(1600).fill(0.5), 16000);
  assert.equal(frames.length, 1);
  assert.ok(frames[0].every((sample) => sample > 16000));
  speech.speaking = true;
  audio.consume(new Float32Array(1600).fill(0.5), 16000);
  assert.equal(frames.length, 2);
  assert.ok(frames[1].every((sample) => sample === 0));
});

test("playback chunks stay contiguous and a reset cancels pending async playback", async () => {
  const { audio } = setup();
  const sources = [];
  const context = {
    currentTime: 0, destination: {},
    createBuffer(channels, length, rate) { return { duration: length / rate, getChannelData: () => new Float32Array(length) }; },
    createBufferSource() {
      const source = { connect() {}, addEventListener() {}, start(time) { this.at = time; }, stop() { this.stopped = true; } };
      sources.push(source);
      return source;
    },
  };
  audio.context = context;
  audio.ensureContext = async () => context;
  await audio.play(new Int16Array(1600).buffer);
  context.currentTime = 0.17;
  await audio.play(new Int16Array(1600).buffer);
  assert.equal(sources[0].at, 0.08);
  assert.ok(Math.abs(sources[1].at - 0.18) < 1e-9);
  let resume;
  audio.ensureContext = () => new Promise((resolve) => { resume = resolve; });
  const pending = audio.play(new Int16Array(1600).buffer);
  audio.resetOutput();
  resume(context);
  await pending;
  assert.equal(sources.length, 2);
  assert.ok(sources.every((source) => source.stopped));
});

test("closing speech reports completion only after its last word", async () => {
  const { audio, speech } = setup();
  const finished = audio.speak("Thank you. Goodbye.");
  let completed = false;
  finished.then(() => { completed = true; });
  await Promise.resolve();
  assert.equal(completed, false);
  speech.utterance.onend();
  assert.equal(await finished, true);
  const cancelled = audio.speak("Another message");
  audio.resetOutput();
  assert.equal(await cancelled, false);
});
