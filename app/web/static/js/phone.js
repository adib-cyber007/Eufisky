(function () {
  const role = document.body.dataset.role;
  const room = new URLSearchParams(location.search).get("room") || "demo";
  const $ = (selector) => document.querySelector(selector);
  document.querySelectorAll("[data-room]").forEach((node) => { node.textContent = room; });

  let connected = false;
  let active = false;
  let micOn = false;
  let currentState = "IDLE";
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

  function renderState(message) {
    currentState = message.call_state;
    active = ["TRUSTED_ACTIVE", "BRIDGED"].includes(currentState);
    $("#badge").textContent = message.badge || "Ready";
    $("#badge").className = `badge ${message.monitored ? "monitored" : message.badge?.startsWith("Trusted") ? "trusted" : "neutral"}`;
    const hangup = $("#hangup");
    if (hangup) hangup.disabled = currentState === "IDLE" || currentState === "ENDED";
    if (role === "caller") {
      $("#dial").disabled = currentState !== "IDLE" && currentState !== "ENDED";
      if (currentState === "SCREENING") setCopy("Eufisky is answering", "A brief screening message is playing.");
      else if (currentState === "RINGING_SENIOR") setCopy("Ringing Margaret…", "Waiting for Margaret to answer.");
      else if (active) setCopy("Call connected", "You can speak now.");
    } else if (active) {
      setCopy(role === "senior" ? "Call connected" : "You joined the call", "You can speak now.");
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
      setCopy(message.from_label, role === "family" ? "Margaret would like you to join." : "Incoming call");
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
    if (message.type === "hold") $("#hold").hidden = !message.on;
    if (message.type === "ended") {
      active = false; currentState = "ENDED";
      $("#caption").textContent = "";
      setCopy("Call ended", message.reason || "The line is free again.");
      $("#badge").textContent = "Ready"; $("#badge").className = "badge neutral";
      if ($("#dial")) $("#dial").disabled = false;
      if ($("#hangup")) $("#hangup").disabled = true;
      if ($("#answer")) $("#answer").hidden = true;
      if ($("#decline")) $("#decline").hidden = true;
      window.speechSynthesis.cancel();
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
    if (input.value.trim()) { send("text", { text: input.value.trim() }); input.value = ""; }
  });
  window.addEventListener("beforeunload", () => audio.stopMic());
})();
