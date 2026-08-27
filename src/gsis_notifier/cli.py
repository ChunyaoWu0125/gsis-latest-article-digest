from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .collector import GSISCollector
from .config import Settings
from .feishu import FeishuClient
from .pipeline import Pipeline
from .state import StateStore
from .writer import DraftWriter


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gsis-notifier",
        description="Find new GSIS papers, draft bilingual LinkedIn copy, and notify Feishu.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="directory containing SKILL.md and .env (default: current directory)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print without sending")
    parser.add_argument("--limit", type=int, help="maximum articles for this run")
    parser.add_argument(
        "--test-feishu", action="store_true", help="send one connection-test message only"
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def _configure_logging(settings: Settings, verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)
    file_handler = logging.FileHandler(settings.log_dir / "gsis-notifier.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = Settings.load(args.project_root)
        _configure_logging(settings, args.verbose)

        if args.test_feishu:
            settings.require_feishu()
            FeishuClient(
                settings.feishu_webhook,
                settings.feishu_secret,
                settings.request_timeout,
            ).test()
            print("Feishu test message accepted.")
            return 0

        settings.require_model()
        collector = GSISCollector(
            crossref_url=settings.crossref_url,
            doaj_url=settings.doaj_url,
            doaj_issn=settings.doaj_issn,
            timeout=settings.request_timeout,
            user_agent=settings.user_agent,
        )
        state = StateStore(settings.db_path)
        writer = DraftWriter(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            skill_path=settings.skill_path,
            base_url=settings.openai_base_url,
            enable_review=settings.enable_review,
            max_attempts=settings.max_generation_attempts,
        )
        feishu = None
        if not args.dry_run:
            settings.require_feishu()
            feishu = FeishuClient(
                settings.feishu_webhook,
                settings.feishu_secret,
                settings.request_timeout,
            )
        summary = Pipeline(
            collector=collector,
            state=state,
            writer=writer,
            feishu=feishu,
            lookback_days=settings.lookback_days,
            max_articles=settings.max_articles_per_run,
            max_message_chars=settings.feishu_max_message_chars,
        ).run(dry_run=args.dry_run, limit=args.limit)
        logging.getLogger(__name__).info(
            "Finished: discovered=%d new=%d sent=%d failed=%d dry_run=%s",
            summary.discovered,
            summary.new_articles,
            summary.sent_articles,
            summary.failed_articles,
            summary.dry_run,
        )
        return 0
    except Exception as exc:
        logging.getLogger(__name__).exception("Run failed: %s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
