from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, TYPE_CHECKING

import discord

from fibz_bot.utils.logging import get_logger
from fibz_bot.utils.metrics import metrics

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from fibz_bot.llm.router import ModelRouter
    from fibz_bot.memory.store import MemoryStore

log = get_logger(__name__)

SENSITIVE_KEYS = {
    "email",
    "phone",
    "address",
    "password",
    "passport",
    "credit card",
    "social security",
    "medical",
    "health",
    "finance",
    "salary",
    "location",
    "token",
}
_CLASSIFIER_SENSITIVE = SENSITIVE_KEYS
_CLASSIFIER_PRIVATE = {"private", "dm", "direct message", "secret", "confidential"}

_CONSENT_MEMORY: Optional["MemoryStore"] = None
_CONSENT_ROUTER: Optional["ModelRouter"] = None


class ConsentDecision:
    SHAREABLE = "shareable"
    PRIVATE = "private"
    CONSENT_REQUIRED = "consent_required"


def classify_info(payload: Dict[str, Any]) -> str:
    tags = {str(t).lower() for t in payload.get("tags", [])}
    if "private" in tags:
        return ConsentDecision.PRIVATE
    if "consent_required" in tags:
        return ConsentDecision.CONSENT_REQUIRED
    keys = {str(k).lower() for k in payload.keys()}
    if SENSITIVE_KEYS & keys:
        return ConsentDecision.CONSENT_REQUIRED
    return ConsentDecision.SHAREABLE


def can_share(
    requester_id: str,
    subject_id: str,
    item_meta: Dict[str, Any],
    *,
    same_channel: bool,
    cross_channel_toggle: bool,
) -> bool:
    if same_channel:
        return True
    return bool(cross_channel_toggle)


def configure_consent(memory: "MemoryStore", router: "ModelRouter" | None = None) -> None:
    global _CONSENT_MEMORY, _CONSENT_ROUTER
    _CONSENT_MEMORY = memory
    if router is not None:
        _CONSENT_ROUTER = router


async def classify_share_request(
    request_text: str,
    requester_id: str,
    subject_id: str,
    guild_id: str | None,
    channel_id: str | None,
    cross_channel_enabled: bool,
    *,
    router: "ModelRouter" | None = None,
) -> str:
    """Classify whether a share request is safe, blocked, or requires consent."""

    metrics.inc("consent.classifier_runs")

    if requester_id == subject_id:
        return "share_safe"

    text = (request_text or "").lower()
    if not cross_channel_enabled:
        if any("#" in token or "channel" in token for token in text.split()):
            return "share_block"
    for phrase in _CLASSIFIER_SENSITIVE:
        if phrase in text:
            return "share_needs_consent"
    if any(phrase in text for phrase in _CLASSIFIER_PRIVATE):
        return "share_needs_consent"

    model = router or _CONSENT_ROUTER
    if model is None:
        return "share_safe"

    # Lightweight LLM check — prefer Flash
    try:
        from vertexai.generative_models import Part
        from fibz_bot.utils.backoff import retry

        prompt = (
            "You act as a privacy classifier. Possible labels: share_safe, share_block, share_needs_consent. "
            "Label the request below. If it demands sensitive data, choose share_needs_consent; if it would violate scope/cross-channel, choose share_block. "
            "Reply with just the label.\nRequest:" + request_text.strip()
        )
        response = retry(
            lambda: (
                model.model_flash if hasattr(model, "model_flash") else model
            ).generate_content(
                [Part.from_text(prompt)], generation_config={"max_output_tokens": 16}
            ),
            operation="consent_classifier",
        )
        label = (getattr(response, "text", "") or "").strip().lower()
        if label in {"share_safe", "share_block", "share_needs_consent"}:
            return label
    except Exception as exc:  # pragma: no cover - network errors mocked elsewhere
        log.warning(
            "consent_classifier_fallback",
            extra={"extra_fields": {"error": exc.__class__.__name__}},
        )
    return "share_safe"


class ConsentView(discord.ui.View):
    def __init__(self, timeout: Optional[float] = 120.0):
        super().__init__(timeout=timeout)
        self.result: Optional[bool] = None
        self._event = asyncio.Event()

    @discord.ui.button(label="Allow", style=discord.ButtonStyle.success)
    async def allow(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = True
        self._event.set()
        await interaction.response.edit_message(content="✅ Consent granted.", view=None)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = False
        self._event.set()
        await interaction.response.edit_message(content="❌ Consent denied.", view=None)

    async def wait_result(self) -> Optional[bool]:
        try:
            await asyncio.wait_for(self._event.wait(), timeout=self.timeout or 120.0)
        except asyncio.TimeoutError:
            return None
        return self.result


async def request_consent_dm(
    bot: discord.Client,
    subject: discord.User | discord.Member,
    requester_name: str,
    scope: str,
    target: str,
) -> Optional[bool]:
    try:
        view = ConsentView(timeout=180.0)
        dm = await subject.create_dm()
        await dm.send(
            content=(
                f"**Consent request**\n"
                f"User **{requester_name}** is requesting to access information about you.\n"
                f"Scope: **{scope}**; Target: **{target}**.\n"
                f"Do you allow Fibz to share the relevant info?"
            ),
            view=view,
        )
        result = await view.wait_result()
        return result
    except Exception as exc:
        log.warning(
            "consent_dm_failed",
            extra={
                "extra_fields": {"subject_id": str(subject.id), "error": exc.__class__.__name__}
            },
        )
        return None


async def ensure_consent(
    subject_id: str,
    scope: str,
    target: str,
    interaction_or_client: discord.Interaction | discord.Client,
    requester_name: str | None = None,
) -> bool:
    if _CONSENT_MEMORY is None:
        raise RuntimeError("Consent memory is not configured")

    cached = _CONSENT_MEMORY.get_consent(subject_id, scope, target)
    if cached is not None:
        return bool(cached)

    metrics.inc("consent.dm_requests")

    client: discord.Client
    if isinstance(interaction_or_client, discord.Interaction):
        client = interaction_or_client.client  # type: ignore[assignment]
        if client is None:  # pragma: no cover - discord typing guard
            client = interaction_or_client._client  # type: ignore[attr-defined]
        requester_name = requester_name or interaction_or_client.user.display_name
        guild = interaction_or_client.guild
        subject: discord.User | discord.Member | None = None
        if guild:
            subject = guild.get_member(int(subject_id))
        if subject is None:
            subject = await client.fetch_user(int(subject_id))
    else:
        client = interaction_or_client
        requester_name = requester_name or "Unknown"
        subject = client.get_user(int(subject_id)) if hasattr(client, "get_user") else None
        if subject is None:
            subject = await client.fetch_user(int(subject_id))

    if subject is None:
        return False

    decision = await request_consent_dm(client, subject, requester_name or "Unknown", scope, target)
    if decision is True:
        metrics.inc("consent.dm_grants")
        _CONSENT_MEMORY.set_consent(subject_id, scope, target, True)
        return True
    if decision is False:
        metrics.inc("consent.dm_denies")
        _CONSENT_MEMORY.set_consent(subject_id, scope, target, False)
        return False
    return False


__all__ = [
    "ConsentDecision",
    "classify_info",
    "classify_share_request",
    "configure_consent",
    "ensure_consent",
    "request_consent_dm",
    "can_share",
]
