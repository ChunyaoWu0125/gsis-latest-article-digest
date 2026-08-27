from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import Article, GeneratedDraft


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    doi TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    link TEXT NOT NULL,
                    published_online TEXT,
                    abstract TEXT NOT NULL,
                    keywords_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'discovered',
                    english_intro TEXT,
                    chinese_intro TEXT,
                    emoji TEXT,
                    error TEXT,
                    first_seen_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    sent_at TEXT
                );
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def was_sent(self, doi: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM articles WHERE doi = ? AND status = 'sent'", (doi,)
            ).fetchone()
        return row is not None

    def load_unsent(self) -> list[Article]:
        """Reload cached, verified articles so a temporary model failure is retried."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT doi, title, link, published_online, abstract, keywords_json, source
                FROM articles
                WHERE status != 'sent' AND abstract != ''
                ORDER BY COALESCE(published_online, first_seen_at) DESC
                """
            ).fetchall()
        return [
            Article(
                doi=str(row["doi"]),
                title=str(row["title"]),
                link=str(row["link"]),
                published_online=row["published_online"],
                abstract=str(row["abstract"]),
                keywords=json.loads(row["keywords_json"]),
                source=str(row["source"]),
            )
            for row in rows
        ]

    def record_discovered(self, article: Article) -> None:
        now = _now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO articles (
                    doi, title, link, published_online, abstract, keywords_json,
                    source, status, first_seen_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'discovered', ?, ?)
                ON CONFLICT(doi) DO UPDATE SET
                    title = excluded.title,
                    link = excluded.link,
                    published_online = excluded.published_online,
                    abstract = excluded.abstract,
                    keywords_json = excluded.keywords_json,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (
                    article.doi,
                    article.title,
                    article.link,
                    article.published_online,
                    article.abstract,
                    json.dumps(article.keywords, ensure_ascii=False),
                    article.source,
                    now,
                    now,
                ),
            )

    def mark_generated(self, doi: str, draft: GeneratedDraft) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE articles
                SET status = 'generated', emoji = ?, english_intro = ?,
                    chinese_intro = ?, error = NULL, updated_at = ?
                WHERE doi = ?
                """,
                (draft.emoji, draft.english_intro, draft.chinese_intro, _now(), doi),
            )

    def mark_failed(self, doi: str, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE articles SET status = 'failed', error = ?, updated_at = ?
                WHERE doi = ?
                """,
                (error[:4000], _now(), doi),
            )

    def mark_sent(self, doi: str) -> None:
        now = _now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE articles
                SET status = 'sent', sent_at = ?, updated_at = ?, error = NULL
                WHERE doi = ?
                """,
                (now, now, doi),
            )

    def get_metadata(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = ?", (key,)
            ).fetchone()
        return str(row["value"]) if row else None

    def set_metadata(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO metadata (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
