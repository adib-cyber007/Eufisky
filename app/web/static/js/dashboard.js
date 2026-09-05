(function () {
  const room = new URLSearchParams(location.search).get("room") || "demo";
  const $ = (selector) => document.querySelector(selector);
  document.querySelectorAll("[data-room]").forEach((node) => { node.textContent = room; });

  document.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll("[data-tab]").forEach((item) => item.classList.toggle("active", item === button));
    document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `panel-${button.dataset.tab}`));
    if (button.dataset.tab === "contacts") loadContacts();
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
      row.innerHTML = `<div><strong></strong><span></span></div><div class="history-meta"><b></b><small></small></div>`;
      row.querySelector("strong").textContent = call.from_label || call.from_phone || "Withheld number";
      row.querySelector("span").textContent = date;
      row.querySelector("b").textContent = call.classification;
      row.querySelector("small").textContent = call.ended_at ? "Ended" : "In progress";
      list.append(row);
    });
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
  $("#ring-family").addEventListener("click", async () => {
    const result = await request("/calls/current/ring-family", { method: "POST" });
    $("#live-feed").textContent = result.ok ? "Sarah’s phone is ringing." : "Start and answer a call before ringing Sarah.";
  });

  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${scheme}://${location.host}/ws/dashboard?room=${encodeURIComponent(room)}`);
  socket.addEventListener("open", () => { $("#connection").textContent = "Live connection"; $("#connection").classList.add("online"); });
  socket.addEventListener("close", () => { $("#connection").textContent = "Disconnected"; $("#connection").classList.remove("online"); });
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "ping") { socket.send(JSON.stringify({ type: "pong" })); return; }
    if (message.type === "state") {
      $("#live-state").textContent = message.to;
      $("#live-classification").textContent = message.classification || message.trigger || "Call state changed";
    }
    if (message.type === "call") { loadHistory(); }
    if (message.type === "transcript") {
      const line = document.createElement("p");
      line.innerHTML = `<b></b><span></span>`;
      line.querySelector("b").textContent = `${message.speaker}: `;
      line.querySelector("span").textContent = message.text;
      const feed = $("#live-feed"); if (feed.classList.contains("empty")) { feed.textContent = ""; feed.classList.remove("empty"); }
      feed.prepend(line);
    }
  });
  loadContacts(); loadHistory();
})();
