from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any

import requests


def make_signature(timestamp: int | str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


class FeishuClient:
    def __init__(
        self,
        webhook: str,
        secret: str = "",
        timeout: int = 30,
        session: Any | None = None,
    ) -> None:
        self.webhook = webhook
        self.secret = secret
        self.timeout = timeout
        self.session = session or requests.Session()

    def _payload(self, text: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "msg_type": "text",
            "content": {"text": text},
        }
        if self.secret:
            timestamp = int(time.time())
            payload.update(
                {"timestamp": str(timestamp), "sign": make_signature(timestamp, self.secret)}
            )
        return payload

    def send_text(self, text: str) -> None:
        response = self.session.post(
            self.webhook,
            json=self._payload(text),
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError("Feishu returned a non-JSON response") from exc
        code = body.get("code", body.get("StatusCode", 0))
        if code not in (0, "0", None):
            message = body.get("msg") or body.get("StatusMessage") or body
            raise RuntimeError(f"Feishu rejected the message: {message}")

    def test(self) -> None:
        self.send_text("✅ GSIS Notifier 飞书连接测试成功。")
