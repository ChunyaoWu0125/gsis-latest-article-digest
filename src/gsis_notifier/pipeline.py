from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from .formatter import format_digest
from .models import Article, GeneratedDraft, RunSummary

LOGGER = logging.getLogger(__name__)
INITIAL_CUTOFF_DATE = date(2026, 8, 15)


class Pipeline:
    def __init__(
        self,
        collector: object,
        state: object,
        writer: object,
        feishu: object | None,
        lookback_days: int,
        max_articles: int,
        max_message_chars: int,
        output: Callable[[str], None] = print,
    ) -> None:
        self.collector = collector
        self.state = state
        self.writer = writer
        self.feishu = feishu
        self.lookback_days = lookback_days
        self.max_articles = max_articles
        self.max_message_chars = max_message_chars
        self.output = output

    def _since_date(self, today: date) -> date:
        """Never retrieve papers published before the initial cutoff date."""
        lookback_start = today - timedelta(days=self.lookback_days)
        return max(INITIAL_CUTOFF_DATE, lookback_start)

    def _last_successful_date(self) -> date | None:
        stored = self.state.get_metadata("last_successful_run")
        if not stored:
            return None
        try:
            return datetime.fromisoformat(stored).date()
        except ValueError:
            LOGGER.warning("Ignoring invalid last_successful_run value: %s", stored)
            return None

    def run(self, dry_run: bool = False, limit: int | None = None) -> RunSummary:
        started_at = datetime.now(timezone.utc)
        today = started_at.date()
        window_start = self._since_date(today)
        previous_run_date = self._last_successful_date()
        outcome = self.collector.collect(window_start)
        for error in outcome.errors:
            LOGGER.warning("%s", error)
        if not outcome.retrieval_succeeded:
            raise RuntimeError("GSIS discovery failed through Crossref")
        if not outcome.articles and any(
            error.startswith("Pending ") for error in outcome.errors
        ):
            raise RuntimeError(
                "Article candidates were found, but none has a complete verified abstract yet; no digest sent"
            )

        # Persist every fully verified candidate before deduplication. Existing
        # sent rows keep their sent status because record_discovered does not
        # overwrite the status column on DOI conflict.
        for article in outcome.articles:
            self.state.record_discovered(article)

        combined: dict[str, Article] = {
            article.doi: article for article in self.state.load_unsent()
        }
        combined.update({article.doi: article for article in outcome.articles})
        new_articles = [
            article
            for article in combined.values()
            if article.is_summarizable and not self.state.was_sent(article.doi)
        ]
        new_articles.sort(
            key=lambda article: article.published_online or "", reverse=True
        )
        cap = min(limit or self.max_articles, self.max_articles)
        new_articles = new_articles[:cap]

        generated: list[tuple[Article, GeneratedDraft]] = []
        failures = 0
        for article in new_articles:
            try:
                draft = self.writer.generate(article)
                self.state.mark_generated(article.doi, draft)
                generated.append((article, draft))
            except Exception as exc:  # one bad draft must not erase other valid results
                failures += 1
                self.state.mark_failed(article.doi, str(exc))
                LOGGER.exception("Draft generation failed for %s", article.doi)

        if new_articles and not generated:
            raise RuntimeError("All new articles failed draft generation; no digest sent")

        chunks = format_digest(
            generated,
            today,
            self.max_message_chars,
            previous_run_date=previous_run_date,
            window_start=window_start,
        )
        if dry_run:
            for chunk in chunks:
                self.output(chunk)
        else:
            if self.feishu is None:
                raise ValueError("Feishu is not configured")
            # Commit delivery state only after every chunk is accepted by Feishu.
            for chunk in chunks:
                self.feishu.send_text(chunk)
            for article, _ in generated:
                self.state.mark_sent(article.doi)
            self.state.set_metadata("last_successful_run", datetime.now(timezone.utc).isoformat())

        return RunSummary(
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            discovered=len(outcome.articles),
            new_articles=len(new_articles),
            sent_articles=0 if dry_run else len(generated),
            failed_articles=failures,
            dry_run=dry_run,
        )
