from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "leads.db"


class LeadStore:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._connection = self._connect(db_path)
        self._initialize()

    @staticmethod
    def _connect(db_path: str | Path) -> sqlite3.Connection:
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL,
                    type TEXT NOT NULL,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_email_type
                ON leads(email, type)
                """
            )
            self._connection.commit()

    def save_lead(self, email: str, lead_type: str, message: str | None = None) -> int:
        with self._lock:
            existing_id = self._get_existing_id(email, lead_type)
            if existing_id is not None:
                return existing_id

            cursor = self._connection.execute(
                "INSERT INTO leads(email, type, message) VALUES (?, ?, ?)",
                (email.strip().lower(), lead_type, message),
            )
            self._connection.commit()
            return int(cursor.lastrowid)

    def get_lead_count(self, lead_type: str) -> int:
        with self._lock:
            cursor = self._connection.execute(
                "SELECT COUNT(*) AS count FROM leads WHERE type = ?",
                (lead_type,),
            )
            row = cursor.fetchone()
            return int(row["count"]) if row is not None else 0

    def lead_exists(self, email: str, lead_type: str) -> bool:
        with self._lock:
            return self._get_existing_id(email, lead_type) is not None

    def _get_existing_id(self, email: str, lead_type: str) -> int | None:
        cursor = self._connection.execute(
            "SELECT id FROM leads WHERE email = ? AND type = ?",
            (email.strip().lower(), lead_type),
        )
        row = cursor.fetchone()
        return int(row["id"]) if row is not None else None
