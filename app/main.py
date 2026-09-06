"""FastAPI entry point for the Eufisky browser phone simulation."""

from contextlib import asynccontextmanager
import json
from pathlib import Path
import secrets
from typing import Literal

from fastapi import FastAPI, HTTPException, Response, WebSocket
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app import db
from app.phone.calls import calls
from app.phone.ws import dashboard_socket, phone_socket
from app import replay as replay_mode
from app.rooms import rooms

APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Eufisky", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


class ContactCreate(BaseModel):
    phone: str
    label: str
    status: Literal["trusted", "blocked", "pending"] = "pending"


class ContactPatch(BaseModel):
    phone: str | None = None
    label: str | None = None
    status: Literal["trusted", "blocked", "pending"] | None = None


class ReplayRequest(BaseModel):
    file: str = "demo_call.json"
    speed: float = 2.0


class RoomSettingsPatch(BaseModel):
    always_ring_first: bool


@app.get("/api/health")
async def health() -> dict[str, bool | str]:
    """Report startup configuration without exposing any secret values."""

    db_ok = db.db_health()
    return {
        "ok": db_ok,
        "assemblyai_key_present": bool(settings.assemblyai_api_key),
        "agent_backend": settings.agent_backend,
        "db_ok": db_ok,
    }


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/{page_name}", response_class=FileResponse)
async def phone_page(page_name: str) -> FileResponse:
    if page_name not in {"caller", "senior", "family", "dashboard"}:
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(WEB_DIR / f"{page_name}.html")


@app.websocket("/ws/phone")
async def ws_phone(websocket: WebSocket) -> None:
    await phone_socket(websocket)


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket) -> None:
    await dashboard_socket(websocket, websocket.query_params.get("room", "demo"))


@app.post("/api/rooms/new")
async def new_room() -> dict[str, str]:
    room = secrets.token_hex(3)
    db.ensure_room(room)
    return {"room": room}


@app.get("/api/rooms/{room}/contacts")
async def contacts_list(room: str) -> list[dict]:
    return db.list_contacts(room)


@app.get("/api/rooms/{room}/settings")
async def settings_get(room: str) -> dict[str, bool]:
    return db.get_room_settings(room)


@app.patch("/api/rooms/{room}/settings")
async def settings_patch(room: str, room_settings: RoomSettingsPatch) -> dict[str, bool]:
    return db.update_room_settings(
        room, always_ring_first=room_settings.always_ring_first
    )


@app.post("/api/rooms/{room}/contacts", status_code=201)
async def contacts_create(room: str, contact: ContactCreate) -> dict:
    return db.create_contact(room, contact.phone, contact.label, contact.status)


@app.patch("/api/rooms/{room}/contacts/{contact_id}")
async def contacts_patch(room: str, contact_id: int, contact: ContactPatch) -> dict:
    result = db.update_contact(room, contact_id, contact.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=404, detail="Contact not found")
    return result


@app.delete("/api/rooms/{room}/contacts/{contact_id}", status_code=204)
async def contacts_delete(room: str, contact_id: int) -> Response:
    if not db.delete_contact(room, contact_id):
        raise HTTPException(status_code=404, detail="Contact not found")
    return Response(status_code=204)


@app.get("/api/rooms/{room}/calls")
async def calls_list(room: str) -> list[dict]:
    return db.list_calls(room)


@app.get("/api/rooms/{room}/calls/{call_id}")
async def calls_get(room: str, call_id: str) -> dict:
    result = db.call_detail(room, call_id)
    if not result:
        raise HTTPException(status_code=404, detail="Call not found")
    return result


@app.get("/api/rooms/{room}/calls/{call_id}/audio", response_class=FileResponse)
async def incident_audio(room: str, call_id: str) -> FileResponse:
    result = db.call_detail(room, call_id)
    incident = result.get("incident") if result else None
    value = incident.get("redacted_audio") if incident else None
    if not value:
        raise HTTPException(status_code=404, detail="Redacted audio not available")
    path = Path(str(value))
    path = path if path.is_absolute() else db.PROJECT_ROOT / path
    resolved = path.resolve()
    if not resolved.is_relative_to(db.DATA_DIR.resolve()) or not resolved.exists():
        raise HTTPException(status_code=404, detail="Redacted audio not available")
    return FileResponse(resolved, media_type="audio/wav", filename=f"incident-{call_id}.wav")


@app.get("/api/rooms/{room}/messages")
async def messages_list(room: str) -> list[dict]:
    return db.list_messages(room)


@app.post("/api/rooms/{room}/replay")
async def replay(room: str, request: ReplayRequest) -> dict:
    db.ensure_room(room)
    try:
        return replay_mode.start(room, request.file, request.speed)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Replay file not found") from None
    except (ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from None


@app.get("/api/rooms/{room}/live")
async def live_state(room: str) -> dict:
    return rooms.snapshot(room)


@app.post("/api/rooms/{room}/calls/current/ring-family")
async def ring_family(room: str) -> dict[str, bool]:
    return {"ok": await calls.ring_family(room)}


@app.post("/api/rooms/{room}/calls/current/guardian/{action}")
async def guardian_action(room: str, action: str) -> dict[str, bool]:
    return {"ok": await calls.guardian_action(room, "dashboard", action)}


__all__ = ["app", "settings"]
