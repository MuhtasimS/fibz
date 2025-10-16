# Codex Master Prompt for Fibz

You are an expert Python engineer working on **Fibz**, a Discord bot that uses Vertex AI (Gemini 2.5 Flash/Pro), ChromaDB, and a consent-aware policy layer. The repository already contains a working scaffold with commands, tools, and ingestion.

## Goals
- Production-ready reliability, tests, CI, and docs.
- Enforce privacy/consent and instruction precedence (core > user > server).
- Follow lint/type/style rules.
- Add GH Actions secrets notes and an example .env.ci template for CI runs.

## Current Features (preserve)
- `/ask`, `/ask_about`, `/summarize`, `/persona_*`, `/crosschannel`, `/rate_answer`, `/sign`, `/status`
- Gemini agent (function-calling), router, tools (`retrieve_memory`, `store_memory`, `web_search`, `calculator`, `get_time`)
- ChromaDB memory; consent; ratings; cross-channel toggle
- Web search via Google CSE → DDG fallback
- GCS uploads + signed URLs (optional)
- PDF/DOCX/PPTX/TXT parsing; Vision OCR (optional)
- Inline citations `[file p.N]` + Sources block
- Page-range hints; prompt cache; JSON logging

## Deliverables
1. Retries/backoff around API calls; overflow handling with .txt attachments.
2. /metrics (admin) + rotating JSON logs to `logs/`.
3. /privacy_status (list/revoke); enforce cross-channel in all paths.
4. /memory_find and /memory_purge (dry-run + confirm).
5. Web search: Markdown bullets with title/link/domain/snippet + allow/deny lists.
6. CI workflow (ruff/black/mypy/pytest), tests expansion, coverage artifacts.
7. Docs: Troubleshooting + CHANGELOG.

## Standards
- Python ≥ 3.10; black line length 100; ruff; mypy strict-ish.
- Use utils/logging.get_logger; do not leak secrets.

## Run
pip install -e ".[dev]"
cp .env.example .env
python -m fibz_bot.bot.main

## Test
ruff --fix . && black . && mypy fibz_bot && pytest -q
