from __future__ import annotations
from typing import List, Dict, Any
from fibz_bot.config import settings
from fibz_bot.utils.http import get_json

def google_cse_search(query: str, num: int = 5) -> List[Dict[str, Any]]:
    api_key = getattr(settings, "GOOGLE_CSE_API_KEY", "") or ""
    cx = getattr(settings, "GOOGLE_CSE_CX", "") or ""
    if not api_key or not cx:
        return []
    url = "https://www.googleapis.com/customsearch/v1"
    data, err = get_json(url, params={"key": api_key, "cx": cx, "q": query, "num": num})
    if err or not data:
        return []
    out = []
    for item in data.get("items", []):
        out.append({
            "title": item.get("title"),
            "link": item.get("link"),
            "snippet": item.get("snippet"),
            "displayLink": item.get("displayLink")
        })
    return out

def ddg_instant_answer(query: str) -> List[Dict[str, Any]]:
    url = "https://api.duckduckgo.com/"
    data, err = get_json(url, params={"q": query, "format":"json", "no_redirect":"1", "no_html":"1"})
    out = []
    if data:
        if data.get("AbstractText"):
            out.append({"title": data.get("Heading"), "link": data.get("AbstractURL"), "snippet": data.get("AbstractText")})
        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"):
                out.append({"title": topic.get("Text"), "link": topic.get("FirstURL"), "snippet": topic.get("Text")})
    return out

def web_search(query: str, num: int = 5) -> List[Dict[str, Any]]:
    results = google_cse_search(query, num=num)
    if results:
        return results[:num]
    return ddg_instant_answer(query)[:num]
