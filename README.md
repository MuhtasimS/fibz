# Fibz — Gemini 2.5 Discord Bot (Python) · v0.5.0

A privacy-first, multimodal Discord bot powered by **Google Vertex AI – Gemini 2.5** (Flash & Pro), with **persistent memory (ChromaDB)**, **consent-aware sharing**, PDF/image extraction with **inline citations**, optional **Google Cloud Storage** integration, and a growing set of admin/dev tools.

---

## ✨ Highlights

- **Gemini 2.5 Flash + Pro routing** (auto-picks Flash for short turns; escalates to Pro when reasoning/long context is needed)
- **Multimodal understanding**: images/audio/video + files (PDF, DOCX, PPTX, TXT) → context for answers
- **Inline citations** in answers: sources like `[file.pdf p.3]` appear next to claims
- **PDF page-range hints** for targeted extraction: `page_hints:"paper.pdf:1-3,5; appendix.pdf:2"`
- **Persistent, referenceable memory** (ChromaDB) with hybrid-lite retrieval and rich metadata
- **Personalized personalities** with **instruction precedence**: **core > user > server/channel**
- **Consent-aware privacy model**: per-user Allow/Deny DM flows; **cross-channel sharing** is a server toggle
- **Web search tool** via Google Programmable Search Engine (fallback to DuckDuckGo Instant)
- **Google Cloud Storage (optional)** for attachment archival + **signed URLs** (admin)
- **Admin quality controls**: up/down **ratings** on answers
- **Metrics** and status endpoints; GitHub Actions CI; prompt cache; JSON logging
- **Discord 2000 char limit** handling by chunking multi-part responses (auto-splitting)

> Roadmap (outlined in AGENTS docs / Codex prompt): retries/backoff, automatic `.txt` attachments for very long answers, richer purge filters, more tests, troubleshooting docs.

---

## 🧩 Features (detailed)

- **Instruction precedence engine**: merges Core → User → Server/Channel into the system prompt, then appends runtime **Privacy & Consent** policy and **Capabilities**. The bot caches this merged prompt for performance.
- **Consent & privacy**:
  - Same-channel sharing permitted by default; **cross-channel** is opt-in per-server.
  - When user B asks about user A, Fibz DMs A with **Allow/Deny** buttons; decision is cached by **scope/target** (e.g., per channel).
- **Memory**:
  - Stores messages (`messages`), internal context (`self_context` for personas, policies, ratings, consents), entities, archives.
  - **Hybrid-lite retrieval**: vector similarity + lexical fusion.
- **Ingestion**:
  - **PDF/DOCX/PPTX/TXT** parsed into chunks; **Images** optionally OCR’d (Vision) with EXIF metadata; all feed the model.
  - Extraction lines include `[filename p.N]` or `[filename slide N]` tags and are referenced inline in answers.
- **Web search**:
  - `web_search` tool uses **Google CSE** if keys present; otherwise **DDG Instant**.
- **Storage (optional)**:
  - Upload attachments to **GCS**; admins can **/sign** paths to get time-limited URLs.
- **Observability & quality**:
  - **/metrics** exposes counters for commands, tools, model choices + uptime.
  - **/status** shows memory collection counts + uptime.
  - Admins can **/rate_answer** with notes.

---

## 🛠️ Commands

### Everyone
- **`/ask question:"..." [page_hints:"paper.pdf:1-3,5; appendix.pdf:2"]`** — Ask Fibz; supports attachments; extracts and cites sources inline.
- **`/ask_about user:@User question:"..."`** — Ask about someone else; triggers **consent** DM if needed.
- **`/summarize`** *(attach a PDF)* — Indexes the PDF into memory; returns abstract + **page-referenced outline** with Sources.
- **`/persona_set text:"..."`** — Save your personal instruction/persona (applies between core and server).
- **`/privacy_status [page:1]`** — View your stored consent records (ephemeral).
- **Message trigger:** mention the bot or `!fibz ...` — Works like `/ask`, including attachments & extraction.

