import base64
import hashlib
import hmac

from gsis_notifier.feishu import FeishuClient, make_signature


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"code": 0, "msg": "success"}


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append((url, json, timeout))
        return FakeResponse()


def test_signature_matches_feishu_algorithm():
    timestamp = 1724544000
    secret = "test-secret"
    expected = base64.b64encode(
        hmac.new(
            f"{timestamp}\n{secret}".encode(), digestmod=hashlib.sha256
        ).digest()
    ).decode()
    assert make_signature(timestamp, secret) == expected


def test_send_text_builds_payload():
    session = FakeSession()
    FeishuClient("https://example.test/hook", "", session=session).send_text("hello")
    _, payload, _ = session.calls[0]
    assert payload == {"msg_type": "text", "content": {"text": "hello"}}
