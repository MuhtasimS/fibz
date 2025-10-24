from __future__ import annotations

import json
from typing import Any, List

from vertexai.generative_models import FunctionCall, Part

from fibz_bot.llm.cache import PromptCache
from fibz_bot.llm.prompts import make_system_prompt
from fibz_bot.llm.router import ModelRouter
from fibz_bot.llm.tools import dispatch_function, toolset
from fibz_bot.utils.backoff import retry


class Agent:
    def __init__(self, router: ModelRouter):
        self.router = router
        self.tools = toolset()
        self.cache = PromptCache(max_items=256, ttl_sec=3600)

    def _safe_text(self, resp) -> str:
        """Return response text safely; Gemini may produce candidates without text parts."""
        try:
            t = getattr(resp, "text", "")
            return t or ""
        except Exception:
            # Try to assemble from parts if available
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

    def _has_malformed_call(self, resp) -> bool:
        for cand in getattr(resp, "candidates", []) or []:
            fr = getattr(cand, "finish_reason", "") or ""
            fm = getattr(cand, "finish_message", "") or ""
            if "MALFORMED_FUNCTION_CALL" in str(fr) or "Malformed function call" in str(fm):
                return True
        return False

    def run(
        self,
        question: str,
        core: str,
        user: str,
        server: str,
        policy_text: str,
        context_docs: list[str] | None = None,
        media_parts: list[Part] | None = None,
        needs_reasoning: bool = True,
        request_context: dict[str, Any] | None = None,
        max_tool_steps: int = 3,
    ) -> str:

        cached = self.cache.get(core, user, server, policy_text)
        if cached:
            system_instruction = cached
        else:
            system_instruction = make_system_prompt(core, user, server, policy_text)
            self.cache.set(core, user, server, policy_text, system_instruction)

        if context_docs:
            system_instruction += "\n\n### CONTEXT\n" + "\n\n".join(context_docs)

        model = self.router.choose_model(
            prompt_tokens=max(len(question) // 4, 1),
            needs_reasoning=needs_reasoning,
        )

        parts: List[Part] = [Part.from_text(system_instruction)]
        if media_parts:
            parts.extend(media_parts)
        parts.append(Part.from_text(question))

        # First model call
        resp = retry(
            lambda: model.generate_content(
                contents=parts,
                tools=self.tools,
                generation_config={"max_output_tokens": 1024},
            ),
            operation="vertex_generate",
        )

        # If the model emitted a malformed tool call, try once without tools
        if self._has_malformed_call(resp):
            resp = retry(
                lambda: model.generate_content(
                    contents=parts,
                    generation_config={"max_output_tokens": 1024},
                ),
                operation="vertex_generate",
            )

        # Tool loop
        for _ in range(max_tool_steps):
            calls: List[FunctionCall] = []
            for cand in getattr(resp, "candidates", []) or []:
                content = getattr(cand, "content", None)
                for part in (getattr(content, "parts", []) or []):
                    fc = getattr(part, "function_call", None)
                    if isinstance(fc, FunctionCall):
                        calls.append(fc)

            if not calls:
                return self._safe_text(resp)

            tool_responses: List[Part] = []
            for call in calls:
                name = call.name
                args = call.args or {}
                result = dispatch_function(request_context["memory"], name, args, request_context or {})
                # Return JSON text to the model to avoid malformed payloads
                result_text = json.dumps(result, ensure_ascii=False)
                tool_responses.append(
                    Part.from_function_response(
                        name=name,
                        response={"content": [{"text": result_text}]},
                    )
                )

            resp = retry(
                lambda: model.generate_content(
                    contents=[Part.from_text(system_instruction)] + tool_responses,
                    tools=self.tools,
                    generation_config={"max_output_tokens": 1024},
                ),
                operation="vertex_generate",
            )

        return self._safe_text(resp)
