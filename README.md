# Fibz — Discord bot with Vertex AI (Gemini), ChromaDB memory, and consent-aware policy

Fibz is a Python Discord bot that routes between **Gemini 2.5 Pro/Flash**, uses **ChromaDB** for retrieval memory, and enforces **privacy/consent** with instruction precedence (**core > user > server**). It supports document parsing, optional OCR, web search (Google CSE → DDG fallback), signed GCS uploads, inline citations, and admin utilities.

> New here? See **Using Codex on this Repo** for step-by-step instructions to work with OpenAI’s Codex agent effectively.

---

## Quickstart

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
python -m fibz_bot.bot.main
```

### Dev loop

```bash
ruff --fix .
black .
mypy fibz_bot
pytest -q
```

---

## Repo Map (source of truth)

```
fibz_bot/
  bot/main.py           # Discord entrypoint; defines slash commands & mention handler
  llm/router.py         # Vertex init, model routing (Flash vs Pro), embeddings
  llm/agent.py          # Function-calling loop; prompt cache; multimodal support
  llm/tools.py          # Tools: retrieve_memory, store_memory, calculator, get_time, web_search
  llm/prompts.py        # System prompt builder (+ inline citation instruction)
  llm/cache.py          # Prompt cache (LRU-ish + TTL)
  memory/store.py       # Chroma collections: message/self_context/entities/archives; ratings; consent
  policy/precedence.py  # Instruction precedence (core > user > server) + prompt stitcher
  policy/injector.py    # Runtime policy/consent text
  policy/consent.py     # DM consent View (buttons) & helpers
  ingest/attachments.py # Download Discord attachments, upload to GCS (optional), Gemini Parts
  ingest/files.py       # Parse PDF/DOCX/PPTX/TXT (+ PDF page filtering)
  ingest/images.py      # EXIF + optional Vision OCR
  storage/gcs.py        # Upload & signed URLs (optional)
  utils/logging.py      # JSON logger
tests/                  # Unit tests (policy precedence, consent, etc.)
scripts/run_bot.py      # Run helper
pyproject.toml          # Tooling & deps
.env.example            # Config template
README.md               # This file
AGENTS.md               # High-level guide for LLMs/agents (root)
docs/AGENTS_GEMINI.md   # Gemini-specific details, examples, & tuning notes
```

---

## Slash Commands

- `/ask question:"..." [page_hints:"file.pdf:1-3,5; other.pdf:2"]`
- `/ask_about user:@User question:"..."`
- `/summarize` *(attach a PDF)*
- `/persona_core` *(owner)*, `/persona_server` *(admin)*, `/persona_set` *(user)*
- `/crosschannel enabled:true|false`
- `/rate_answer message_link:"..." vote:up|down [note:"..."]` *(admin)*
- `/sign path_in_bucket:"discord/filename.pdf"` *(admin)*
- `/status`

Also supports `!fibz …` and mention triggers; attachments are handled.

---

## Features

- **Gemini 2.5** (Pro/Flash) with **function calling** tools
- **ChromaDB** persistent memory + hybrid-lite retrieval
- **Consent & privacy** with **instruction precedence:** **core > user > server**
- **Cross-channel** toggle and per-scope consent
- **Web search** via Google CSE → DDG fallback
- **GCS** uploads & signed URLs (optional)
- **PDF/DOCX/PPTX/TXT** parsing; **Vision OCR** (optional)
- **Inline citations** like `[file p.N]` with a **Sources** block
- **Prompt cache** and **admin ratings**
- JSON logging & (planned) **/metrics**

---

## Configuration & Secrets

Create `.env` (see `.env.example`). Typical environment variables:

```
# Discord / OpenAI / Search
DISCORD_BOT_TOKEN=...
GCP_PROJECT_ID=...
GCP_VERTEX_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json   # or Workload Identity
GOOGLE_CSE_ID=...
GOOGLE_CSE_API_KEY=...

# Storage / Memory
GCS_BUCKET=...               # optional
CHROMA_PATH=.chroma

