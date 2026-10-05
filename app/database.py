import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from app.config import DB_PATH
from app.logger import logger
from app.seed_data import (
    SEED_SEGMENTS,
    SEED_SUBSCRIPTIONS,
    SEED_FIELD_REPORTS,
    SEED_LANDSLIDE_HISTORY,
)

@contextmanager
def get_db():
    """
    Context manager providing a SQLite database connection with row dictionary access.
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def create_tables(conn: sqlite3.Connection):
    """
    Creates SQLite schema tables if they do not already exist.
    """
    cursor = conn.cursor()
    
    # 1. Segments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS segments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sequence_order INTEGER NOT NULL,
            start_lat REAL NOT NULL,
            start_lng REAL NOT NULL,
            end_lat REAL NOT NULL,
            end_lng REAL NOT NULL,
            subpoints_json TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            risk_score REAL NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # 2. Subscriptions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone_or_email TEXT NOT NULL,
            segment_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            consent BOOLEAN NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (segment_id) REFERENCES segments(id)
        )
    """)

    # 3. Field reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS field_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            description TEXT NOT NULL,
            photo_url TEXT,
            reporter_name TEXT NOT NULL,
            reporter_ip TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Pending',
            decision_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # 4. Landslide history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS landslide_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            location TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            event_date TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT NOT NULL
        )
    """)

    # --- Backward-compatible column migrations for existing databases ---
    cursor.execute("PRAGMA table_info(subscriptions)")
    sub_cols = [row[1] for row in cursor.fetchall()]
    if "consent" not in sub_cols:
        cursor.execute("ALTER TABLE subscriptions ADD COLUMN consent BOOLEAN NOT NULL DEFAULT 1")

    cursor.execute("PRAGMA table_info(field_reports)")
    fr_cols = [row[1] for row in cursor.fetchall()]
    if "reporter_ip" not in fr_cols:
        cursor.execute("ALTER TABLE field_reports ADD COLUMN reporter_ip TEXT DEFAULT ''")

def seed_database(conn: sqlite3.Connection):
    """
    Seeds initial realistic segments, subscriptions, reports, and history if empty.
    """
    cursor = conn.cursor()
    
    # Check if segments exist
    cursor.execute("SELECT COUNT(*) as count FROM segments")
    if cursor.fetchone()["count"] == 0:
        logger.info("Seeding segments table...")
        for seg in SEED_SEGMENTS:
            cursor.execute("""
                INSERT INTO segments (
                    id, name, sequence_order, start_lat, start_lng,
                    end_lat, end_lng, subpoints_json, risk_level, risk_score, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                seg["id"],
                seg["name"],
                seg["sequence_order"],
                seg["start_lat"],
                seg["start_lng"],
                seg["end_lat"],
                seg["end_lng"],
                json.dumps(seg.get("subpoints", [])),
                seg["risk_level"],
                seg["risk_score"],
                seg["updated_at"]
            ))

    # Check subscriptions
    cursor.execute("SELECT COUNT(*) as count FROM subscriptions")
    if cursor.fetchone()["count"] == 0:
        logger.info("Seeding subscriptions table...")
        for sub in SEED_SUBSCRIPTIONS:
            cursor.execute("""
                INSERT INTO subscriptions (name, phone_or_email, segment_id, channel, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sub["name"],
                sub["phone_or_email"],
                sub["segment_id"],
                sub["channel"],
                sub["created_at"]
            ))

    # Check field reports
    cursor.execute("SELECT COUNT(*) as count FROM field_reports")
    if cursor.fetchone()["count"] == 0:
        logger.info("Seeding field_reports table...")
        for rep in SEED_FIELD_REPORTS:
            cursor.execute("""
                INSERT INTO field_reports (
                    lat, lng, description, photo_url, reporter_name, status, decision_notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rep["lat"],
                rep["lng"],
                rep["description"],
                rep["photo_url"],
                rep["reporter_name"],
                rep["status"],
                rep.get("decision_notes", ""),
                rep["created_at"],
                rep["updated_at"]
            ))

    # Check landslide history
    cursor.execute("SELECT COUNT(*) as count FROM landslide_history")
    if cursor.fetchone()["count"] == 0:
        logger.info("Seeding landslide_history table...")
        for hist in SEED_LANDSLIDE_HISTORY:
            cursor.execute("""
                INSERT INTO landslide_history (title, location, lat, lng, event_date, description, severity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                hist["title"],
                hist["location"],
                hist["lat"],
                hist["lng"],
                hist["event_date"],
                hist["description"],
                hist["severity"]
            ))
    logger.info("Database initialization and seed verification complete.")

def init_db():
    """
    Initializes database tables and verifies seed data.
    """
    with get_db() as conn:
        create_tables(conn)
        seed_database(conn)

def reset_db():
    """
    Drops all tables and re-seeds fresh data.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS landslide_history")
        cursor.execute("DROP TABLE IF EXISTS field_reports")
        cursor.execute("DROP TABLE IF EXISTS subscriptions")
        cursor.execute("DROP TABLE IF EXISTS segments")
        create_tables(conn)
        seed_database(conn)
    logger.info("Database has been completely reset and re-seeded.")
