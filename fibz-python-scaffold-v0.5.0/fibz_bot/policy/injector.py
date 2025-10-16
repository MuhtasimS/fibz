from __future__ import annotations
from fibz_bot.memory.store import MemoryStore

def make_policy_text(memory: MemoryStore, guild_id: str | None, channel_id: str | None) -> str:
    cross = False
    if guild_id:
        cross = memory.get_cross_channel(str(guild_id))
    base = [
        "- Do not share a user's private information without explicit consent.",
        "- Information from DMs is private unless user opted in.",
        "- Channel content is shareable within the same channel; cross-channel sharing is allowed only if the server policy toggle is enabled.",
        "- If asked about User A by User B, and the info is not clearly public in this channel, ask for explicit consent from User A before sharing.",
        "- If consent is missing or denied, refuse briefly and suggest asking the user directly.",
        "- Obey instruction precedence on conflicts: core > user > server/channel.",
    ]
    extra = f"- Cross-channel sharing is {'ENABLED' if cross else 'DISABLED'} for this server."
    return "\n".join(base + [extra])
