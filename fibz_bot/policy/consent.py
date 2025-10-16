from __future__ import annotations
from typing import Dict, Any, Optional
import discord, asyncio

SENSITIVE_KEYS = {"email","phone","address","health","finance","password","token"}

class ConsentDecision:
    SHAREABLE = "shareable"
    PRIVATE = "private"
    CONSENT_REQUIRED = "consent_required"

def classify_info(payload: Dict[str, Any]) -> str:
    tags = set(str(t).lower() for t in payload.get("tags", []))
    if "private" in tags:
        return ConsentDecision.PRIVATE
    if "consent_required" in tags:
        return ConsentDecision.CONSENT_REQUIRED
    keys = set(k.lower() for k in payload.keys())
    if SENSITIVE_KEYS & keys:
        return ConsentDecision.CONSENT_REQUIRED
    return ConsentDecision.SHAREABLE

def can_share(requester_id: str, subject_id: str, item_meta: Dict[str, Any], same_channel: bool,
              cross_channel_toggle: bool) -> bool:
    if same_channel:
        return True
    return bool(cross_channel_toggle)

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

async def request_consent_dm(bot: discord.Client, subject: discord.User | discord.Member, requester_name: str, scope: str, target: str) -> Optional[bool]:
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
            view=view
        )
        result = await view.wait_result()
        return result
    except Exception:
        return None
