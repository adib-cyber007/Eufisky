"""Small SQLite persistence layer for Eufisky rooms and calls."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "eufisky.db"
SEED_PATH = DATA_DIR / "seed.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room TEXT NOT NULL,
    phone TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('trusted','blocked','pending')),
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contacts_room_phone ON contacts(room, phone);
CREATE TABLE IF NOT EXISTS calls (
    id TEXT PRIMARY KEY, room TEXT NOT NULL, from_phone TEXT, from_label TEXT,
    classification TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT,
    final_state TEXT, peak_risk INTEGER NOT NULL DEFAULT 0,
    front_door_outcome TEXT, guardian_outcome TEXT,
    recording_caller TEXT, recording_senior TEXT
);
CREATE INDEX IF NOT EXISTS idx_calls_room_started ON calls(room, started_at DESC);
CREATE TABLE IF NOT EXISTS call_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT NOT NULL, t_ms INTEGER NOT NULL,
    type TEXT NOT NULL, payload_json TEXT NOT NULL,
    FOREIGN KEY(call_id) REFERENCES calls(id)
);
CREATE TABLE IF NOT EXISTS risk_samples (
    call_id TEXT NOT NULL, t_ms INTEGER NOT NULL, score INTEGER NOT NULL,
    signals_json TEXT NOT NULL, FOREIGN KEY(call_id) REFERENCES calls(id)
);
CREATE TABLE IF NOT EXISTS transcript_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT NOT NULL, speaker TEXT NOT NULL,
    t_ms INTEGER NOT NULL, text TEXT NOT NULL, is_final INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(call_id) REFERENCES calls(id)
);
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT NOT NULL, summary_json TEXT,
    redacted_transcript TEXT, entities_json TEXT, created_at TEXT NOT NULL,
    FOREIGN KEY(call_id) REFERENCES calls(id)
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, room TEXT NOT NULL, call_id TEXT,
    from_phone TEXT, caller_name TEXT, body TEXT NOT NULL, callback_number TEXT,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    """Create every documented table and seed the demo room."""
    with _connect() as connection:
        connection.executescript(SCHEMA)
    ensure_room("demo")


def _seed_contacts() -> list[dict[str, str]]:
    if not SEED_PATH.exists():
        return []
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return list(data.get("contacts", []))


def ensure_room(room: str) -> str:
    """Copy seed contacts into a room the first time it is seen."""
    room = room.strip() or "demo"
    with _connect() as connection:
        known = connection.execute("SELECT 1 FROM rooms WHERE id = ?", (room,)).fetchone()
        if not known:
            # Migrate rooms created before the durable room marker existed without
            # duplicating their seed contacts.
            has_existing_data = any(
                connection.execute(
                    f"SELECT 1 FROM {table} WHERE room = ? LIMIT 1", (room,)
                ).fetchone()
                for table in ("contacts", "calls", "messages")
            )
            connection.execute(
                "INSERT INTO rooms(id, created_at) VALUES (?, ?)", (room, _now())
            )
            if has_existing_data:
                return room
            for contact in _seed_contacts():
                connection.execute(
                    """INSERT INTO contacts(room, phone, label, status, source, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (room, contact["phone"], contact["label"],
                     contact.get("status", "pending"), contact.get("source", "seed"), _now()),
                )
    return room


def list_contacts(room: str) -> list[dict[str, Any]]:
    ensure_room(room)
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM contacts WHERE room = ? ORDER BY label COLLATE NOCASE", (room,)
        ).fetchall()
    return [dict(row) for row in rows]


