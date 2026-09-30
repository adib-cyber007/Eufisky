(function () {
  const TARGET_RATE = 16000;
  const FRAME_SAMPLES = 1600;

  class PhoneAudio {
    constructor(onFrame, onLevel) {
      this.onFrame = onFrame;
      this.onLevel = onLevel;
      this.context = null;
      this.stream = null;
      this.source = null;
      this.processor = null;
      this.pending = [];
      this.playAt = 0;
      this.playSources = new Set();
      this.holdTimer = null;
      this.resampleWeight = 0;
      this.resampleSum = 0;
      this.speechDone = null;
      this.outputGeneration = 0;
    }

    async ensureContext() {
      if (!this.context) this.context = new AudioContext({ latencyHint: "interactive" });
      if (this.context.state === "suspended") await this.context.resume();
      return this.context;
    }

    downsample(input, sourceRate) {
      if (sourceRate === TARGET_RATE) return input;
      const ratio = sourceRate / TARGET_RATE;
      const output = [];
      // Keep fractional samples across worklet blocks. Rounding each 128-sample
      // block separately loses audio and changes the speech timing/pitch.
      for (const sample of input) {
        let remaining = 1;
        while (remaining > 1e-9) {
          const weight = Math.min(remaining, ratio - this.resampleWeight);
          this.resampleSum += sample * weight;
          this.resampleWeight += weight;
          remaining -= weight;
          if (this.resampleWeight >= ratio - 1e-9) {
            output.push(this.resampleSum / ratio);
            this.resampleWeight = this.resampleSum = 0;
          }
        }
      }
      return new Float32Array(output);
    }

    consume(floatSamples, sourceRate) {
      const samples = this.downsample(floatSamples, sourceRate);
      let peak = 0;
      for (const sample of samples) peak = Math.max(peak, Math.abs(sample));
      this.onLevel(Math.min(1, peak * 2.5));

      // Web Audio playback uses the microphone's echo cancellation, so keep
      // capturing during PCM replies and human conversation (full duplex).
      // System speech isn't part of that echo reference. Send silence during
      // this fallback, preserving the STT clock instead of dropping frames.
      if (window.speechSynthesis.speaking) samples.fill(0);

      this.pending.push(...samples);
      while (this.pending.length >= FRAME_SAMPLES) {
        const frame = this.pending.splice(0, FRAME_SAMPLES);
        const pcm = new Int16Array(FRAME_SAMPLES);
        frame.forEach((sample, index) => {
          const clamped = Math.max(-1, Math.min(1, sample));
          pcm[index] = clamped < 0 ? clamped * 32768 : clamped * 32767;
        });
        this.onFrame(pcm.buffer);
      }
    }

    async startMic() {
      const context = await this.ensureContext();
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      this.source = context.createMediaStreamSource(this.stream);
      if (context.audioWorklet) {
        const code = `class Capture extends AudioWorkletProcessor { process(inputs) { const c=inputs[0]&&inputs[0][0]; if(c) this.port.postMessage(c.slice(0)); return true; } } registerProcessor('eufisky-capture', Capture);`;
        const url = URL.createObjectURL(new Blob([code], { type: "text/javascript" }));
        await context.audioWorklet.addModule(url);
        URL.revokeObjectURL(url);
        this.processor = new AudioWorkletNode(context, "eufisky-capture");
        this.processor.port.onmessage = (event) => this.consume(event.data, context.sampleRate);
      } else {
        this.processor = context.createScriptProcessor(2048, 1, 1);
        this.processor.onaudioprocess = (event) => this.consume(event.inputBuffer.getChannelData(0), context.sampleRate);
      }
      const mute = context.createGain();
      mute.gain.value = 0;
      this.source.connect(this.processor);
      this.processor.connect(mute);
      mute.connect(context.destination);
    }

    stopMic() {
      if (this.source) this.source.disconnect();
      if (this.processor) this.processor.disconnect();
      if (this.stream) this.stream.getTracks().forEach((track) => track.stop());
      this.stream = this.source = this.processor = null;
      this.pending = [];
      this.resampleWeight = this.resampleSum = 0;
      this.onLevel(0);
    }

    async play(arrayBuffer) {
      const generation = this.outputGeneration;
      const context = await this.ensureContext();
      if (generation !== this.outputGeneration) return;
      this.cancelSpeech();
      const pcm = new Int16Array(arrayBuffer);
      const audio = context.createBuffer(1, pcm.length, TARGET_RATE);
      const channel = audio.getChannelData(0);
      for (let i = 0; i < pcm.length; i += 1) channel[i] = pcm[i] / 32768;
      const source = context.createBufferSource();
      this.playSources.add(source);
      source.addEventListener("ended", () => this.playSources.delete(source), { once: true });
      source.buffer = audio;
      source.connect(context.destination);
      const now = context.currentTime;
      // Buffer 80 ms only on an empty queue. Adding a safety gap to every
      // chunk inserts audible breaks when packets arrive around playback time.
      if (this.playAt <= now) this.playAt = now + 0.08;
      source.start(this.playAt);
      this.playAt += audio.duration;
    }

    stopPcm() {
      this.outputGeneration += 1;
      this.playSources.forEach((source) => {
        try { source.stop(); } catch (_) { /* already stopped */ }
      });
      this.playSources.clear();
      this.playAt = this.context ? this.context.currentTime : 0;
    }

    resetOutput() {
      this.cancelSpeech();
      this.stopPcm();
    }

    cancelSpeech() {
      if (this.speechDone) this.speechDone(false);
      window.speechSynthesis.cancel();
    }

    preferredGuardianVoice() {
      const preferredNames = [
        "microsoft aria", "microsoft zira", "microsoft hazel", "samantha",
        "victoria", "karen", "moira", "tessa", "google uk english female",
      ];
      const voices = window.speechSynthesis.getVoices();
      return voices.find((voice) => {
        const name = voice.name.toLowerCase();
        return voice.lang.toLowerCase().startsWith("en")
          && (name.includes("female") || preferredNames.some((candidate) => name.includes(candidate)));
      }) || null;
    }

    speak(text) {
      const options = arguments[1] || {};
      this.stopPcm();
      this.cancelSpeech();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = options.confidenceFriendly ? 0.82 : 0.93;
      utterance.pitch = 1;
      if (options.confidenceFriendly) {
        const voice = this.preferredGuardianVoice();
        if (voice) utterance.voice = voice;
      }
      return new Promise((resolve) => {
        const finish = (completed) => {
          if (this.speechDone !== finish) return;
          this.speechDone = null;
          resolve(completed);
        };
        this.speechDone = finish;
        utterance.onend = () => finish(true);
        utterance.onerror = () => finish(false);
        window.speechSynthesis.speak(utterance);
      });
    }

    destroy() {
      this.stopMic();
      this.holdMusic(false);
      this.resetOutput();
    }

    async chime() {
      const context = await this.ensureContext();
      [0, 0.18].forEach((offset, index) => {
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.frequency.value = index ? 660 : 523;
        gain.gain.setValueAtTime(0.0001, context.currentTime + offset);
        gain.gain.exponentialRampToValueAtTime(0.14, context.currentTime + offset + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + offset + 0.17);
        oscillator.connect(gain).connect(context.destination);
        oscillator.start(context.currentTime + offset);
        oscillator.stop(context.currentTime + offset + 0.18);
      });
    }

    async notice() {
      const context = await this.ensureContext();
      [440, 554].forEach((frequency, index) => {
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        const start = context.currentTime + index * 0.13;
        oscillator.frequency.value = frequency;
        oscillator.type = "sine";
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.045, start + 0.025);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.12);
        oscillator.connect(gain).connect(context.destination);
        oscillator.start(start);
        oscillator.stop(start + 0.13);
      });
    }

    async holdMusic(on) {
      if (!on) {
        if (this.holdTimer) clearInterval(this.holdTimer);
        this.holdTimer = null;
        return;
      }
      if (this.holdTimer) return;
      const playPhrase = async () => {
        const context = await this.ensureContext();
        [392, 494, 587, 494].forEach((frequency, index) => {
          const oscillator = context.createOscillator();
          const gain = context.createGain();
          const start = context.currentTime + index * 0.32;
          oscillator.frequency.value = frequency;
          oscillator.type = "sine";
          gain.gain.setValueAtTime(0.0001, start);
          gain.gain.exponentialRampToValueAtTime(0.045, start + 0.03);
          gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.28);
          oscillator.connect(gain).connect(context.destination);
          oscillator.start(start); oscillator.stop(start + 0.3);
        });
      };
      await playPhrase();
      this.holdTimer = setInterval(playPhrase, 2400);
    }
  }

  window.EufiskyAudio = PhoneAudio;
})();
