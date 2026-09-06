"""Small SQLite persistence layer for Eufisky rooms and calls."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

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
    redacted_transcript TEXT, entities_json TEXT, redacted_audio TEXT,
    analysis_source TEXT NOT NULL DEFAULT 'template', created_at TEXT NOT NULL,
    FOREIGN KEY(call_id) REFERENCES calls(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_incidents_call ON incidents(call_id);
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
        _ensure_column(connection, "incidents", "redacted_audio", "TEXT")
        _ensure_column(
            connection,
            "incidents",
            "analysis_source",
            "TEXT NOT NULL DEFAULT 'template'",
        )
    ensure_room("demo")
    # Phase seed additions also appear for an existing local demo database.
    with _connect() as connection:
        _seed_room(connection, "demo", contacts=False)


def _ensure_column(
    connection: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    columns = {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _seed_data() -> dict[str, Any]:
    if not SEED_PATH.exists():
        return {}
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _seed_call_id(room: str, key: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"eufisky:{room}:{key}").hex


def _seed_room(
    connection: sqlite3.Connection, room: str, *, contacts: bool = True
) -> None:
    data = _seed_data()
    if contacts:
        for contact in data.get("contacts", []):
            present = connection.execute(
                "SELECT 1 FROM contacts WHERE room = ? AND phone = ? LIMIT 1",
                (room, contact["phone"]),
            ).fetchone()
            if present:
                continue
            connection.execute(
                """INSERT INTO contacts(room, phone, label, status, source, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    room,
                    contact["phone"],
                    contact["label"],
                    contact.get("status", "pending"),
                    contact.get("source", "seed"),
                    _now(),
                ),
            )

    for item in data.get("incidents", []):
        key = str(item.get("key") or "incident")
        call_id = _seed_call_id(room, key)
        call = item.get("call") or {}
        cursor = connection.execute(
            """INSERT OR IGNORE INTO calls(
                   id, room, from_phone, from_label, classification, started_at,
                   ended_at, final_state, peak_risk, front_door_outcome,
                   guardian_outcome, recording_caller, recording_senior
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
            (
                call_id,
                room,
                call.get("from_phone"),
                call.get("from_label"),
                call.get("classification", "unknown"),
                call.get("started_at") or _now(),
                call.get("ended_at") or call.get("started_at") or _now(),
                call.get("final_state", "WRAPUP"),
                int(call.get("peak_risk") or 0),
                call.get("front_door_outcome"),
                call.get("guardian_outcome"),
            ),
        )
        is_new = cursor.rowcount > 0
        connection.execute(
            """INSERT OR IGNORE INTO incidents(
                   call_id, summary_json, redacted_transcript, entities_json,
                   redacted_audio, analysis_source, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                call_id,
                json.dumps(item.get("summary") or {}),
                str(item.get("redacted_transcript") or ""),
                json.dumps(item.get("analytics") or {}),
                item.get("redacted_audio"),
                str(item.get("analysis_source") or "lemur"),
                str(item.get("created_at") or call.get("ended_at") or _now()),
            ),
        )
        if not is_new:
            continue
        for sample in item.get("risk_samples", []):
            connection.execute(
                """INSERT INTO risk_samples(call_id,t_ms,score,signals_json)
                   VALUES (?,?,?,?)""",
                (
                    call_id,
                    int(sample.get("t_ms") or 0),
                    int(sample.get("score") or 0),
                    json.dumps(sample.get("signals") or []),
                ),
            )
        for event in item.get("events", []):
            payload = {key: value for key, value in event.items() if key != "t_ms"}
            connection.execute(
                """INSERT INTO call_events(call_id,t_ms,type,payload_json)
                   VALUES (?,?,?,?)""",
                (
                    call_id,
                    int(event.get("t_ms") or 0),
                    str(event.get("type") or "state"),
                    json.dumps(payload),
                ),
            )

    for message in data.get("messages", []):
        present = connection.execute(
            """SELECT 1 FROM messages
               WHERE room = ? AND caller_name = ? AND body = ? LIMIT 1""",
            (room, message.get("caller_name"), message.get("body", "")),
        ).fetchone()
        if present:
            continue
        connection.execute(
            """INSERT INTO messages(
                   room,call_id,from_phone,caller_name,body,callback_number,created_at
               ) VALUES (?,?,?,?,?,?,?)""",
            (
                room,
                None,
                message.get("from_phone"),
                message.get("caller_name"),
                message.get("body", ""),
                message.get("callback_number"),
                message.get("created_at") or _now(),
            ),
        )


