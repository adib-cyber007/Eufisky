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
    }

    async ensureContext() {
      if (!this.context) this.context = new AudioContext({ latencyHint: "interactive" });
      if (this.context.state === "suspended") await this.context.resume();
      return this.context;
    }

    downsample(input, sourceRate) {
      if (sourceRate === TARGET_RATE) return input;
      const ratio = sourceRate / TARGET_RATE;
      const length = Math.floor(input.length / ratio);
      const output = new Float32Array(length);
      for (let i = 0; i < length; i += 1) {
        const start = Math.floor(i * ratio);
        const end = Math.max(start + 1, Math.floor((i + 1) * ratio));
        let sum = 0;
        for (let j = start; j < end && j < input.length; j += 1) sum += input[j];
        output[i] = sum / (end - start);
      }
      return output;
    }

    consume(floatSamples, sourceRate) {
      const samples = this.downsample(floatSamples, sourceRate);
      this.pending.push(...samples);
      let peak = 0;
      for (const sample of samples) peak = Math.max(peak, Math.abs(sample));
      if (peak > 0.08 && window.speechSynthesis.speaking) window.speechSynthesis.cancel();
      this.onLevel(Math.min(1, peak * 2.5));
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
      this.onLevel(0);
    }

    async play(arrayBuffer) {
      window.speechSynthesis.cancel();
      const context = await this.ensureContext();
      const pcm = new Int16Array(arrayBuffer);
      const audio = context.createBuffer(1, pcm.length, TARGET_RATE);
      const channel = audio.getChannelData(0);
      for (let i = 0; i < pcm.length; i += 1) channel[i] = pcm[i] / 32768;
      const source = context.createBufferSource();
      source.buffer = audio;
      source.connect(context.destination);
      const now = context.currentTime;
      this.playAt = Math.max(now + 0.015, this.playAt);
      source.start(this.playAt);
      this.playAt += audio.duration;
    }

    speak(text) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.93;
      utterance.pitch = 1;
      window.speechSynthesis.speak(utterance);
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
  }

  window.EufiskyAudio = PhoneAudio;
})();
