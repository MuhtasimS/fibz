from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable

from vertexai.generative_models import Part

from fibz_bot.config import settings
from fibz_bot.llm.prompts import ENTITY_EXTRACTION_PROMPT
from fibz_bot.llm.router import ModelRouter
from fibz_bot.memory.store import MemoryStore
from fibz_bot.utils.backoff import retry
from fibz_bot.utils.logging import get_logger
from fibz_bot.utils.metrics import metrics

log = get_logger(__name__)


def _build_payload(
    *,
    author_id: str,
    author_display: str | None,
    guild_id: str | None,
    channel_id: str | None,
    message_text: str,
    answer_text: str | None,
) -> str:
    lines = [
        f"author_id={author_id}",
        f"author_display={author_display or ''}",
        f"guild_id={guild_id or 'direct'}",
        f"channel_id={channel_id or ''}",
        "message:\n" + message_text.strip(),
    ]
    if answer_text:
        lines.append("assistant_response:\n" + answer_text.strip())
    return "\n".join(lines)


def _safe_text(resp) -> str:
    """Safely extract text from a Vertex response; tolerate empty/blocked candidates."""
    try:
        t = getattr(resp, "text", "")
        if t:
            return t
    except Exception:
        pass
    # Fallback: walk candidates → content.parts → text
    try:
        for cand in getattr(resp, "candidates", []) or []:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if parts:
                texts = [getattr(p, "text", "") for p in parts if getattr(p, "text", "")]
                if texts:
                    return "\n".join(texts)
    except Exception:
        pass
    return ""


def extract_entities(router: ModelRouter, payload: str) -> dict[str, Any]:
    prompt = ENTITY_EXTRACTION_PROMPT.strip() + "\n\n" + payload.strip()
    resp = retry(
        lambda: router.model_flash.generate_content(
            contents=[Part.from_text(prompt)],
            generation_config={
                "max_output_tokens": 256,
                # If your SDK supports it, uncomment to enforce JSON:
                # "response_mime_type": "application/json",
            },
        ),
        operation="entity_revision",
    )

    text = _safe_text(resp)
    if not text:
        # Nothing to parse — return empty result to avoid crashing the caller
        log.info("entity_revision_no_text", extra={"extra_fields": {"reason": "empty_response"}})
        return {}

    # Try strict JSON first
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Try to recover the largest JSON object span
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
        if isinstance(data, dict):
            return data
    except Exception:
        log.warning("entity_revision_parse_failed", extra={"extra_fields": {"raw": text[:200]}})

    return {}  # final fallback — caller will treat as no facts/targets


def _clean_facts(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    facts: list[str] = []
    for item in items:
        item = (item or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        facts.append(item)
    return facts


async def run_entity_revision_pass(
    router: ModelRouter,
    memory: MemoryStore,
    *,
    author_id: str,
    author_display: str | None,
    guild_id: str | None,
    channel_id: str | None,
    message_text: str,
    answer_text: str | None,
    is_owner: bool,
) -> None:
    if not settings.ENTITY_REVISION_ENABLED:
        return
    message_text = (message_text or "").strip()
    if not message_text:
        return

    metrics.inc("entity.revision_runs")

    payload = _build_payload(
        author_id=author_id,
        author_display=author_display,
        guild_id=guild_id,
        channel_id=channel_id,
        message_text=message_text,
        answer_text=answer_text,
    )

    data = extract_entities(router, payload) or {}
    facts = _clean_facts(data.get("facts", []))
    if not facts:
        return

    sensitive = _clean_facts(data.get("sensitive", []))
    if sensitive and not settings.ENTITY_ALLOW_SENSITIVE:
        log.info(
            "entity_revision_sensitive_skipped",
            extra={"extra_fields": {"author_id": author_id, "items": sensitive}},
        )
        return

    targets = data.get("targets") or []
    target_list: list[dict[str, Any]] = [t for t in targets if isinstance(t, dict)]
    if is_owner and not any(t.get("entity_id") == "bot:self" for t in target_list):
        target_list.append({"entity_id": "bot:self", "kind": "bot", "display_name": "Fibz"})

    default_entity = f"user:{author_id}"
    if not target_list:
        target_list.append(
            {"entity_id": default_entity, "kind": "user", "display_name": author_display or ""}
        )

    for target in target_list:
        entity_id = target.get("entity_id") or default_entity
        entity_id = str(entity_id)

        # Guard: don't write other users' entities based on this author
        if entity_id.startswith("user:") and entity_id != default_entity:
            continue
        # Only owners can update bot:self
        if entity_id == "bot:self" and not is_owner and entity_id != default_entity:
            continue

        existing = memory.get_entity(entity_id) or {}
        existing_doc = existing.get("document", "") if isinstance(existing, dict) else ""
        existing_meta = existing.get("metadata", {}) if isinstance(existing, dict) else {}

        existing_facts = _clean_facts(line.lstrip("- ") for line in existing_doc.splitlines())
        combined = _clean_facts(facts + existing_facts)[: settings.ENTITY_MAX_FACTS]
        if not combined:
            continue

        channels = set()
        existing_channels = existing_meta.get("channels", [])
        if isinstance(existing_channels, str):
            channels.update(part for part in existing_channels.split(",") if part)
        elif isinstance(existing_channels, (list, tuple, set)):
            for ch in existing_channels:
                channels.add(str(ch))
        if channel_id:
            channels.add(str(channel_id))

        metadata = {
            "entity_id": entity_id,
            "kind": target.get("kind", "user"),
            "display_name": target.get("display_name")
            or existing_meta.get("display_name")
            or author_display
            or "",
            "tags": ",".join(sorted({"entity", target.get("kind", "user")})),
            "source": "auto_revision",
            "updated_at": datetime.utcnow().isoformat(),
            "guild_id": guild_id,
            "channels": ",".join(sorted(channels)) if channels else existing_meta.get("channels", ""),
        }
        content = "\n".join(f"- {fact}" for fact in combined)
        memory.upsert_entity(entity_id, content, metadata)