### Admin / Owner
- **`/persona_server text:"..."`** — Set server persona. *(admin)*
- **`/persona_core text:"..."`** — Set core persona (highest precedence). *(owner)*
- **`/crosschannel enabled:true|false`** — Toggle cross-channel sharing of channel content. *(admin)*
- **`/rate_answer message_link:"…" vote:up|down [note:"…"]`** — Record an answer rating with an optional note. *(admin)*
- **`/sign path_in_bucket:"discord/filename.pdf"`** — Generate a **GCS signed URL**. *(admin)*
- **`/metrics`** — JSON snapshot: counters (commands/tools/model choices), uptime. *(admin)*
- **`/memory_find query:"..." [k:6]`** — Search memory with scores & tag snippets (channel-scoped). *(ephemeral)*
- **`/memory_purge filter:'{...}' confirm:false`** — Dry-run delete by JSON metadata filter; set `confirm:true` to delete. *(admin)*
- **`/status`** — Memory counts + uptime (ephemeral).

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+**
- **Discord bot token** (create at https://discord.com/developers/applications)
- **Google Cloud** project with Vertex AI enabled and a service account (JSON key)
- Optional:
  - **Google Programmable Search Engine** (API key + CX) for web search
  - **Google Cloud Storage** bucket for attachments/signed URLs
  - **Cloud Vision API** for image OCR

### Setup
```bash
# 1) Install
pip install -e ".[dev]"

# 2) Configure environment
cp .env.example .env
# Fill in: DISCORD_BOT_TOKEN, VERTEX_PROJECT_ID, VERTEX_LOCATION,
# VERTEX_MODEL_FLASH, VERTEX_MODEL_PRO, VERTEX_EMBED_MODEL,
# GOOGLE_APPLICATION_CREDENTIALS, CHROMA_PATH, FIBZ_OWNER_ID, etc.
# Optional: GOOGLE_CSE_API_KEY, GOOGLE_CSE_CX, GCS_BUCKET, ENABLE_VISION_OCR=true

# 3) Run
python -m fibz_bot.bot.main
```

### Environment variables (excerpt)
```
DISCORD_BOT_TOKEN=...

# Vertex / Google Cloud
VERTEX_PROJECT_ID=your_gcp_project
VERTEX_LOCATION=us-central1
VERTEX_MODEL_FLASH=gemini-2.5-flash
VERTEX_MODEL_PRO=gemini-2.5-pro
VERTEX_EMBED_MODEL=text-embedding-004
GOOGLE_APPLICATION_CREDENTIALS=/abs/path/to/service_account.json

# Memory & policy
CHROMA_PATH=./chroma_data
CROSS_CHANNEL_SHARING_DEFAULT=false
DEFAULT_FLASH_RATIO=0.5

# Ownership
FIBZ_OWNER_ID=000000000000000000

# Optional features
ENABLE_VISION_OCR=false
SPEECH_LANGUAGE=en-US
GOOGLE_CSE_API_KEY=
GOOGLE_CSE_CX=
GCS_BUCKET=
GCS_SIGN_URLS=true
GCS_SIGN_URL_EXPIRY_SECONDS=86400
```

---

## 🔧 Customization

- **Personas**:
  - **Core** (owner): `/persona_core`
  - **User** (self): `/persona_set`
  - **Server** (admin): `/persona_server`
  - Merge order at runtime: **core > user > server/channel**
- **Privacy defaults**:
  - Same-channel sharing by default; toggle cross-channel via `/crosschannel`.
- **Retrieval**:
  - ChromaDB path via `CHROMA_PATH`; metadata includes guild/channel/user/tags; supports channel-only retrieval in tools.

---

## 🔒 Admin & Security

- Admin-only commands are gated by Discord permissions (or owner ID for `/persona_core`).
- Consent is required to share user-specific info that isn’t clearly public in the current channel.
- Do **not** commit `.env` or keys. The bot logs in structured JSON (avoid secrets in logs).

---

## 🧪 Development

- **Linting/formatting**: `ruff --fix . && black .`
- **Type checking**: `mypy fibz_bot`
- **Tests**: `pytest -q` (lightweight tests included; no Vertex/Discord required)
- **CI**: GitHub Actions workflow runs ruff, black (check), mypy, pytest on pushes/PRs.

---

## ❓ FAQ

- **Does Gemini browse the web by itself?**  
  No. Web is provided via the `web_search` tool (Google CSE if configured; DuckDuckGo Instant fallback).

- **How does Fibz handle long answers?**  
  It auto-splits into multiple messages. (Roadmap: attach `.txt` for very long outputs.)

- **Where are files stored?**  
  Locally downloaded for processing; optionally uploaded to **GCS**. Extracted text is fed to the model and may be indexed into Chroma when you use `/summarize`.

---

## 🗺️ Roadmap (next up)

- Retry/backoff wrappers around Vertex & Discord operations
- Automatic `.txt` attachments for very long answers
- Richer purge filters (time windows/regex), domain allow/deny lists for web search
- More tests and a Troubleshooting section

---

## 📝 Changelog

- **v0.5.0**
  - Added **/metrics**, **/privacy_status**, **/memory_find**, **/memory_purge**
  - Metrics wiring (model choices, tool calls, commands), CI workflow, minimal tests
- **v0.4.x**
  - Inline citations, page-range hints, `/summarize`, `/sign`, GCS & Vision OCR options
- **v0.3.x**
  - Initial Python scaffold: Gemini agent/tools, personas, consent policy, Chroma memory, web search
