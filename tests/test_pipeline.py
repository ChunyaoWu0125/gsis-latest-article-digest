from gsis_notifier.models import CollectionOutcome
from gsis_notifier.pipeline import Pipeline
from gsis_notifier.state import StateStore


class FakeCollector:
    def __init__(self, article):
        self.article = article

    def collect(self, _since):
        return CollectionOutcome([self.article], [], True, False)


class FakeWriter:
    def __init__(self, draft):
        self.draft = draft

    def generate(self, _article):
        return self.draft


class FakeFeishu:
    def __init__(self):
        self.messages = []

    def send_text(self, text):
        self.messages.append(text)


def _pipeline(tmp_path, article, draft, feishu, output=print):
    state = StateStore(tmp_path / "state.db")
    pipeline = Pipeline(
        collector=FakeCollector(article),
        state=state,
        writer=FakeWriter(draft),
        feishu=feishu,
        lookback_days=14,
        max_articles=20,
        max_message_chars=15000,
        output=output,
    )
    return pipeline, state


def test_dry_run_does_not_mark_sent(tmp_path, article, draft):
    output = []
    pipeline, state = _pipeline(tmp_path, article, draft, None, output.append)
    summary = pipeline.run(dry_run=True)
    assert summary.new_articles == 1
    assert not state.was_sent(article.doi)
    assert "[Latest article]" in output[0]


def test_delivery_marks_sent_after_success(tmp_path, article, draft):
    feishu = FakeFeishu()
    pipeline, state = _pipeline(tmp_path, article, draft, feishu)
    summary = pipeline.run()
    assert summary.sent_articles == 1
    assert state.was_sent(article.doi)
    assert len(feishu.messages) == 1
