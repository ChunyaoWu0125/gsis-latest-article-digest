from types import SimpleNamespace

import pytest

from gsis_notifier.models import GeneratedDraft, ReviewResult
from gsis_notifier.writer import (
    DraftWriter,
    hashtag_count,
    validate_draft,
    validate_numeric_grounding,
)


class FakeResponses:
    def __init__(self, parsed_values):
        self.parsed_values = iter(parsed_values)

    def parse(self, **_kwargs):
        return SimpleNamespace(output_parsed=next(self.parsed_values))


class FakeClient:
    def __init__(self, parsed_values):
        self.responses = FakeResponses(parsed_values)


def test_validate_hashtags(draft):
    assert hashtag_count(draft.english_intro) == 4
    assert hashtag_count(draft.chinese_intro) == 4
    assert validate_draft(draft) == []


def test_invalid_hashtag_count():
    draft = GeneratedDraft(
        emoji="🛰️",
        english_intro="A sufficiently long paragraph with only #one hashtag.",
        chinese_intro="这是一个足够长但只有 #一个 标签的中文段落。",
    )
    assert len(validate_draft(draft)) == 2


def test_writer_accepts_generated_and_reviewed_draft(tmp_path, article, draft):
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("Use only verified facts.", encoding="utf-8")
    client = FakeClient(
        [
            draft,
            ReviewResult(
                all_claims_supported=True,
                languages_consistent=True,
                hashtag_rules_satisfied=True,
                issues=[],
            ),
        ]
    )
    writer = DraftWriter(
        api_key="test",
        model="test-model",
        skill_path=skill_path,
        client=client,
    )
    assert writer.generate(article) == draft


def test_writer_rejects_missing_abstract(tmp_path, article):
    article.abstract = ""
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("rules", encoding="utf-8")
    writer = DraftWriter(
        api_key="test", model="test", skill_path=skill_path, client=FakeClient([])
    )
    with pytest.raises(ValueError, match="verified abstract"):
        writer.generate(article)


def test_numeric_grounding_rejects_invented_number(article, draft):
    draft.english_intro += " Accuracy reached 99.9%."
    assert validate_numeric_grounding(article, draft) == [
        "draft contains unsupported numeric value: 99.9%"
    ]
