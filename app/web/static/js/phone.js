(function () {
  const role = document.body.dataset.role;
  const room = new URLSearchParams(location.search).get("room") || "demo";
  const $ = (selector) => document.querySelector(selector);
  document.querySelectorAll("[data-room]").forEach((node) => { node.textContent = room; });

  let connected = false;
  let active = false;
  let micOn = false;
  let currentState = "IDLE";
  const noticeQueue = [];
  let noticeVisible = false;
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${scheme}://${location.host}/ws/phone`);
  socket.binaryType = "arraybuffer";
  const audio = new window.EufiskyAudio(
    (frame) => { if (socket.readyState === WebSocket.OPEN && micOn) socket.send(frame); },
    (level) => { $("#meter-fill").style.width = `${Math.round(level * 100)}%`; },
  );

  function callerPhone() {
    if (role !== "caller") return undefined;
    return $("#caller-id").value === "custom" ? $("#custom-number").value.trim() : $("#caller-id").value;
  }

  function send(type, extra = {}) {
    if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type, ...extra }));
  }

  function setCopy(title, copy) {
    $("#status-title").textContent = title;
    $("#status-copy").textContent = copy;
  }

  function showNextNotice() {
    if (role !== "senior" || noticeVisible || !noticeQueue.length) return;
    const message = noticeQueue.shift();
    const ending = message.kind === "message_taken" ? "A message was saved." : "The call was declined.";
    const purpose = String(message.purpose || "No details were provided").replace(/[.!?]+$/, "");
    $("#screening-notice-copy").textContent = `A call from ${message.caller_label || "an unknown caller"} was screened. ${purpose}. ${ending}`;
    $("#screening-notice").hidden = false;
    noticeVisible = true;
    audio.notice().catch(() => {});
  }

  function dismissNotice() {
    if (role !== "senior") return;
    $("#screening-notice").hidden = true;
    noticeVisible = false;
    showNextNotice();
  }

  function renderState(message) {
    currentState = message.call_state;
    active = ["TRUSTED_ACTIVE", "BRIDGED", "FAMILY_CONF"].includes(currentState);
    if (role === "family") active = Boolean(message.family_joined);
    $("#badge").textContent = message.badge || "Ready";
    $("#badge").className = `badge ${message.monitored ? "monitored" : message.badge?.startsWith("Trusted") ? "trusted" : "neutral"}`;
    const hangup = $("#hangup");
    if (hangup) hangup.disabled = currentState === "IDLE" || currentState === "ENDED";
    if (role === "caller") {
      $("#dial").disabled = currentState !== "IDLE" && currentState !== "ENDED";
      if (currentState === "SCREENING") setCopy("Eufisky is answering", "A brief screening message is playing.");
      else if (currentState === "DIALING_SENIOR" || currentState === "RINGING_SENIOR") setCopy("Ringing Margaret…", "Waiting for Margaret to answer.");
      else if (currentState === "INTRO") setCopy("Introducing your call…", "Eufisky is connecting the line.");
      else if (currentState === "GUARDIAN" || currentState === "FAMILY_CONF") setCopy("Please hold", "Eufisky is speaking privately with Margaret.");
      else if (active) setCopy("Call connected", "You can speak now.");
    } else if (currentState === "GUARDIAN") {
      setCopy(role === "senior" ? "Eufisky is helping" : "Standing by", role === "senior" ? "The caller is safely on hold." : "Margaret is speaking privately with Eufisky.");
    } else if (active) {
      setCopy(role === "senior" ? (currentState === "FAMILY_CONF" ? "Sarah is joining" : "Call connected") : "You joined the call", currentState === "FAMILY_CONF" ? "The caller remains on hold." : "You can speak now.");
      if ($("#answer")) $("#answer").hidden = true;
      if ($("#decline")) $("#decline").hidden = true;
    } else if (role === "family" && !message.family_ringing) {
      setCopy("Standing by", "Eufisky can invite you into Margaret's call.");
      if ($("#answer")) $("#answer").hidden = true;
      if ($("#decline")) $("#decline").hidden = true;
    }
  }

  socket.addEventListener("open", () => {
    connected = true;
    send("hello", { role, room, caller_phone: callerPhone() });
  });
  socket.addEventListener("close", () => {
    connected = false;
    setCopy("Connection closed", "Refresh this page to reconnect.");
  });
  socket.addEventListener("message", async (event) => {
    if (event.data instanceof ArrayBuffer) { await audio.play(event.data); return; }
    const message = JSON.parse(event.data);
    if (message.type === "state") renderState(message);
    if (message.type === "ring") {
      $("#caption").textContent = "";
      setCopy(message.from_label, message.reason || (role === "family" ? "Margaret would like you to join." : "Incoming call"));
      $("#badge").textContent = message.trusted ? "Trusted — not monitored" : "Unknown — screened";
      $("#badge").className = `badge ${message.trusted ? "trusted" : "monitored"}`;
      if ($("#answer")) $("#answer").hidden = false;
      if ($("#decline")) $("#decline").hidden = false;
      await audio.chime();
    }
    if (message.type === "agent_say") {
      $("#caption").textContent = message.text;
      audio.speak(message.text);
    }
    if (message.type === "agent_caption") $("#caption").textContent = message.text;
    if (message.type === "notice" && role === "senior") {
      noticeQueue.push(message);
      showNextNotice();
    }
    if (message.type === "hold") {
      $("#hold").hidden = !message.on;
      if (role === "caller") {
        setCopy(message.on ? "Please hold" : "Call connected", message.on ? "Eufisky is helping Margaret." : "You can speak now.");
        audio.holdMusic(Boolean(message.on));
      }
    }
    if (message.type === "tone" && message.name === "hold_music") audio.holdMusic(true);
    if (message.type === "tone" && message.name === "hold_stop") audio.holdMusic(false);
    if (message.type === "guardian_controls" && $("#guardian-controls")) $("#guardian-controls").hidden = !message.visible;
    if (message.type === "ended") {
      active = false; currentState = "ENDED";
      $("#caption").textContent = "";
      setCopy("Call ended", message.reason || "The line is free again.");
      $("#badge").textContent = "Ready"; $("#badge").className = "badge neutral";
      if ($("#dial")) $("#dial").disabled = false;
      if ($("#hangup")) $("#hangup").disabled = true;
      if ($("#answer")) $("#answer").hidden = true;
      if ($("#decline")) $("#decline").hidden = true;
      if ($("#guardian-controls")) $("#guardian-controls").hidden = true;
      window.speechSynthesis.cancel();
      audio.holdMusic(false);
    }
    if (message.type === "ping") send("pong");
  });

  if ($("#caller-id")) $("#caller-id").addEventListener("change", () => {
    $("#custom-number").hidden = $("#caller-id").value !== "custom";
  });
  if ($("#dial")) $("#dial").addEventListener("click", () => {
    const phone = callerPhone();
    if (!connected || ($("#caller-id").value === "custom" && !phone)) return;
    send("hello", { role, room, caller_phone: phone });
    send("dial");
    setCopy("Calling…", "Eufisky is checking the number.");
  });
  if ($("#answer")) $("#answer").addEventListener("click", () => send("answer"));
  if ($("#decline")) $("#decline").addEventListener("click", () => send("hangup"));
  if ($("#hangup")) $("#hangup").addEventListener("click", () => send("hangup"));
  if ($("#dismiss-screening-notice")) $("#dismiss-screening-notice").addEventListener("click", dismissNotice);
  document.querySelectorAll("[data-guardian]").forEach((button) => button.addEventListener("click", () => send("guardian_action", { action: button.dataset.guardian })));
  $("#mic-toggle").addEventListener("click", async () => {
    try {
      if (micOn) { audio.stopMic(); micOn = false; } else { await audio.startMic(); micOn = true; }
      $("#mic-toggle").textContent = micOn ? "Mic ON" : "Mic OFF";
      $("#mic-toggle").classList.toggle("on", micOn);
      $("#mic-toggle").setAttribute("aria-pressed", String(micOn));
      send("mic", { on: micOn });
    } catch (_) { $("#caption").textContent = "Microphone access was not allowed."; }
  });
  $("#text-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = $("#text-talk");
    if (input.value.trim()) {
      window.speechSynthesis.cancel();
      send("text", { text: input.value.trim() }); input.value = "";
    }
  });
  window.addEventListener("beforeunload", () => { audio.stopMic(); audio.holdMusic(false); });
})();
