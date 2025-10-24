# AGENTS_GEMINI.md — Prompting & Tools

## System Prompt
- Build from CORE → USER → SERVER, then add CAPABILITIES and PRIVACY & CONSENT.
- Keep `[file p.N]` tags inline in answers for statements sourced from context.

## Tools
- `retrieve_memory` for message history
- `web_search` for fresh info (use sparingly)
- `store_memory` for durable facts (avoid sensitive data)
- `calculator`, `get_time`

## Entity Extraction
- After each turn, run the **Entity revision** call with Gemini 2.5 Flash.
- Prompt snippet:
-  ```
  You extract safe, non-sensitive facts from a single message for long-term memory.

  Return strict JSON:
  {
    "facts": [ "short, declarative fact", ... ],
    "targets": [ {"entity_id": "user:<id>|bot:self|server:<guild>", "kind":"user|bot|server", "display_name": "<optional>"} ],
    "sensitive": [ "brief description of any sensitive items you refused", ... ]
  }

  Guidelines:
  - Only keep non-sensitive, share-safe facts unless explicit consent applies.
  - Prefer durable attributes (skills, preferences stated as public, time zones if user provided them voluntarily in-channel, project updates the bot should remember).
  - Skip health, finances, precise location, or private identifiers.
  ```
- Store only non-sensitive, share-safe facts. Skip or redact sensitive attributes unless explicit consent is cached.
- Update `entities` collection summaries (users/bot/server) and refresh metadata timestamps.

## Memory policies
- When you read entity summaries, respect consent + cross-channel scope.
- Write decisions/consents under `consent:<subject_id>:<scope>:<target>` in `self_context`.

## Routing
- Prefer Flash; escalate to Pro when `needs_reasoning=True` or tokens > 3k.

## Safety & Consent
- DM consent for user A when user B asks about private info; cache decision.
- Cross-channel sharing only if server toggle enabled.

## Output
- Keep answers within Discord limits; the bot will paginate or attach.
- Include inline citations and a Sources block.