def create_contact(
    room: str, phone: str, label: str, status: str = "pending", source: str = "manual"
) -> dict[str, Any]:
    ensure_room(room)
    if status not in {"trusted", "blocked", "pending"}:
        raise ValueError("invalid contact status")
    with _connect() as connection:
        cursor = connection.execute(
            """INSERT INTO contacts(room, phone, label, status, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (room, phone.strip(), label.strip(), status, source, _now()),
        )
        row = connection.execute("SELECT * FROM contacts WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def get_contact(room: str, contact_id: int) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM contacts WHERE room = ? AND id = ?", (room, contact_id)
        ).fetchone()
    return dict(row) if row else None


def update_contact(room: str, contact_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {"phone", "label", "status"}
    updates = {key: value for key, value in fields.items() if key in allowed}
    if "status" in updates and updates["status"] not in {"trusted", "blocked", "pending"}:
        raise ValueError("invalid contact status")
    if not updates:
        return get_contact(room, contact_id)
    clause = ", ".join(f"{key} = ?" for key in updates)
    with _connect() as connection:
        connection.execute(
            f"UPDATE contacts SET {clause} WHERE room = ? AND id = ?",
            (*updates.values(), room, contact_id),
        )
    return get_contact(room, contact_id)


def delete_contact(room: str, contact_id: int) -> bool:
    with _connect() as connection:
        cursor = connection.execute(
            "DELETE FROM contacts WHERE room = ? AND id = ?", (room, contact_id)
        )
    return cursor.rowcount > 0


def classify_phone(room: str, phone: str | None) -> tuple[str, str]:
    """Return classification and label, with blocked always winning."""
    phone = (phone or "").strip()
    if not phone:
        return "unknown", "Withheld number"
    ensure_room(room)
    with _connect() as connection:
        row = connection.execute(
            """SELECT label, status FROM contacts WHERE room = ? AND phone = ?
               ORDER BY CASE status WHEN 'blocked' THEN 0 WHEN 'trusted' THEN 1 ELSE 2 END
               LIMIT 1""",
            (room, phone),
        ).fetchone()
    if not row or row["status"] == "pending":
        return "unknown", "Unknown caller"
    return str(row["status"]), str(row["label"])


def create_call(call: dict[str, Any]) -> dict[str, Any]:
    columns = (
        "id", "room", "from_phone", "from_label", "classification", "started_at",
        "ended_at", "final_state", "peak_risk", "front_door_outcome", "guardian_outcome",
        "recording_caller", "recording_senior",
    )
    values = [call.get(column) for column in columns]
    values[5] = values[5] or _now()
    values[8] = values[8] or 0
    with _connect() as connection:
        connection.execute(
            f"INSERT INTO calls({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            values,
        )
    return get_call(call["id"]) or call


def update_call(call_id: str, **fields: Any) -> None:
    allowed = {
        "ended_at", "final_state", "peak_risk", "front_door_outcome", "guardian_outcome",
        "recording_caller", "recording_senior", "classification", "from_label",
    }
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return
    clause = ", ".join(f"{key} = ?" for key in updates)
    with _connect() as connection:
        connection.execute(f"UPDATE calls SET {clause} WHERE id = ?", (*updates.values(), call_id))


def list_calls(room: str) -> list[dict[str, Any]]:
    ensure_room(room)
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM calls WHERE room = ? ORDER BY started_at DESC", (room,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_call(call_id: str, room: str | None = None) -> dict[str, Any] | None:
    sql = "SELECT * FROM calls WHERE id = ?"
    params: tuple[Any, ...] = (call_id,)
    if room is not None:
        sql += " AND room = ?"
        params = (call_id, room)
    with _connect() as connection:
        row = connection.execute(sql, params).fetchone()
    return dict(row) if row else None


def add_event(call_id: str, t_ms: int, event_type: str, payload: dict[str, Any]) -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT INTO call_events(call_id,t_ms,type,payload_json) VALUES (?,?,?,?)",
            (call_id, t_ms, event_type, json.dumps(payload)),
        )


def add_segment(
    call_id: str, speaker: str, t_ms: int, text: str, is_final: bool = True
) -> dict[str, Any]:
    with _connect() as connection:
        cursor = connection.execute(
            """INSERT INTO transcript_segments(call_id,speaker,t_ms,text,is_final)
               VALUES (?,?,?,?,?)""",
            (call_id, speaker, t_ms, text, int(is_final)),
        )
    return {"id": cursor.lastrowid, "call_id": call_id, "speaker": speaker,
            "t_ms": t_ms, "text": text, "is_final": is_final}


def list_segments(call_id: str) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM transcript_segments WHERE call_id = ? ORDER BY t_ms, id", (call_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def list_events(call_id: str) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM call_events WHERE call_id = ? ORDER BY t_ms, id", (call_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def list_messages(room: str) -> list[dict[str, Any]]:
    ensure_room(room)
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM messages WHERE room = ? ORDER BY created_at DESC", (room,)
        ).fetchall()
    return [dict(row) for row in rows]


def add_message(room: str, **message: Any) -> dict[str, Any]:
    with _connect() as connection:
        cursor = connection.execute(
            """INSERT INTO messages(room,call_id,from_phone,caller_name,body,callback_number,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (room, message.get("call_id"), message.get("from_phone"), message.get("caller_name"),
             message.get("body", ""), message.get("callback_number"), _now()),
        )
        row = connection.execute("SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def call_detail(room: str, call_id: str) -> dict[str, Any] | None:
    call = get_call(call_id, room)
    if not call:
        return None
    call["events"] = list_events(call_id)
    call["segments"] = list_segments(call_id)
    return call
