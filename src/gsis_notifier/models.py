from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


@dataclass(slots=True)
class Article:
    doi: str
    title: str
    link: str
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    published_online: str | None = None
    source: str = "tandfonline"

    @property
    def is_summarizable(self) -> bool:
        return bool(self.doi and self.title and self.abstract and self.link)

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "doi": self.doi,
            "title": self.title,
            "link": self.link,
            "published_online": self.published_online or "Not provided",
            "abstract": self.abstract,
            "author_keywords": self.keywords,
        }


@dataclass(slots=True)
class CollectionOutcome:
    articles: list[Article]
    errors: list[str]
    crossref_source_succeeded: bool
    doaj_source_succeeded: bool

    @property
    def retrieval_succeeded(self) -> bool:
        # Crossref is the authoritative discovery/date source. DOAJ enriches
        # those DOI records with abstracts and author-provided keywords.
        return self.crossref_source_succeeded


class GeneratedDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emoji: str = Field(min_length=1, max_length=8)
    english_intro: str = Field(min_length=20)
    chinese_intro: str = Field(min_length=10)


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    all_claims_supported: bool
    languages_consistent: bool
    hashtag_rules_satisfied: bool
    issues: list[str] = Field(default_factory=list)


@dataclass(slots=True)
class RunSummary:
    started_at: datetime
    finished_at: datetime
    discovered: int
    new_articles: int
    sent_articles: int
    failed_articles: int
    dry_run: bool
