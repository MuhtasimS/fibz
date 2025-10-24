# AGENTS_GEMINI.md — Prompting & Tools

## System Prompt
- Build from CORE → USER → SERVER, then add CAPABILITIES and PRIVACY & CONSENT.
- Keep `[file p.N]` tags inline in answers for statements sourced from context.

## Tools
- `retrieve_memory` for message history
- `web_search` for fresh info (use sparingly)
- `store_memory` for durable facts (avoid sensitive data)
- `calculator`, `get_time`

## Routing
- Prefer Flash; escalate to Pro when `needs_reasoning=True` or tokens > 3k.

## Safety & Consent
- DM consent for user A when user B asks about private info; cache decision.
- Cross-channel sharing only if server toggle enabled.

## Output
- Keep answers within Discord limits; the bot will paginate or attach.
- Include inline citations and a Sources block.
