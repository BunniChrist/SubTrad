from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SubtitleCache:
    def __init__(self, db_path: str) -> None:
        self._connection = sqlite3.connect(self._prepare_db_path(db_path))
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS subtitle_cache (
                video_id TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                subtitles_json TEXT NOT NULL,
                platform TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL,
                detected_language TEXT,
                source TEXT NOT NULL,
                needs_transcription INTEGER NOT NULL DEFAULT 0,
                translation_status TEXT NOT NULL DEFAULT 'translated',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (video_id, target_lang)
            )
            """
        )
        self._connection.commit()

    def store(self, video_id: str, target_lang: str, response_data: dict[str, Any]) -> None:
        self._connection.execute(
            """
            INSERT INTO subtitle_cache (
                video_id,
                target_lang,
                subtitles_json,
                platform,
                duration_seconds,
                detected_language,
                source,
                needs_transcription,
                translation_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id, target_lang)
            DO UPDATE SET
                subtitles_json = excluded.subtitles_json,
                platform = excluded.platform,
                duration_seconds = excluded.duration_seconds,
                detected_language = excluded.detected_language,
                source = excluded.source,
                needs_transcription = excluded.needs_transcription,
                translation_status = excluded.translation_status,
                created_at = CURRENT_TIMESTAMP
            """,
            (
                video_id,
                target_lang,
                json.dumps(response_data["subtitles"]),
                response_data["platform"],
                response_data["duration_seconds"],
                response_data.get("detected_language"),
                response_data["source"],
                int(bool(response_data.get("needs_transcription", False))),
                response_data.get("translation_status", "translated"),
            ),
        )
        self._connection.commit()

    def retrieve(self, video_id: str, target_lang: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            """
            SELECT
                video_id,
                target_lang,
                subtitles_json,
                platform,
                duration_seconds,
                detected_language,
                source,
                needs_transcription,
                translation_status
            FROM subtitle_cache
            WHERE video_id = ? AND target_lang = ?
            """,
            (video_id, target_lang),
        ).fetchone()
        if row is None:
            return None

        return {
            "platform": row["platform"],
            "video_id": row["video_id"],
            "subtitles": json.loads(row["subtitles_json"]),
            "duration_seconds": row["duration_seconds"],
            "needs_transcription": bool(row["needs_transcription"]),
            "source": row["source"],
            "target_lang": row["target_lang"],
            "detected_language": row["detected_language"],
            "translation_status": row["translation_status"],
        }

    def exists(self, video_id: str, target_lang: str) -> bool:
        row = self._connection.execute(
            """
            SELECT 1
            FROM subtitle_cache
            WHERE video_id = ? AND target_lang = ?
            """,
            (video_id, target_lang),
        ).fetchone()
        return row is not None

    @staticmethod
    def _prepare_db_path(db_path: str) -> str:
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return db_path
