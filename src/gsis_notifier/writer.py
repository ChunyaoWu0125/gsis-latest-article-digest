from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

from .models import Article, GeneratedDraft, ReviewResult

HASHTAG_RE = re.compile(r"(?<!\w)#([\w\u3400-\u9fff]+)", re.UNICODE)
NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?%?")
LOGGER = logging.getLogger(__name__)


def hashtag_count(text: str) -> int:
    return len(HASHTAG_RE.findall(text))


def validate_draft(draft: GeneratedDraft) -> list[str]:
    issues: list[str] = []
    for language, paragraph in (
        ("English", draft.english_intro),
        ("Chinese", draft.chinese_intro),
    ):
        hashtags = HASHTAG_RE.findall(paragraph)
        count = len(hashtags)
        if not 4 <= count <= 6:
            issues.append(f"{language} paragraph has {count} hashtags; expected 4-6")
        if len({tag.casefold() for tag in hashtags}) != count:
            issues.append(f"{language} paragraph repeats a hashtag")
        if any(line.strip().startswith("#") for line in paragraph.splitlines()[1:]):
            issues.append(f"{language} paragraph contains a separate hashtag line")
    if "#" in draft.emoji or "[Latest article]" in draft.emoji:
        issues.append("emoji field must contain only one relevant emoji")
    return issues


def validate_numeric_grounding(article: Article, draft: GeneratedDraft) -> list[str]:
    """Reject numeric claims that do not occur in the verified source metadata."""
    source = " ".join([article.title, article.abstract, " ".join(article.keywords)])
    source_numbers = set(NUMBER_RE.findall(source))
    draft_numbers = set(
        NUMBER_RE.findall(f"{draft.english_intro} {draft.chinese_intro}")
    )
    unsupported = sorted(draft_numbers - source_numbers)
    return [f"draft contains unsupported numeric value: {value}" for value in unsupported]


class DraftWriter:
    def __init__(
        self,
        api_key: str,
        model: str,
        skill_path: Path,
        base_url: str | None = None,
        enable_review: bool = True,
        max_attempts: int = 3,
        client: Any | None = None,
    ) -> None:
        options: dict[str, Any] = {"api_key": api_key}
        if base_url:
            options["base_url"] = base_url
        self.client = client or OpenAI(**options)
        self.model = model
        self.enable_review = enable_review
        self.max_attempts = max_attempts
        self.skill_text = skill_path.read_text(encoding="utf-8")

    @staticmethod
    def _log_usage(response: Any, stage: str) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            LOGGER.debug("Model usage unavailable for %s", stage)
            return
        LOGGER.info(
            "Model usage [%s]: input=%s output=%s total=%s",
            stage,
            getattr(usage, "input_tokens", "unknown"),
            getattr(usage, "output_tokens", "unknown"),
            getattr(usage, "total_tokens", "unknown"),
        )

    def _generate_once(self, article: Article, feedback: list[str]) -> GeneratedDraft:
        prompt = {
            "task": "Draft bilingual LinkedIn introductions for this one article.",
            "verified_article": article.to_prompt_dict(),
            "requirements": [
                "Use only facts explicitly present in the verified title, abstract, and author keywords.",
                "Do not add a title, link, prefix, hashtag list, citations, or markdown.",
                "Write 2-3 concise sentences in English and the same claims in Chinese.",
                "Each paragraph must contain 4-6 natural inline hashtags.",
                "For English multiword hashtags, replace spaces or hyphens with underscores.",
                "Prefer author keywords; otherwise use concrete phrases explicitly found in the title or abstract.",
                "Choose one relevant emoji. Never imply a result not stated in the abstract.",
            ],
            "feedback_from_previous_attempt": feedback,
        }
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a cautious scientific editor. Follow the bundled skill rules. "
                        "If the source does not support a detail, omit it.\n\n" + self.skill_text
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            text_format=GeneratedDraft,
        )
        self._log_usage(response, "draft-generation")
        draft = response.output_parsed
        if draft is None:
            raise RuntimeError("model returned no parsed draft")
        return draft

    def _review(self, article: Article, draft: GeneratedDraft) -> ReviewResult:
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Audit a bilingual scientific social-media draft against its source. "
                        "Be strict: unsupported details, changed certainty, mismatched languages, "
                        "or hashtag-rule violations must fail the review."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "verified_article": article.to_prompt_dict(),
                            "draft": draft.model_dump(),
                            "rules": {
                                "facts_must_be_source_grounded": True,
                                "languages_must_match": True,
                                "inline_hashtags_per_language": "4-6",
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            text_format=ReviewResult,
        )
        self._log_usage(response, "evidence-review")
        review = response.output_parsed
        if review is None:
            raise RuntimeError("model returned no parsed review")
        return review

    def generate(self, article: Article) -> GeneratedDraft:
        if not article.is_summarizable:
            raise ValueError(f"article {article.doi or article.title!r} has no verified abstract")

        feedback: list[str] = []
        for attempt in range(1, self.max_attempts + 1):
            draft = self._generate_once(article, feedback)
            issues = validate_draft(draft)
            issues.extend(validate_numeric_grounding(article, draft))
            if not issues and self.enable_review:
                review = self._review(article, draft)
                if not (
                    review.all_claims_supported
                    and review.languages_consistent
                    and review.hashtag_rules_satisfied
                ):
                    issues.extend(review.issues or ["independent review failed"])
            if not issues:
                return draft
            feedback = issues
            if attempt == self.max_attempts:
                raise ValueError("draft validation failed: " + "; ".join(issues))
        raise AssertionError("unreachable")
