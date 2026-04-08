"""
Message Bus — SQLite-backed inter-agent messaging system.
Assignment requirement: structured JSON messages between agents.
"""
import sqlite3
import uuid
import json
from datetime import datetime, timezone
import os

from agents.ui_utils import print_message, console
from rich.table import Table
from rich.box import ROUNDED

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "agent_messages.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_message_bus():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL UNIQUE,
            from_agent TEXT NOT NULL,
            to_agent   TEXT NOT NULL,
            message_type TEXT NOT NULL,  -- task | result | revision_request | confirmation
            payload    TEXT NOT NULL,    -- JSON string
            timestamp  TEXT NOT NULL,
            parent_message_id TEXT,
            read       INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    print("[MessageBus] Initialized ✅")


def send_message(from_agent: str, to_agent: str, message_type: str,
                 payload: dict, parent_message_id: str = None) -> str:
    """Send a structured JSON message from one agent to another."""
    message_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    msg = {
        "message_id": message_id,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "message_type": message_type,
        "payload": payload,
        "timestamp": timestamp,
        "parent_message_id": parent_message_id
    }

    conn = _get_conn()
    conn.execute("""
        INSERT INTO agent_messages 
        (message_id, from_agent, to_agent, message_type, payload, timestamp, parent_message_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        message_id, from_agent, to_agent, message_type,
        json.dumps(payload), timestamp, parent_message_id
    ))
    conn.commit()
    conn.close()

    # Beautiful UI output
    print_message(from_agent, to_agent, message_type, payload)

    return message_id


def get_messages(to_agent: str, unread_only: bool = True) -> list[dict]:
    """Get all messages addressed to a specific agent."""
    conn = _get_conn()
    if unread_only:
        rows = conn.execute(
            "SELECT * FROM agent_messages WHERE to_agent=? AND read=0 ORDER BY id ASC",
            (to_agent,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM agent_messages WHERE to_agent=? ORDER BY id ASC",
            (to_agent,)
        ).fetchall()

    messages = []
    for row in rows:
        msg = dict(row)
        msg["payload"] = json.loads(msg["payload"])
        messages.append(msg)

    # Mark as read
    if unread_only and rows:
        ids = [r["id"] for r in rows]
        conn.execute(f"UPDATE agent_messages SET read=1 WHERE id IN ({','.join('?'*len(ids))})", ids)
        conn.commit()

    conn.close()
    return messages


def get_latest_message(to_agent: str, message_type: str = None) -> dict | None:
    """Get the most recent message for an agent, optionally filtered by type."""
    conn = _get_conn()
    if message_type:
        row = conn.execute(
            "SELECT * FROM agent_messages WHERE to_agent=? AND message_type=? ORDER BY id DESC LIMIT 1",
            (to_agent, message_type)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM agent_messages WHERE to_agent=? ORDER BY id DESC LIMIT 1",
            (to_agent,)
        ).fetchone()
    conn.close()
    if row:
        msg = dict(row)
        msg["payload"] = json.loads(msg["payload"])
        return msg
    return None


def get_all_messages() -> list[dict]:
    """Get the full message log — for demo/evaluator visibility."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM agent_messages ORDER BY id ASC").fetchall()
    conn.close()
    messages = []
    for row in rows:
        msg = dict(row)
        msg["payload"] = json.loads(msg["payload"])
        messages.append(msg)
    return messages


def print_full_message_log():
    """Print the entire agent message log in a beautiful table."""
    table = Table(title="📋 FULL AGENT MESSAGE LOG", box=ROUNDED, header_style="bold magenta")
    table.add_column("Time", style="dim cyan")
    table.add_column("From ➔ To", style="bold white")
    table.add_column("Type", style="yellow")
    table.add_column("Payload Summary", style="italic white")

    for msg in get_all_messages():
        # Truncate payload for clean table view
        payload_str = json.dumps(msg['payload'])
        if len(payload_str) > 60:
            payload_str = payload_str[:57] + "..."
            
        table.add_row(
            msg['timestamp'].split('T')[1].split('.')[0], # HH:MM:SS
            f"{msg['from_agent'].upper()} ➔ {msg['to_agent'].upper()}",
            msg['message_type'].upper(),
            payload_str
        )
    
    console.print("\n")
    console.print(table)
    console.print("\n")
