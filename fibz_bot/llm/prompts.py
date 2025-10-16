from __future__ import annotations
from fibz_bot.policy.precedence import build_prompt_text

CAPABILITIES_TEXT = """
You can use tools via function calling when needed. Prefer:
- retrieve_memory for prior messages or facts
- calculator for math
- get_time for time questions
- web_search for web lookups (if enabled by the admin)
When unsure, ask brief clarifying questions.
Respect privacy and consent rules injected below.
When you use CONTEXT items that include a bracketed source tag like [filename p.3], include that tag inline next to the relevant statement.
"""

def make_system_prompt(core_text: str, user_text: str, server_text: str, policy_text: str) -> str:
    instr = build_prompt_text(core_text, user_text, server_text)
    return instr + "\n\n### CAPABILITIES\n" + CAPABILITIES_TEXT.strip() + "\n\n### PRIVACY & CONSENT\n" + policy_text.strip()