def ensure_room(room: str) -> str:
    """Copy all demo seed data into a room the first time it is seen."""
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
            _seed_room(connection, room)
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
    calls = [dict(row) for row in rows]
    for call in calls:
        call["incident"] = get_incident(str(call["id"]))
    return calls


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


def add_risk_sample(
    call_id: str, t_ms: int, score: int, signals: list[str]
) -> dict[str, Any]:
    """Persist one live score and monotonically update the call peak."""

    score = max(0, min(100, int(score)))
    with _connect() as connection:
        connection.execute(
            "INSERT INTO risk_samples(call_id,t_ms,score,signals_json) VALUES (?,?,?,?)",
            (call_id, t_ms, score, json.dumps(signals)),
        )
        connection.execute(
            "UPDATE calls SET peak_risk = MAX(peak_risk, ?) WHERE id = ?",
            (score, call_id),
        )
    return {"call_id": call_id, "t_ms": t_ms, "score": score, "signals": signals}


def list_risk_samples(call_id: str) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM risk_samples WHERE call_id = ? ORDER BY t_ms", (call_id,)
        ).fetchall()
    samples: list[dict[str, Any]] = []
    for row in rows:
        sample = dict(row)
        sample["signals"] = json.loads(sample.pop("signals_json"))
        samples.append(sample)
    return samples


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
    events: list[dict[str, Any]] = []
    for row in rows:
        event = dict(row)
        try:
            event["payload"] = json.loads(event.get("payload_json") or "{}")
        except json.JSONDecodeError:
            event["payload"] = {}
        events.append(event)
    return events


def add_incident(
    call_id: str,
    summary: dict[str, Any],
    redacted_transcript: str,
    analytics: dict[str, Any] | None = None,
    redacted_audio: str | None = None,
    analysis_source: str = "template",
) -> dict[str, Any]:
    with _connect() as connection:
        connection.execute(
            """INSERT INTO incidents(
                   call_id,summary_json,redacted_transcript,entities_json,
                   redacted_audio,analysis_source,created_at
               ) VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(call_id) DO UPDATE SET
                   summary_json=excluded.summary_json,
                   redacted_transcript=excluded.redacted_transcript,
                   entities_json=excluded.entities_json,
                   redacted_audio=excluded.redacted_audio,
                   analysis_source=excluded.analysis_source,
                   created_at=excluded.created_at""",
            (
                call_id,
                json.dumps(summary),
                redacted_transcript,
                json.dumps(analytics or {}),
                redacted_audio,
                analysis_source,
                _now(),
            ),
        )
    return get_incident(call_id) or {}


def get_incident(call_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM incidents WHERE call_id = ? ORDER BY id DESC LIMIT 1",
            (call_id,),
        ).fetchone()
    if not row:
        return None
    incident = dict(row)
    for source, target, fallback in (
        ("summary_json", "summary", {}),
        ("entities_json", "analytics", {}),
    ):
        try:
            incident[target] = json.loads(incident.get(source) or "{}")
        except json.JSONDecodeError:
            incident[target] = fallback
    return incident


def db_health() -> bool:
    try:
        with _connect() as connection:
            return connection.execute("SELECT 1").fetchone()[0] == 1
    except sqlite3.Error:
        return False


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
    call["samples"] = list_risk_samples(call_id)
    call["segments"] = list_segments(call_id)
    call["incident"] = get_incident(call_id)
    return call