# Search filtering (optional, comma-separated)
ALLOW_DOMAINS=
DENY_DOMAINS=
```

**CI-specific template:** add `.env.ci` with placeholders (referenced in GitHub Actions secrets).

---

## Consent & Instruction Precedence

> **Precedence:** `core > user > server`

**System prompt construction**
- Build from **CORE → USER → SERVER** policy layers.
- Append **Capabilities** and **Privacy & Consent** sections to the final system message.
- Preserve inline citation tags (e.g., `[file p.N]`) when statements are sourced from context.

**Pseudocode**
```py
def decide(request, ctx):
    # Merge rules with core highest priority
    rules = merge(core, server, user)
    if not rules.allow(request.scope):
        return Deny(reason="scope denied", scope=request.scope)
    if request.cross_channel and not rules.cross_channel:
        return Deny(reason="cross-channel disabled", scope="cross_channel")
    return Allow(expires_at=rules.expiry)
```

**Dataclass (canonical)**
```py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class ConsentDecision:
    allowed: bool
    reason: str
    scope: str
    expires_at: Optional[datetime]
```

**Safety & consent specifics**
- If **user B** asks about **user A**’s private info, require **DM consent** from A; **cache** the decision.
- **Cross-channel sharing** only when the server toggle is enabled (deny otherwise).

---

## Gemini Agent Behavior (from `docs/AGENTS_GEMINI.md`)

**Tools**
- `retrieve_memory` — fetch prior message/context history.
- `store_memory` — store durable facts (avoid sensitive or disallowed scopes).
- `web_search` — use sparingly for fresh info; prefer citations when used.
- `calculator`, `get_time` — utility tools.

**Routing**
- Prefer **Gemini 2.5 Flash** by default.
- Escalate to **Gemini 2.5 Pro** when `needs_reasoning=True` **or** token budget is **> 3k** for the current task.

**Output rules**
- Keep answers within **Discord limits**; the bot will **paginate or attach** overflow.
- Always include **inline citations** like `[file p.N]` and a final **Sources** block when context or web search is used.

---

## Logging & Metrics

**JSON log record (shape)**
```json
{
  "ts": "2025-01-01T12:34:56.789Z",
  "level": "INFO",
  "event": "cmd.run",
  "user_id": "…",
  "guild_id": "…",
  "cmd": "/ask",
  "duration_ms": 123,
  "pii_scrubbed": true
}
```

**Metrics** (planned `/metrics`):
- JSON **and** Prom-text endpoints
- Counters: `cmd:/ask`, `cmd:/summarize`, `tool:web_search`, `tool:retrieve_memory`, …
- Model histogram: `gemini-2.5-pro`, `gemini-2.5-flash`
- `uptime_s`

---

## Reliability & Overflow Policy

- **Retries/backoff**: wrap outbound calls (Vertex/GCS/CSE) with **exponential backoff + full jitter**; retry on `429`, `5xx`, and timeouts; never retry on `4xx` except `429`.
- **Overflow handling**: if a response would exceed Discord limits or internal cap (default: ~1,800 chars of content), write a `.txt` to `./tmp/overflow/<uuid>.txt` and send as an attachment, with a short summary in-channel.
- **Redaction**: never log secrets; truncate or hash identifiers; clip content previews to ≤120 chars.

---

## CI

A minimal CI should:
- set up Python 3.10–3.12
- `pip install -e ".[dev]"`
- `ruff --fix . && black . && mypy fibz_bot && pytest -q`
- upload coverage artifacts

A sketch of `.github/workflows/ci.yml` is in **docs/CI.md** (or generate via Codex).

---

## Testing Strategy

- **Discord**: mock the bot/client context; assert replies & permissions
- **Vertex/Gemini**: stub client; simulate `429/5xx/TimeoutError` for backoff tests
- **ChromaDB**: temp dir; seed fixtures for retrieval
- **Web search**: fake HTTP client or fixture JSON; test allow/deny filters & pagination
- **Policy**: property tests for precedence and consent revocation flows
- **E2E**: ensure cross-channel denial blocks writes

---

## Web Search UX

Present results as bullets:

```
- [Title](url) — domain — snippet
```

Honor `ALLOW_DOMAINS` / `DENY_DOMAINS`, with tests for both.

---


### The Bootstrap Snippet

```
Role: You are an expert Python engineer on Fibz (Discord bot using Gemini 2.5 Pro/Flash, ChromaDB, consent-aware policy).
Repo map to edit: see README "Repo Map". Touch only those files unless necessary.

