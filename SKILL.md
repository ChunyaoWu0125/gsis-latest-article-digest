---
name: gsis-latest-article-digest
description: Monitor newly published Geo-spatial Information Science (GSIS) articles and create evidence-grounded bilingual digests. Use when Codex needs to discover recent GSIS papers through Crossref, verify abstracts and author keywords through DOAJ, deduplicate DOI records in local SQLite state, draft and review English/Chinese LinkedIn copy with OpenAI, preview or explicitly send a Feishu digest, test Feishu delivery, or configure local scheduling.
---

# GSIS Latest Article Digest

Use the bundled application to discover recent GSIS papers, verify their metadata, draft bilingual LinkedIn copy, and optionally deliver a Feishu digest. Treat source verification, DOI-level deduplication, and confirmed delivery as hard requirements.

## Prepare The Application

1. Resolve the skill root as the directory containing this `SKILL.md`.
2. Create a Python 3.10+ virtual environment when one is not already available.
3. Install the package and tests with `python -m pip install -e ".[test]"` from the skill root.
4. Copy `.env.example` to `.env` when `.env` does not exist.
5. Ask the user to populate missing credentials locally. Never display, log, commit, or transmit credential values outside their intended service.
6. Keep `data/`, `logs/`, `.env`, and virtual environments local and untracked.

## Choose The Run Mode

- Default to `gsis-notifier --dry-run --limit 1` when the user asks to check, preview, test, or demonstrate the workflow.
- Run `gsis-notifier --dry-run` to preview all eligible articles without sending Feishu messages or marking DOI records as sent.
- Run `gsis-notifier --test-feishu` only when the user explicitly asks to test the configured Feishu bot.
- Run `gsis-notifier` without `--dry-run` only when the user explicitly authorizes Feishu delivery.
- Use `scripts/run_gsis.ps1` on Windows or `scripts/run_gsis.sh` on POSIX systems for an installed local workflow.
- Use `scripts/install_windows_task.ps1` only when the user explicitly asks to create or replace the Windows scheduled task.

## Execute The Verified Workflow

1. Discover recent DOI records and online publication dates from the configured Crossref journal endpoint.
2. Restrict results to *Geo-spatial Information Science* and DOI values beginning with `10.1080/10095020`.
3. Join Crossref candidates to DOAJ records by complete DOI.
4. Require a verified title, canonical DOI link, and complete abstract before drafting.
5. Preserve author-provided keywords verbatim. Treat missing keywords as `Not provided`; never invent official keywords.
6. Record verified candidates in SQLite, then exclude DOI records already marked as successfully sent.
7. Generate bilingual copy using only the verified title, abstract, and author keywords.
8. Review generated claims when review is enabled.
9. Send every Feishu message part successfully before marking any included DOI as sent.

## Enforce Evidence Rules

- Do not infer experiments, datasets, findings, performance gains, mechanisms, locations, implications, or novelty that the source does not state.
- Preserve numbers, comparisons, qualifiers, and causal language in meaning.
- Do not claim `first`, `novel`, `significant`, `outperforms`, or `improves` unless the abstract explicitly supports the claim.
- Reject drafts containing numeric values absent from the verified source metadata.
- Keep the English and Chinese paragraphs factually equivalent.
- Embed 4-6 natural hashtags in each language. Do not append a separate hashtag list.
- Do not publish to LinkedIn. Produce draft copy only.

## Handle Outcomes

- Report Crossref failure as retrieval failure; never convert it into a no-new-articles result.
- Leave incomplete Crossref/DOAJ candidates pending so a later lookback window can retry them.
- Continue processing other articles when one draft fails, but do not send a digest when every new article fails generation.
- Preserve the current SQLite database unless the user explicitly accepts losing deduplication and delivery history.
- Read `references/output-example.md` only when validating or changing final layout and tone.

## Verify Changes

Run `python -m pytest` after modifying application code, prompts, formatting, delivery behavior, or state handling. Keep all tests network-free by using fixtures or fake clients.
