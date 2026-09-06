(function () {
  const room = new URLSearchParams(location.search).get("room") || "demo";
  const $ = (selector) => document.querySelector(selector);
  const seenTranscript = new Set();
  const seenTimeline = new Set();
  let lastBubble = null;
  let currentCallId = null;
  let socket = null;
  let reconnectTimer = null;
  let reconnectAttempt = 0;
  let unreadMessages = 0;

  document.querySelectorAll("[data-room]").forEach((node) => { node.textContent = room; });

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function showError(container, message) {
    container.replaceChildren(element("p", "empty error-copy", message));
  }

  function activateTab(name) {
    document.querySelectorAll("[data-tab]").forEach((item) => {
      item.classList.toggle("active", item.dataset.tab === name);
    });
    document.querySelectorAll(".tab-panel").forEach((panel) => {
      panel.classList.toggle("active", panel.id === `panel-${name}`);
    });
    if (name === "contacts") return loadContacts();
    if (name === "messages") {
      unreadMessages = 0;
      updateUnreadBadge();
      return loadMessages();
    }
    if (name === "history") return loadHistory();
    if (name === "settings") return loadSettings();
    return Promise.resolve();
  }

  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => activateTab(button.dataset.tab));
  });

  async function request(path, options = {}) {
    const response = await fetch(`/api/rooms/${encodeURIComponent(room)}${path}`, {
      headers: { "Content-Type": "application/json" }, ...options,
    });
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    return response.status === 204 ? null : response.json();
  }

  function updateUnreadBadge() {
    const badge = $("#message-unread");
    badge.textContent = String(unreadMessages);
    badge.hidden = unreadMessages === 0;
  }

  async function loadSettings() {
    try {
      const roomSettings = await request("/settings");
      $("#always-ring-first").checked = Boolean(roomSettings.always_ring_first);
      $("#settings-feedback").textContent = "";
    } catch (error) {
      $("#settings-feedback").textContent = "Settings could not be loaded.";
      $("#settings-feedback").classList.add("error-copy");
    }
  }

  function contactFeedback(message, error = false) {
    const feedback = $("#contact-feedback");
    feedback.textContent = message;
    feedback.classList.toggle("error-copy", error);
  }

  async function changeContactStatus(contact, status, label) {
    try {
      await request(`/contacts/${contact.id}`, {
        method: "PATCH", body: JSON.stringify({ status }),
      });
      contactFeedback(`${contact.label} is now ${label.toLowerCase()}.`);
      await loadContacts();
    } catch (error) {
      contactFeedback(`${contact.label} could not be updated.`, true);
    }
  }

  function contactRow(contact) {
    const row = element("article", "data-row contact-row");
    const identity = element("div", "contact-identity");
    identity.append(element("strong", "", contact.label));
    const details = element("div", "contact-details");
    details.append(element("span", "contact-phone", contact.phone));
    details.append(element("span", `status-badge ${contact.status}`, contact.status));
    identity.append(details);
    if (contact.status === "blocked" && contact.related_call_id) {
      const reason = element("p", "block-reason", contact.block_reason || "Blocked after a safety incident.");
      const link = element("button", "incident-link", "View related incident");
      link.type = "button";
      link.addEventListener("click", async () => {
        await activateTab("history");
        const card = document.querySelector(`[data-call-id="${CSS.escape(contact.related_call_id)}"]`);
        if (card) {
          card.scrollIntoView({ behavior: "smooth", block: "center" });
          card.classList.add("incident-highlight");
          setTimeout(() => card.classList.remove("incident-highlight"), 2200);
        }
      });
      reason.append(" ", link);
      identity.append(reason);
    }
    const actions = element("div", "row-actions");
    const statusActions = [["Trust", "trusted"]];
    if (contact.status === "trusted") statusActions.push(["Untrust", "pending"]);
    statusActions.push(["Block", "blocked"]);
    if (contact.status === "blocked") statusActions.push(["Unblock", "pending"]);
    statusActions.forEach(([label, status]) => {
      const button = element("button", "", label);
      button.type = "button";
      button.disabled = contact.status === status;
      button.dataset.action = label.toLowerCase();
      button.addEventListener("click", () => changeContactStatus(contact, status, status));
      actions.append(button);
    });
    const remove = element("button", "", "Delete");
    remove.type = "button";
    remove.dataset.delete = "";
    remove.addEventListener("click", async () => {
      if (!window.confirm(`Delete ${contact.label} from Contacts?`)) return;
      try {
        await request(`/contacts/${contact.id}`, { method: "DELETE" });
        contactFeedback(`${contact.label} was deleted.`);
        await loadContacts();
      } catch (error) {
        contactFeedback(`${contact.label} could not be deleted.`, true);
      }
    });
    actions.append(remove);
    row.append(identity, actions);
    return row;
  }

  async function loadContacts() {
    const list = $("#contact-list");
    try {
      const contacts = await request("/contacts");
      list.replaceChildren(...contacts.map(contactRow));
      if (!contacts.length) list.append(element("p", "empty", "No contacts yet."));
    } catch (error) {
      showError(list, "Contacts could not be loaded. Try Refresh.");
    }
  }

  function riskBand(score) {
    if (score >= 90) return "critical";
    if (score >= 65) return "guardian";
    if (score >= 40) return "nudge";
    return "quiet";
  }

  function sparkline(samples) {
    const figure = element("figure", "risk-sparkline");
    const caption = element("figcaption", "", "Risk over time");
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 300 72");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Call risk score over time");
    const values = samples.length ? samples : [{ t_ms: 0, score: 0 }];
    const maxTime = Math.max(1, ...values.map((sample) => Number(sample.t_ms) || 0));
    const points = values.map((sample) => {
      const x = 4 + ((Number(sample.t_ms) || 0) / maxTime) * 292;
      const y = 68 - (Math.max(0, Math.min(100, Number(sample.score) || 0)) / 100) * 64;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    const guide = document.createElementNS("http://www.w3.org/2000/svg", "line");
    guide.setAttribute("x1", "4"); guide.setAttribute("x2", "296");
    guide.setAttribute("y1", "26.4"); guide.setAttribute("y2", "26.4");
    guide.setAttribute("class", "guardian-guide");
    const polyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    polyline.setAttribute("points", points);
    svg.append(guide, polyline);
    figure.append(caption, svg);
    return figure;
  }

  function detailRow(label, value, className = "") {
    const wrapper = element("div", className);
    wrapper.append(element("dt", "", label), element("dd", "", value || "Not captured"));
    return wrapper;
  }

  function historyTimeline(events) {
    const list = element("ol", "incident-timeline");
    const relevant = events.filter((event) => ["state", "level", "tool", "family"].includes(event.type));
    relevant.forEach((event) => {
      const payload = event.payload || {};
      const item = element("li");
      item.append(element("time", "", `${((Number(event.t_ms) || 0) / 1000).toFixed(0)}s`));
      let title = "Call update";
      let copy = payload.trigger || "Recorded";
      if (event.type === "state") title = payload.to || "Call state";
      if (event.type === "level") {
        title = `Safety level ${payload.level || ""}`;
        copy = payload.level === 1 ? "Margaret received a private nudge" : (payload.trigger || "Risk threshold crossed");
      }
      if (event.type === "tool") {
        title = "Guardian action";
        copy = String(payload.name || "action recorded").replaceAll("_", " ");
      }
      if (event.type === "family") {
        title = "Family support";
        copy = String(payload.event || "invited");
      }
      item.append(element("b", "", title), element("span", "", copy));
      list.append(item);
    });
    if (!relevant.length) list.append(element("li", "empty", "No safety actions were needed."));
    return list;
  }

  function incidentCard(call, detail) {
    const incident = detail.incident;
    const summary = incident.summary || {};
    const peak = Number(call.peak_risk) || 0;
    const card = element("article", `incident-card ${riskBand(peak)}`);
    card.dataset.callId = call.id;
    const header = element("header", "incident-header");
    const heading = element("div");
    heading.append(
      element("h3", "", call.from_label || call.from_phone || "Withheld number"),
      element("time", "", new Date(call.started_at).toLocaleString()),
    );
    const badges = element("div", "incident-badges");
    badges.append(element("span", `risk-badge ${riskBand(peak)}`, `Peak risk ${peak}`));
    const fallback = String(incident.analysis_source || "").startsWith("template");
    badges.append(element("span", `source-badge ${fallback ? "fallback" : ""}`, fallback ? "Template fallback" : "AI summary"));
    header.append(heading, badges);
    card.append(header, element("p", "incident-summary", summary.summary || "Incident summary unavailable."));

    const facts = element("dl", "incident-facts");
    facts.append(
      detailRow("Caller claimed", summary.caller_claim),
      detailRow("Asked for", Array.isArray(summary.requests_made) ? summary.requests_made.join("; ") : summary.requests_made),
      detailRow("Margaret shared", summary.disclosed_by_senior),
      detailRow("Intervention", summary.intervention),
      detailRow("Outcome", summary.outcome),
      detailRow("Recommendation", summary.recommendation, "recommendation"),
    );
    card.append(facts);

    const trace = element("div", "incident-trace");
    trace.append(sparkline(detail.samples || []));
    const timelineDetails = element("details", "incident-details");
    timelineDetails.append(element("summary", "", "Safety timeline"), historyTimeline(detail.events || []));
    trace.append(timelineDetails);
    card.append(trace);

    const disclosure = element("div", "incident-disclosure");
    const transcript = element("details");
    transcript.append(element("summary", "", "View redacted transcript"));
    transcript.append(element("pre", "", incident.redacted_transcript || "No transcript was captured."));
    disclosure.append(transcript);
    if (incident.redacted_audio) {
      const audioWrap = element("div", "incident-audio");
      audioWrap.append(element("span", "", "Redacted call audio"));
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.preload = "none";
      audio.src = `/api/rooms/${encodeURIComponent(room)}/calls/${encodeURIComponent(call.id)}/audio`;
      audioWrap.append(audio);
      disclosure.append(audioWrap);
    }
    card.append(disclosure);
    return card;
  }

  function compactCall(call) {
    const row = element("article", "data-row history-row");
    const identity = element("div");
    identity.append(
      element("strong", "", call.from_label || call.from_phone || "Withheld number"),
      element("span", "", new Date(call.started_at).toLocaleString()),
    );
    const meta = element("div", "history-meta");
    meta.append(element("b", "", call.classification));
    meta.append(element("em", "", call.classification === "trusted" ? "Private—never monitored" : call.ended_at ? "Report is being prepared" : "In progress"));
    row.append(identity, meta);
    return row;
  }

  async function loadHistory() {
    const list = $("#history-list");
    list.replaceChildren(element("p", "empty", "Loading incident history…"));
    try {
      const calls = await request("/calls");
      if (!calls.length) {
        showError(list, "No calls yet. Place one from the Caller phone or replay the demo.");
        return;
      }
      const reports = calls.filter((call) => call.incident);
      const details = await Promise.all(reports.map((call) => request(`/calls/${encodeURIComponent(call.id)}`)));
      list.replaceChildren();
      if (reports.length) {
        list.append(element("h3", "history-subhead", "Safety reports"));
        reports.forEach((call, index) => list.append(incidentCard(call, details[index])));
      }
      const otherCalls = calls.filter((call) => !call.incident).slice(0, 8);
      if (otherCalls.length) {
        list.append(element("h3", "history-subhead compact", "Recent calls"));
        otherCalls.forEach((call) => list.append(compactCall(call)));
      }
    } catch (error) {
      showError(list, "History could not be loaded. Try Refresh.");
    }
  }

  async function loadMessages() {
    const list = $("#message-list");
    try {
      const messages = await request("/messages");
      list.replaceChildren();
      if (!messages.length) {
        list.append(element("p", "empty", "No messages yet."));
        return;
      }
      messages.forEach((message) => {
        const row = element("article", "data-row message-row");
        const content = element("div");
        content.append(element("strong", "", message.caller_name || "Unknown caller"));
        content.append(element("p", "", message.body));
        const meta = element("div", "history-meta");
        meta.append(element("small", "", message.callback_number ? `Callback: ${message.callback_number}` : "No callback number"));
        meta.append(element("time", "", new Date(message.created_at).toLocaleString()));
        row.append(content, meta);
        list.append(row);
      });
    } catch (error) {
      showError(list, "Messages could not be loaded. Try Refresh.");
    }
  }

  function resetLive(callId) {
    currentCallId = callId;
    seenTranscript.clear();
    seenTimeline.clear();
    lastBubble = null;
    $("#live-feed").className = "transcript-stream empty";
    $("#live-feed").textContent = "Listening for the first words…";
    $("#timeline-list").innerHTML = '<li class="empty">Call connected. Monitoring begins after Margaret answers.</li>';
    $("#live-state").textContent = "SCREENING";
    $("#live-classification").textContent = "Unknown caller is being screened";
    updateRisk({ score: 0, signals: [], evidence: [] });
  }

  function updateRisk(message) {
    const score = Math.max(0, Math.min(100, Number(message.score) || 0));
    $("#risk-score").textContent = Math.round(score);
    $("#risk-fill").style.width = `${score}%`;
    const band = riskBand(score);
    $("#risk-fill").dataset.band = band;
    $("#risk-status").textContent = {
      quiet: "Quiet", nudge: "Senior nudged", guardian: "Guardian stepped in", critical: "Critical",
    }[band];
    const chips = $("#signal-chips");
    chips.replaceChildren();
    if (!(message.signals || []).length) {
      chips.append(element("span", "signal-empty", "No risk signals"));
      return;
    }
    message.signals.forEach((signal) => {
      const evidence = (message.evidence || []).filter((item) => item.family === signal);
      const chip = element("span", `signal-chip ${signal === "benign" ? "benign" : ""}`, signal.replaceAll("_", " "));
      chip.title = evidence.length ? evidence.map((item) => `${item.speaker}: “${item.phrase}”`).join("\n") : "Signal remains active while its score decays.";
      chips.append(chip);
    });
  }

  function speakerLabel(speaker) {
    return { senior: "Margaret", family: "Sarah", caller: "Caller", agent: "Eufisky" }[speaker] || "Caller";
  }

  function addTranscript(message) {
    const speaker = message.speaker || message.role || "caller";
    const key = `${message.call_id || ""}|${speaker}|${message.t_ms}|${message.text}`;
    if (seenTranscript.has(key)) return;
    seenTranscript.add(key);
    const feed = $("#live-feed");
    if (feed.classList.contains("empty")) {
      feed.replaceChildren();
      feed.classList.remove("empty");
    }
    const tMs = Number(message.t_ms) || 0;
    if (lastBubble && lastBubble.speaker === speaker && tMs - lastBubble.tMs <= 3000) {
      const text = lastBubble.node.querySelector(".transcript-text");
      text.textContent = `${text.textContent} ${message.text}`.trim();
      lastBubble.tMs = tMs;
      return;
    }
    const line = element("article", `transcript-line ${speaker}`);
    line.append(element("b", "", speakerLabel(speaker)));
    line.append(element("p", "transcript-text", message.text));
    line.append(element("time", "", `${(tMs / 1000).toFixed(1)}s`));
    feed.append(line);
    feed.scrollTop = feed.scrollHeight;
    lastBubble = { speaker, tMs, node: line };
  }

  function addTimeline(message) {
    const key = `${message.type}|${message.t_ms}|${message.to || message.level || message.name || ""}`;
    if (seenTimeline.has(key)) return;
    seenTimeline.add(key);
    const list = $("#timeline-list");
    const empty = list.querySelector(".empty");
    if (empty) empty.remove();
    const item = element("li");
    const seconds = ((Number(message.t_ms) || 0) / 1000).toFixed(1);
    item.append(element("time", "", `${seconds}s`));
    if (message.type === "level") {
      item.className = `level-${message.level}`;
      item.append(element("b", "", `Safety level ${message.level}`));
      item.append(element("span", "", message.level === 1 ? "Soft nudge sent to Margaret" : `Triggered · ${message.trigger || "risk threshold"}`));
    } else if (message.type === "tool") {
      item.append(element("b", "", "Guardian action"));
      item.append(element("span", "", String(message.name || "").replaceAll("_", " ")));
    } else {
      item.append(element("b", "", message.to || "Call state"));
      item.append(element("span", "", message.trigger || "State changed"));
    }
    list.append(item);
  }

  function handleSocketMessage(event) {
    let message;
    try { message = JSON.parse(event.data); } catch (error) { return; }
    if (message.type === "ping") {
      if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "pong" }));
      return;
    }
    if (message.type === "replay") {
      if (message.status === "started") {
        resetLive("replay-demo");
        $("#replay-status").textContent = "Replay running…";
      } else {
        $("#replay-status").textContent = "Replay complete.";
        $("#replay-demo").disabled = false;
      }
      return;
    }
    if (message.type === "call" && message.event === "started") resetLive(message.call_id);
    if (message.type === "call") {
      if (!message.replay) loadHistory();
      if (message.event === "ended") $("#guardian-banner").hidden = true;
    }
    if (message.type === "incident") {
      $("#replay-status").textContent = "A new incident report is ready.";
      loadHistory();
    }
    if (message.type === "message") loadMessages();
    if (message.type === "notice") {
      const messagesOpen = $("[data-tab=\"messages\"]").classList.contains("active");
      if (!messagesOpen) {
        unreadMessages += 1;
        updateUnreadBadge();
      } else {
        loadMessages();
      }
    }
    if (message.type === "state") {
      $("#live-state").textContent = message.to || "IDLE";
      $("#live-classification").textContent = message.classification || message.trigger || "Call state changed";
      if (message.trigger !== "snapshot") addTimeline(message);
    }
    if (message.type === "transcript" || message.type === "caption") addTranscript(message);
    if (message.type === "risk") updateRisk(message);
    if (message.type === "level" || message.type === "tool") addTimeline(message);
    if (message.type === "guardian") {
      const active = ["GUARDIAN", "FAMILY_CONF"].includes(message.state);
      $("#guardian-banner").hidden = !active;
      $("#guardian-detail").textContent = message.tool ? `Guardian chose: ${message.tool.replaceAll("_", " ")}` : (message.recommendation === "bring in family" ? "Family support is recommended." : "The caller is safely on hold.");
      $("#guardian-join").hidden = message.state === "FAMILY_CONF";
    }
  }

  function connectDashboard() {
    clearTimeout(reconnectTimer);
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    $("#connection").textContent = reconnectAttempt ? "Reconnecting…" : "Connecting…";
    socket = new WebSocket(`${scheme}://${location.host}/ws/dashboard?room=${encodeURIComponent(room)}`);
    socket.addEventListener("open", () => {
      reconnectAttempt = 0;
      $("#connection").textContent = "Live connection";
      $("#connection").classList.add("online");
    });
    socket.addEventListener("message", handleSocketMessage);
    socket.addEventListener("close", () => {
      $("#connection").textContent = "Reconnecting…";
      $("#connection").classList.remove("online");
      const wait = Math.min(10000, 1000 * (2 ** reconnectAttempt));
      reconnectAttempt = Math.min(reconnectAttempt + 1, 4);
      reconnectTimer = setTimeout(connectDashboard, wait);
    });
  }

  $("#contact-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const label = $("#contact-label").value.trim();
    try {
      await request("/contacts", { method: "POST", body: JSON.stringify({
        label, phone: $("#contact-phone").value.trim(),
        status: $("#contact-status").value,
      }) });
      event.target.reset();
      contactFeedback(`${label} was added.`);
      await loadContacts();
    } catch (error) {
      contactFeedback(`${label || "The contact"} could not be added.`, true);
    }
  });
  $("#refresh-history").addEventListener("click", loadHistory);
  $("#refresh-messages").addEventListener("click", loadMessages);
  $("#always-ring-first").addEventListener("change", async (event) => {
    const toggle = event.target;
    toggle.disabled = true;
    try {
      const saved = await request("/settings", {
        method: "PATCH",
        body: JSON.stringify({ always_ring_first: toggle.checked }),
      });
      toggle.checked = Boolean(saved.always_ring_first);
      $("#settings-feedback").classList.remove("error-copy");
      $("#settings-feedback").textContent = toggle.checked
        ? "On — screened risky calls will ring Margaret and remain monitored."
        : "Off — the standard Front Door filtering policy is active.";
    } catch (error) {
      toggle.checked = !toggle.checked;
      $("#settings-feedback").classList.add("error-copy");
      $("#settings-feedback").textContent = "The setting could not be saved.";
    } finally {
      toggle.disabled = false;
    }
  });
  $("#guardian-join").addEventListener("click", async () => {
    await request("/calls/current/guardian/family", { method: "POST" });
  });
  $("#replay-demo").addEventListener("click", async () => {
    const button = $("#replay-demo");
    button.disabled = true;
    $("#replay-status").textContent = "Starting replay…";
    try {
      await request("/replay", {
        method: "POST",
        body: JSON.stringify({ file: "demo_call.json", speed: Number($("#replay-speed").value) }),
      });
    } catch (error) {
      button.disabled = false;
      $("#replay-status").textContent = "Replay could not start. Check the live connection.";
    }
  });

  connectDashboard();
  loadContacts();
  loadMessages();
  loadHistory();
  loadSettings();
})();
