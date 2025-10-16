from __future__ import annotations
from typing import List
from fibz_bot.config import settings

def get_builtin_tools():
    try:
        if settings.USE_VERTEX_SEARCH_GROUNDING:
            from vertexai.generative_models import Tool, grounding
            return [Tool.from_google_search_retrieval(grounding.GoogleSearchRetrieval())]
    except Exception:
        pass
    return []