Standards: Python ≥3.10, Ruff, Black 100 cols, mypy strict-ish, utils/logging.get_logger, no secret leaks.

Consent precedence: core > user > server (see README for pseudocode + ConsentDecision dataclass).

Output rules:
1) Propose a 3–6 step plan.
2) Return a minimal unified diff (≤200 lines if possible).
3) Include/modify tests in `tests/` that prove acceptance.
4) Print exact commands to run: `ruff --fix . && black . && mypy fibz_bot && pytest -q`.
```

### Task Templates

**A) Retries/backoff**
```
Task: Add Tenacity-style backoff to Vertex, CSE, and GCS calls.
Files: fibz_bot/llm/agent.py, fibz_bot/llm/router.py, fibz_bot/llm/tools.py, storage/gcs.py
Requirements:
- exp backoff + full jitter, base 0.5s, cap 8s, max 5 tries
- retry on 429/5xx/TimeoutError; no retry on other 4xx
- log attempt count and elapsed_ms via utils/logging.get_logger
- overflow > ~1800 chars → tmp/overflow/<uuid>.txt attachment

Acceptance:
- tests simulate 429→success, 500→fail
- mypy/lints/tests all pass
```

**B) `/metrics`**
```
Task: Add admin-only /metrics (JSON + Prom).
Files: fibz_bot/infra/metrics.py (new), fibz_bot/bot/main.py, fibz_bot/llm/agent.py
JSON schema:
{"uptime_s": int, "counters": {...}, "models": {...}}
Acceptance:
- unit tests verify counters increment
- e2e test checks authz & payload shape
```

**C) Privacy commands**
```
Task: Add /privacy_status and /privacy_revoke; enforce cross-channel everywhere.
Files: policy/consent.py, policy/precedence.py, fibz_bot/bot/main.py, memory/store.py
Acceptance:
- revocation persists and blocks memory writes in cross-channel e2e test
- audit log emitted on revoke
```

**D) Web search bullets + filters**
```
Task: Format search results as "- [Title](url) — domain — snippet", enforce ALLOW_DOMAINS/DENY_DOMAINS.
Files: fibz_bot/llm/tools.py
Acceptance: tests for filtering and pagination
```

**E) CI**
```
Task: Add .github/workflows/ci.yml with matrix 3.10–3.12, cache pip, run ruff/black/mypy/pytest, upload coverage artifact; create .env.ci template.
Acceptance: CI passes on PR
```

### How to Prompt Codex Effectively

1. **Paste the exact code excerpts** it must edit (or very small files).  
2. **State acceptance criteria** as bullet points and tests it must add/modify.  
3. **Ask for a single, minimal diff** plus the **tests** and **run commands**.  
4. **Iterate**: run the commands locally; paste failures back with “patch only what fails.”

---

## Documentation

- `AGENTS.md` (root): high-level LLM guidance & repo map (this README mirrors/extends it)
- `docs/AGENTS_GEMINI.md`: Gemini-specific tips, model selection, token/latency tradeoffs
- `docs/TROUBLESHOOTING.md`: common errors, rate limits, CI failures
- `CHANGELOG.md`: shipped changes by date

---

## Acceptance Criteria (project-level)

- Commands function end-to-end; consent flows persist & gate sharing
- Long outputs are paginated or attached via overflow policy
- Inline citations appear when sources exist
- Lints/type checks/tests pass locally and in CI
- Metrics and logs are emitted as specified

---

## License

MIT (or your preferred license).
