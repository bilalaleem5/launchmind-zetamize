"""
===============================================================
  AI SALES SYSTEM — Database Layer
  SQLite schema + all CRUD operations
===============================================================
"""

import sqlite3
import os
from datetime import datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    # ── Leads ──────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT,
        company     TEXT NOT NULL,
        email       TEXT,
        phone       TEXT,
        website     TEXT,
        address     TEXT,
        industry    TEXT,
        city        TEXT,
        source      TEXT,           -- 'google_maps' | 'manual' | 'linkedin' etc.
        mode        TEXT DEFAULT 'automation',  -- 'automation' | 'product'
        product_id  INTEGER,        -- FK to products table (if mode=product)
        status      TEXT DEFAULT 'new',
        -- new | researched | contacted | replied | meeting_booked | closed_won | closed_lost | cold
        fit_score   INTEGER DEFAULT 0,   -- 1-10
        pain_points TEXT,               -- JSON array
        research    TEXT,               -- JSON: full AI research result
        notes       TEXT,
        email_valid INTEGER DEFAULT 0,  -- 0/1
        wa_valid    INTEGER DEFAULT 0,  -- 0/1 WhatsApp valid
        created_at  TEXT DEFAULT (datetime('now')),
        updated_at  TEXT DEFAULT (datetime('now'))
    )""")

    # ── Products (for product mode) ────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        description TEXT,
        features    TEXT,            -- JSON array of feature strings
        target_audience TEXT,
        price_range TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    )""")

    # ── Outreach Log ────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS outreach (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id     INTEGER NOT NULL,
        channel     TEXT NOT NULL,  -- 'email' | 'whatsapp'
        subject     TEXT,
        message     TEXT NOT NULL,
        status      TEXT DEFAULT 'sent',  -- 'sent' | 'failed' | 'replied'
        sent_at     TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (lead_id) REFERENCES leads(id)
    )""")

    # ── Follow-ups ──────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS followups (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id         INTEGER NOT NULL,
        channel         TEXT NOT NULL,
        message         TEXT,
        scheduled_at    TEXT NOT NULL,
        done            INTEGER DEFAULT 0,
        attempt_number  INTEGER DEFAULT 1,
        done_at         TEXT,
        FOREIGN KEY (lead_id) REFERENCES leads(id)
    )""")

    # ── Deals / Pipeline ────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS deals (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id     INTEGER UNIQUE NOT NULL,
        stage       TEXT DEFAULT 'new',
        -- new | contacted | replied | meeting_booked | closed_won | closed_lost
        value       REAL,
        notes       TEXT,
        meeting_at  TEXT,
        closed_at   TEXT,
        created_at  TEXT DEFAULT (datetime('now')),
        updated_at  TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (lead_id) REFERENCES leads(id)
    )""")

    # ── System Log ──────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS system_log (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        level     TEXT DEFAULT 'info',
        agent     TEXT,
        message   TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    # ── Sessions (Phase 1: Recovery) ─────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        industry          TEXT,
        city              TEXT,
        max_leads         INTEGER,
        status            TEXT DEFAULT 'running', -- running | completed | interrupted
        current_step      TEXT, -- 'scraping' | 'researching' | 'outreach'
        current_lead_idx  INTEGER DEFAULT 0,
        total_leads_found INTEGER DEFAULT 0,
        blueprint         TEXT, -- JSON: AI-generated campaign roadmap
        created_at        TEXT DEFAULT (datetime('now')),
        updated_at        TEXT DEFAULT (datetime('now'))
    )""")

    conn.commit()
    conn.close()
    print(f"✅ Database initialized at: {DB_PATH}")


# ── Lead Operations ─────────────────────────────────────────────

def insert_lead(data: dict) -> int:
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM leads WHERE company=? AND (email=? OR phone=?)",
        (data.get('company',''), data.get('email',''), data.get('phone',''))
    ).fetchone()
    if existing:
        conn.close()
        return -1  # duplicate

    c = conn.execute("""
        INSERT INTO leads (name,company,email,phone,website,address,industry,city,source,mode,product_id)
        VALUES (:name,:company,:email,:phone,:website,:address,:industry,:city,:source,:mode,:product_id)
    """, {
        'name': data.get('name',''),
        'company': data.get('company',''),
        'email': data.get('email',''),
        'phone': data.get('phone',''),
        'website': data.get('website',''),
        'address': data.get('address',''),
        'industry': data.get('industry',''),
        'city': data.get('city',''),
        'source': data.get('source','manual'),
        'mode': data.get('mode','automation'),
        'product_id': data.get('product_id', None),
    })
    lead_id = c.lastrowid
    # Auto-create deal entry
    conn.execute("INSERT OR IGNORE INTO deals (lead_id) VALUES (?)", (lead_id,))
    conn.commit()
    conn.close()
    return lead_id


