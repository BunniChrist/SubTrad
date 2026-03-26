from __future__ import annotations

import sqlite3
from pathlib import Path


class RequestCounter:
    def __init__(self, db_path: str, threshold: int = 100) -> None:
        self.threshold = threshold
        self._connection = sqlite3.connect(self._prepare_db_path(db_path))
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS request_counts (
                video_id TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                count INTEGER NOT NULL,
                PRIMARY KEY (video_id, target_lang)
            )
            """
        )
        self._connection.commit()

    def increment(self, video_id: str, target_lang: str) -> int:
        self._connection.execute(
            """
            INSERT INTO request_counts (video_id, target_lang, count)
            VALUES (?, ?, 1)
            ON CONFLICT(video_id, target_lang)
            DO UPDATE SET count = count + 1
            """,
            (video_id, target_lang),
        )
        self._connection.commit()
        return self.get_count(video_id, target_lang)

    def get_count(self, video_id: str, target_lang: str) -> int:
        row = self._connection.execute(
            """
            SELECT count
            FROM request_counts
            WHERE video_id = ? AND target_lang = ?
            """,
            (video_id, target_lang),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def should_cache(self, video_id: str, target_lang: str) -> bool:
        return self.get_count(video_id, target_lang) >= self.threshold

    @staticmethod
    def _prepare_db_path(db_path: str) -> str:
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return db_path
