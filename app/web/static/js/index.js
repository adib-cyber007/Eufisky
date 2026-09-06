const roomInput = document.querySelector("#room");
const roomNote = document.querySelector("#room-note");
const requestedRoom = new URLSearchParams(location.search).get("room");

function updateLinks() {
  const room = roomInput.value.trim() || "demo";
  document.querySelectorAll("[data-page]").forEach((link) => {
    link.href = `/${link.dataset.page}?room=${encodeURIComponent(room)}`;
  });
  roomNote.textContent = `Links now use room “${room}”.`;
}

roomInput.addEventListener("input", updateLinks);
document.querySelector("#new-room").addEventListener("click", async () => {
  const response = await fetch("/api/rooms/new", { method: "POST" });
  const data = await response.json();
  roomInput.value = data.room;
  updateLinks();
  roomNote.textContent = `New room “${data.room}” is ready. Open the phones below.`;
});

if (requestedRoom) roomInput.value = requestedRoom;
updateLinks();
fetch(`/api/rooms/${encodeURIComponent(roomInput.value.trim() || "demo")}/contacts`)
  .catch(() => { roomNote.textContent = "The room will be prepared when you open a phone."; });
