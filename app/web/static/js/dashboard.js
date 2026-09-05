(function () {
  const room = new URLSearchParams(location.search).get("room") || "demo";
  const $ = (selector) => document.querySelector(selector);
  const seenTranscript = new Set();
  let lastBubble = null;
  let currentCallId = null;
  document.querySelectorAll("[data-room]").forEach((node) => { node.textContent = room; });

  document.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll("[data-tab]").forEach((item) => item.classList.toggle("active", item === button));
    document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `panel-${button.dataset.tab}`));
    if (button.dataset.tab === "contacts") loadContacts();
    if (button.dataset.tab === "messages") loadMessages();
    if (button.dataset.tab === "history") loadHistory();
  }));

  async function request(path, options = {}) {
    const response = await fetch(`/api/rooms/${encodeURIComponent(room)}${path}`, {
      headers: { "Content-Type": "application/json" }, ...options,
    });
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    return response.status === 204 ? null : response.json();
  }

  function contactRow(contact) {
    const row = document.createElement("article");
    row.className = "data-row";
    row.innerHTML = `<div><strong></strong><span></span></div><div class="row-actions"><button data-status="trusted">Trust</button><button data-status="blocked">Block</button><button data-delete>Delete</button></div>`;
    row.querySelector("strong").textContent = contact.label;
    row.querySelector("span").textContent = `${contact.phone} · ${contact.status}`;
    row.querySelectorAll("[data-status]").forEach((button) => button.addEventListener("click", async () => {
      await request(`/contacts/${contact.id}`, { method: "PATCH", body: JSON.stringify({ status: button.dataset.status }) });
      loadContacts();
    }));
    row.querySelector("[data-delete]").addEventListener("click", async () => {
      await request(`/contacts/${contact.id}`, { method: "DELETE" }); loadContacts();
    });
    return row;
  }

  async function loadContacts() {
    const contacts = await request("/contacts");
    const list = $("#contact-list"); list.replaceChildren();
    contacts.forEach((contact) => list.append(contactRow(contact)));
  }

  async function loadHistory() {
    const calls = await request("/calls");
    const list = $("#history-list"); list.replaceChildren();
    if (!calls.length) { list.innerHTML = '<p class="empty">No calls yet. Place one from the Caller phone.</p>'; return; }
    calls.forEach((call) => {
      const row = document.createElement("article"); row.className = "data-row history-row";
      const date = new Date(call.started_at).toLocaleString();
      row.innerHTML = `<div><strong></strong><span></span></div><div class="history-meta"><b></b><em></em><small></small></div>`;
      row.querySelector("strong").textContent = call.from_label || call.from_phone || "Withheld number";
      row.querySelector("span").textContent = date;
      row.querySelector("b").textContent = call.classification;
      row.querySelector("em").textContent = call.classification === "trusted" ? "Private" : `Peak risk ${call.peak_risk || 0}`;
      row.querySelector("small").textContent = call.ended_at ? "Ended" : "In progress";
      list.append(row);
    });
  }

  async function loadMessages() {
    const messages = await request("/messages");
    const list = $("#message-list"); list.replaceChildren();
    if (!messages.length) { list.innerHTML = '<p class="empty">No messages yet.</p>'; return; }
    messages.forEach((message) => {
      const row = document.createElement("article"); row.className = "data-row";
      row.innerHTML = '<div><strong></strong><span></span></div><div class="history-meta"><small></small></div>';
      row.querySelector("strong").textContent = message.caller_name || "Unknown caller";
      row.querySelector("span").textContent = message.body;
      row.querySelector("small").textContent = message.callback_number ? `Callback: ${message.callback_number}` : new Date(message.created_at).toLocaleString();
      list.append(row);
    });
  }

  function resetLive(callId) {
    currentCallId = callId;
    seenTranscript.clear();
    lastBubble = null;
    $("#live-feed").className = "transcript-stream empty";
    $("#live-feed").textContent = "Listening for the first words…";
    $("#timeline-list").innerHTML = '<li class="empty">Call connected. Monitoring begins after Margaret answers.</li>';
    updateRisk({ score: 0, signals: [], evidence: [] });
  }

  function updateRisk(message) {
    const score = Math.max(0, Math.min(100, Number(message.score) || 0));
    $("#risk-score").textContent = Math.round(score);
    $("#risk-fill").style.width = `${score}%`;
    const band = score >= 90 ? "critical" : score >= 65 ? "guardian" : score >= 40 ? "nudge" : "quiet";
    $("#risk-fill").dataset.band = band;
    $("#risk-status").textContent = {
      quiet: "Quiet", nudge: "Senior nudged", guardian: "Guardian stepped in", critical: "Critical",
    }[band];

    const chips = $("#signal-chips");
    chips.replaceChildren();
    if (!(message.signals || []).length) {
      chips.innerHTML = '<span class="signal-empty">No risk signals</span>';
      return;
    }
    message.signals.forEach((signal) => {
      const evidence = (message.evidence || []).filter((item) => item.family === signal);
      const chip = document.createElement("span");
      chip.className = `signal-chip ${signal === "benign" ? "benign" : ""}`;
      chip.textContent = signal.replaceAll("_", " ");
      chip.title = evidence.length
        ? evidence.map((item) => `${item.speaker}: “${item.phrase}”`).join("\n")
        : "Signal remains active while its score decays.";
      chips.append(chip);
    });
  }

  function addTranscript(message) {
    const key = `${message.call_id || ""}|${message.speaker}|${message.t_ms}|${message.text}`;
    if (seenTranscript.has(key)) return;
    seenTranscript.add(key);
    const feed = $("#live-feed");
    if (feed.classList.contains("empty")) {
      feed.replaceChildren();
      feed.classList.remove("empty");
    }
    const tMs = Number(message.t_ms) || 0;
    if (lastBubble && lastBubble.speaker === message.speaker && tMs - lastBubble.tMs <= 3000) {
      const text = lastBubble.node.querySelector(".transcript-text");
      text.textContent = `${text.textContent} ${message.text}`.trim();
      lastBubble.tMs = tMs;
      return;
    }
    const line = document.createElement("article");
    line.className = `transcript-line ${message.speaker === "senior" ? "senior" : "caller"}`;
    line.innerHTML = '<b></b><p class="transcript-text"></p><time></time>';
    line.querySelector("b").textContent = message.speaker === "senior" ? "Margaret" : "Caller";
    line.querySelector(".transcript-text").textContent = message.text;
    line.querySelector("time").textContent = `${(tMs / 1000).toFixed(1)}s`;
    feed.append(line);
    feed.scrollTop = feed.scrollHeight;
    lastBubble = { speaker: message.speaker, tMs, node: line };
  }

  function addTimeline(message) {
    const list = $("#timeline-list");
    const empty = list.querySelector(".empty");
    if (empty) empty.remove();
    const item = document.createElement("li");
    const seconds = ((Number(message.t_ms) || 0) / 1000).toFixed(1);
    if (message.type === "level") {
      item.className = `level-${message.level}`;
      item.innerHTML = `<time>${seconds}s</time><b>Safety level ${message.level}</b><span></span>`;
      item.querySelector("span").textContent = message.level === 1 ? "Soft nudge sent to Margaret" : `Triggered · ${message.trigger || "risk threshold"}`;
    } else if (message.type === "tool") {
      item.innerHTML = `<time>${seconds}s</time><b>Guardian action</b><span></span>`;
      item.querySelector("span").textContent = String(message.name || "").replaceAll("_", " ");
    } else {
      item.innerHTML = `<time>${seconds}s</time><b></b><span></span>`;
      item.querySelector("b").textContent = message.to || "Call state";
      item.querySelector("span").textContent = message.trigger || "State changed";
    }
    list.append(item);
  }

  $("#contact-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await request("/contacts", { method: "POST", body: JSON.stringify({
      label: $("#contact-label").value, phone: $("#contact-phone").value,
      status: $("#contact-status").value,
    }) });
    event.target.reset(); loadContacts();
  });
  $("#refresh-history").addEventListener("click", loadHistory);
  $("#refresh-messages").addEventListener("click", loadMessages);
  $("#ring-family").addEventListener("click", async () => {
    const result = await request("/calls/current/ring-family", { method: "POST" });
    addTimeline({ type: "state", t_ms: 0, to: result.ok ? "FAMILY RINGING" : "NO ACTIVE CALL", trigger: result.ok ? "Sarah was invited" : "Answer a call first" });
  });
  $("#guardian-join").addEventListener("click", async () => {
    await request("/calls/current/guardian/family", { method: "POST" });
  });

  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${scheme}://${location.host}/ws/dashboard?room=${encodeURIComponent(room)}`);
  socket.addEventListener("open", () => { $("#connection").textContent = "Live connection"; $("#connection").classList.add("online"); });
  socket.addEventListener("close", () => { $("#connection").textContent = "Disconnected"; $("#connection").classList.remove("online"); });
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "ping") { socket.send(JSON.stringify({ type: "pong" })); return; }
    if (message.type === "call" && message.event === "started") resetLive(message.call_id);
    if (message.type === "call") {
      loadHistory();
      if (message.event === "ended") $("#guardian-banner").hidden = true;
    }
    if (message.type === "message") loadMessages();
    if (message.type === "state") {
      $("#live-state").textContent = message.to;
      $("#live-classification").textContent = message.classification || message.trigger || "Call state changed";
      addTimeline(message);
    }
    if (message.type === "transcript") addTranscript(message);
    if (message.type === "risk") updateRisk(message);
    if (message.type === "level") addTimeline(message);
    if (message.type === "tool") addTimeline(message);
    if (message.type === "guardian") {
      const active = ["GUARDIAN", "FAMILY_CONF"].includes(message.state);
      $("#guardian-banner").hidden = !active;
      $("#guardian-detail").textContent = message.tool ? `Guardian chose: ${message.tool.replaceAll("_", " ")}` : (message.recommendation === "bring in family" ? "Family support is recommended." : "The caller is safely on hold.");
      $("#guardian-join").hidden = message.state === "FAMILY_CONF";
    }
  });
  loadContacts(); loadMessages(); loadHistory();
})();
