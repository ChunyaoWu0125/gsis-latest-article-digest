from __future__ import annotations

from datetime import date

from .models import Article, GeneratedDraft


def format_article(article: Article, draft: GeneratedDraft) -> str:
    online_date = article.published_online or "Not provided"
    return (
        f"【新增论文】\n"
        f"标题：{article.title}\n"
        f"在线发表：{online_date}\n\n"
        f"【LinkedIn 中英文草稿】\n"
        f"{draft.emoji} [Latest article] {article.title}\n\n"
        f"{article.link}\n\n"
        f"{draft.english_intro}\n\n"
        f"{draft.chinese_intro}"
    )


def _split_long_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = max_chars
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    return chunks


def format_digest(
    items: list[tuple[Article, GeneratedDraft]],
    run_date: date,
    max_chars: int = 15000,
    previous_run_date: date | None = None,
    window_start: date | None = None,
) -> list[str]:
    def chinese_date(value: date) -> str:
        return f"{value.year}年{value.month}月{value.day}日"

    header_lines = [f"📚 GSIS 新文章监测｜{chinese_date(run_date)}"]
    if previous_run_date:
        header_lines.append(f"上次成功检测：{chinese_date(previous_run_date)}")
    elif window_start:
        header_lines.append(
            f"首次检测回溯范围：{chinese_date(window_start)}—{chinese_date(run_date)}"
        )

    if not items:
        header_lines.append("两次检测期间未发现尚未推送的新论文。")
        return ["\n".join(header_lines)]

    if previous_run_date:
        header_lines.append(
            f"两次检测期间，共发现 {len(items)} 篇尚未推送的新论文。"
        )
    else:
        header_lines.append(f"本次共发现 {len(items)} 篇尚未推送的新论文。")
    header = "\n".join(header_lines) + "\n\n"
    blocks = [format_article(article, draft) for article, draft in items]
    chunks: list[str] = []
    current = header
    for block in blocks:
        separator = "\n\n────────────────────\n\n" if current != header else ""
        candidate = current + separator + block
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current != header:
            chunks.append(current)
            current = header
        long_parts = _split_long_text(header + block, max_chars)
        chunks.extend(long_parts[:-1])
        current = long_parts[-1]
    if current.strip() and current != header:
        chunks.append(current)

    if len(chunks) > 1:
        total = len(chunks)
        chunks = [f"（{index}/{total}）\n{chunk}" for index, chunk in enumerate(chunks, 1)]
    return chunks
