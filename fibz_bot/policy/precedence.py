from __future__ import annotations
from typing import Dict, Any

def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def resolve_instructions(core: Dict[str, Any], user: Dict[str, Any], server: Dict[str, Any]) -> Dict[str, Any]:
    merged = deep_merge(server or {}, user or {})
    merged = deep_merge(merged, core or {})
    return merged

def build_prompt_text(core_text: str, user_text: str, server_text: str) -> str:
    sections = []
    if core_text:
        sections.append("### CORE INSTRUCTIONS\n" + core_text.strip())
    if user_text:
        sections.append("### USER INSTRUCTIONS\n" + user_text.strip())
    if server_text:
        sections.append("### SERVER/CHANNEL INSTRUCTIONS\n" + server_text.strip())
    return "\n\n".join(sections)
