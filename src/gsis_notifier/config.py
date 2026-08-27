from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    skill_path: Path
    openai_api_key: str
    openai_model: str
    openai_base_url: str | None
    enable_review: bool
    max_generation_attempts: int
    crossref_url: str
    doaj_url: str
    doaj_issn: str
    lookback_days: int
    request_timeout: int
    max_articles_per_run: int
    user_agent: str
    db_path: Path
    log_dir: Path
    feishu_webhook: str
    feishu_secret: str
    feishu_max_message_chars: int

    @classmethod
    def load(cls, project_root: Path | None = None) -> "Settings":
        root = (project_root or Path.cwd()).resolve()
        load_dotenv(root / ".env")

        def resolve_path(name: str, default: str) -> Path:
            value = Path(os.getenv(name, default))
            return value if value.is_absolute() else root / value

        skill_path = root / "SKILL.md"
        if not skill_path.exists():
            raise FileNotFoundError(
                f"SKILL.md not found at {skill_path}. Run the command from the project root."
            )

        settings = cls(
            project_root=root,
            skill_path=skill_path,
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6").strip(),
            openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
            enable_review=_as_bool(os.getenv("OPENAI_ENABLE_REVIEW"), True),
            max_generation_attempts=max(
                1, int(os.getenv("OPENAI_MAX_GENERATION_ATTEMPTS", "3"))
            ),
            crossref_url=os.getenv(
                "GSIS_CROSSREF_URL",
                "https://api.crossref.org/journals/1009-5020/works",
            ).strip(),
            doaj_url=os.getenv(
                "GSIS_DOAJ_URL",
                "https://doaj.org/api/search/articles",
            ).strip(),
            doaj_issn=os.getenv("GSIS_DOAJ_ISSN", "1993-5153").strip(),
            lookback_days=max(1, int(os.getenv("GSIS_LOOKBACK_DAYS", "14"))),
            request_timeout=max(5, int(os.getenv("GSIS_REQUEST_TIMEOUT", "30"))),
            max_articles_per_run=max(
                1, int(os.getenv("GSIS_MAX_ARTICLES_PER_RUN", "20"))
            ),
            user_agent=os.getenv(
                "GSIS_USER_AGENT",
                "GSIS-Notifier/0.2.1 (personal academic monitor)",
            ).strip(),
            db_path=resolve_path("GSIS_DB_PATH", "data/gsis.db"),
            log_dir=resolve_path("GSIS_LOG_DIR", "logs"),
            feishu_webhook=os.getenv("FEISHU_WEBHOOK", "").strip(),
            feishu_secret=os.getenv("FEISHU_SECRET", "").strip(),
            feishu_max_message_chars=max(
                1000, int(os.getenv("FEISHU_MAX_MESSAGE_CHARS", "15000"))
            ),
        )
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        return settings

    def require_model(self) -> None:
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is missing in .env")

    def require_feishu(self) -> None:
        if not self.feishu_webhook:
            raise ValueError("FEISHU_WEBHOOK is missing in .env")
