from gsis_notifier.state import StateStore


def test_state_marks_only_successful_delivery(tmp_path, article, draft):
    state = StateStore(tmp_path / "state.db")
    state.record_discovered(article)
    assert not state.was_sent(article.doi)

    state.mark_generated(article.doi, draft)
    assert not state.was_sent(article.doi)
    assert state.load_unsent()[0].doi == article.doi

    state.mark_sent(article.doi)
    assert state.was_sent(article.doi)
    assert state.load_unsent() == []


def test_metadata_round_trip(tmp_path):
    state = StateStore(tmp_path / "state.db")
    assert state.get_metadata("last_successful_run") is None
    state.set_metadata("last_successful_run", "2026-08-25T00:00:00+00:00")
    assert state.get_metadata("last_successful_run") == "2026-08-25T00:00:00+00:00"