def update_lead(lead_id: int, **kwargs):
    kwargs['updated_at'] = datetime.now().isoformat()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [lead_id]
    conn = get_conn()
    conn.execute(f"UPDATE leads SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def get_lead(lead_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_leads(status=None, mode=None, product_id=None, limit=100) -> list[dict]:
    conn = get_conn()
    query = "SELECT l.*, d.stage FROM leads l LEFT JOIN deals d ON l.id=d.lead_id WHERE 1=1"
    params = []
    if status:
        query += " AND l.status=?"
        params.append(status)
    if mode:
        query += " AND l.mode=?"
        params.append(mode)
    if product_id:
        query += " AND l.product_id=?"
        params.append(product_id)
    query += " ORDER BY l.created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_leads_needing_followup(days=3) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT l.* FROM leads l
        WHERE l.status = 'contacted'
        AND NOT EXISTS (
            SELECT 1 FROM followups f
            WHERE f.lead_id=l.id AND f.done=0
        )
        AND datetime(l.updated_at) <= datetime('now', ?)
    """, (f'-{days} days',)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Product Operations ─────────────────────────────────────────

def insert_product(data: dict) -> int:
    import json
    conn = get_conn()
    c = conn.execute("""
        INSERT INTO products (name,description,features,target_audience,price_range)
        VALUES (?,?,?,?,?)
    """, (
        data['name'],
        data.get('description',''),
        json.dumps(data.get('features',[])),
        data.get('target_audience',''),
        data.get('price_range',''),
    ))
    pid = c.lastrowid
    conn.commit()
    conn.close()
    return pid


def get_products() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product(product_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Outreach Operations ─────────────────────────────────────────

def log_outreach(lead_id: int, channel: str, message: str, subject: str = '', status: str = 'sent'):
    conn = get_conn()
    conn.execute("""
        INSERT INTO outreach (lead_id,channel,subject,message,status)
        VALUES (?,?,?,?,?)
    """, (lead_id, channel, subject, message, status))
    conn.commit()
    conn.close()


def get_outreach(lead_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM outreach WHERE lead_id=? ORDER BY sent_at DESC", (lead_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Follow-up Operations ────────────────────────────────────────

def schedule_followup(lead_id: int, channel: str, scheduled_at: str, attempt: int = 1):
    conn = get_conn()
    conn.execute("""
        INSERT INTO followups (lead_id,channel,scheduled_at,attempt_number)
        VALUES (?,?,?,?)
    """, (lead_id, channel, scheduled_at, attempt))
    conn.commit()
    conn.close()


def get_due_followups() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT f.*, l.email, l.phone, l.company, l.name, l.status
        FROM followups f JOIN leads l ON f.lead_id=l.id
        WHERE f.done=0 AND datetime(f.scheduled_at) <= datetime('now')
        ORDER BY f.scheduled_at ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_followup_done(followup_id: int):
    conn = get_conn()
    conn.execute(
        "UPDATE followups SET done=1, done_at=datetime('now') WHERE id=?", (followup_id,)
    )
    conn.commit()
    conn.close()


def get_followups_for_lead(lead_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM followups WHERE lead_id=? ORDER BY scheduled_at DESC", (lead_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Deal / Pipeline Operations ──────────────────────────────────

def update_deal_stage(lead_id: int, stage: str, notes: str = None, meeting_at: str = None):
    conn = get_conn()
    updates = {"stage": stage, "updated_at": datetime.now().isoformat()}
    if notes:
        updates["notes"] = notes
    if meeting_at:
        updates["meeting_at"] = meeting_at
    if stage in ('closed_won', 'closed_lost'):
        updates["closed_at"] = datetime.now().isoformat()
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [lead_id]
    conn.execute(f"UPDATE deals SET {sets} WHERE lead_id=?", vals)
    conn.commit()
    conn.close()


def get_pipeline_stats() -> dict:
    conn = get_conn()
    stages = ['new','contacted','replied','meeting_booked','closed_won','closed_lost','cold']
    stats = {}
    for s in stages:
        row = conn.execute("SELECT COUNT(*) as cnt FROM deals WHERE stage=?", (s,)).fetchone()
        stats[s] = row['cnt']
    total = conn.execute("SELECT COUNT(*) as cnt FROM leads").fetchone()['cnt']
    emails = conn.execute("SELECT COUNT(*) as cnt FROM outreach WHERE channel='email'").fetchone()['cnt']
    wa = conn.execute("SELECT COUNT(*) as cnt FROM outreach WHERE channel='whatsapp'").fetchone()['cnt']
    conn.close()
    return {**stats, 'total_leads': total, 'emails_sent': emails, 'wa_sent': wa}


# ── System Log ──────────────────────────────────────────────────

def syslog(agent: str, message: str, level: str = 'info'):
    print(f"[{level.upper()}][{agent}] {message}")
    conn = get_conn()
    conn.execute(
        "INSERT INTO system_log (level,agent,message) VALUES (?,?,?)",
        (level, agent, message)
    )
    conn.commit()
    conn.close()


def get_system_logs(limit=100) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM system_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Session Operations (Phase 1) ────────────────────────────────

def start_session(industry, city, max_leads) -> int:
    conn = get_conn()
    c = conn.execute("""
        INSERT INTO sessions (industry, city, max_leads, status, current_step)
        VALUES (?, ?, ?, 'running', 'initializing')
    """, (industry, city, max_leads))
    sid = c.lastrowid
    conn.commit()
    conn.close()
    return sid

def update_session(session_id, **kwargs):
    kwargs['updated_at'] = datetime.now().isoformat()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [session_id]
    conn = get_conn()
    conn.execute(f"UPDATE sessions SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()

def get_active_session() -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE status='running' ORDER BY created_at DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def get_sessions(limit=50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
