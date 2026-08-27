from datetime import date

from gsis_notifier.formatter import format_digest


def test_digest_contains_record_and_bilingual_draft(article, draft):
    chunks = format_digest(
        [(article, draft)],
        date(2026, 8, 25),
        previous_run_date=date(2026, 8, 22),
    )
    assert len(chunks) == 1
    assert "上次成功检测：2026年8月22日" in chunks[0]
    assert "共发现 1 篇尚未推送的新论文" in chunks[0]
    assert "摘要：" not in chunks[0]
    assert chunks[0].count(article.link) == 1
    assert "[Latest article] A verified geospatial test article" in chunks[0]
    assert draft.english_intro in chunks[0]
    assert draft.chinese_intro in chunks[0]


def test_empty_digest_is_explicit():
    chunks = format_digest([], date(2026, 8, 25), previous_run_date=date(2026, 8, 22))
    assert "两次检测期间未发现尚未推送的新论文" in chunks[0]


def test_digest_splits_at_limit(article, draft):
    chunks = format_digest([(article, draft), (article, draft)], date(2026, 8, 25), 500)
    assert len(chunks) >= 2
    assert chunks[0].startswith("（1/")
