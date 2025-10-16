# Fibz (Python scaffold) — v0.5.0

New in this version:
- **/metrics** (admin): uptime + counters (commands, tools, model choices)
- **/privacy_status**: list your stored consents (ephemeral)
- **/memory_find**: search memory (ephemeral)
- **/memory_purge** (admin): delete by JSON filter with dry-run
- CI workflow (Ruff, Black, Mypy, Pytest)
- Metrics wiring in router/tools/commands

All previous features remain (Gemini agent, citations, page hints, summarize, consent flow, web search, GCS, OCR, personas, cross-channel toggle, Chroma memory, prompt cache, ratings).

## Quickstart
```bash
pip install -e ".[dev]"
cp .env.example .env
python -m fibz_bot.bot.main
```
