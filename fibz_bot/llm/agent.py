from __future__ import annotations
from typing import Dict, Any, List, Optional
from fibz_bot.llm.router import ModelRouter
from fibz_bot.llm.prompts import make_system_prompt
from fibz_bot.llm.tools import toolset, dispatch_function
from fibz_bot.llm.cache import PromptCache
from vertexai.generative_models import FunctionCall, Tool, Part

class Agent:
    def __init__(self, router: ModelRouter):
        self.router = router
        self.tools = toolset()
        self.cache = PromptCache(max_items=256, ttl_sec=3600)

    def run(self, question: str, core: str, user: str, server: str, policy_text: str,
            context_docs: Optional[List[str]] = None,
            media_parts: Optional[List[Part]] = None,
            needs_reasoning: bool = True,
            request_context: Optional[Dict[str, Any]] = None,
            max_tool_steps: int = 3) -> str:

        cached = self.cache.get(core, user, server, policy_text)
        if cached:
            system_instruction = cached
        else:
            system_instruction = make_system_prompt(core, user, server, policy_text)
            self.cache.set(core, user, server, policy_text, system_instruction)

        if context_docs:
            system_instruction += "\n\n### CONTEXT\n" + "\n\n".join(context_docs)

        model = self.router.choose_model(prompt_tokens=max(len(question)//4,1), needs_reasoning=needs_reasoning)

        parts = [Part.from_text(system_instruction)]
        if media_parts:
            parts.extend(media_parts)
        parts.append(Part.from_text(question))

        resp = model.generate_content(
            parts,
            tools=self.tools,
            tool_config={"function_calling_config": {"mode": "AUTO"}},
            generation_config={"max_output_tokens": 1024},
        )

        for _ in range(max_tool_steps):
            calls = []
            for cand in getattr(resp, "candidates", []):
                for part in cand.content.parts:
                    if hasattr(part, "function_call") and isinstance(part.function_call, FunctionCall):
                        calls.append(part.function_call)

            if not calls:
                return getattr(resp, "text", "") or ""

            tool_responses = []
            for call in calls:
                name = call.name
                args = call.args or {}
                result = dispatch_function(request_context["memory"], name, args, request_context or {})
                tool_responses.append(Part.from_function_response(name=name, response={"name": name, "content": [result]}))

            resp = model.generate_content(
                [Part.from_text(system_instruction)] + tool_responses,
                tools=self.tools,
                tool_config={"function_calling_config": {"mode": "AUTO"}},
                generation_config={"max_output_tokens": 1024},
            )

        return getattr(resp, "text", "") or ""
