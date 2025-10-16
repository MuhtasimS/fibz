from __future__ import annotations
from typing import Any, Dict, List
from vertexai.generative_models import Tool, FunctionDeclaration, Schema, SchemaType
from fibz_bot.memory.store import MemoryStore
from fibz_bot.web.search import web_search as do_search
from fibz_bot.utils.metrics import record_tool_call

def toolset() -> List[Tool]:
    memory_funcs = [
        FunctionDeclaration(
            name="retrieve_memory",
            description="Retrieve relevant past content from memory for grounding answers.",
            parameters=Schema(
                type=SchemaType.OBJECT,
                properties={
                    "query": Schema(type=SchemaType.STRING),
                    "k": Schema(type=SchemaType.NUMBER),
                    "channel_only": Schema(type=SchemaType.BOOLEAN),
                },
                required=["query"]
            )
        ),
        FunctionDeclaration(
            name="store_memory",
            description="Store an item in long-term memory with optional tags.",
            parameters=Schema(
                type=SchemaType.OBJECT,
                properties={
                    "text": Schema(type=SchemaType.STRING),
                    "tags": Schema(type=SchemaType.ARRAY, items=Schema(type=SchemaType.STRING)),
                },
                required=["text"]
            )
        ),
    ]
    util_funcs = [
        FunctionDeclaration(
            name="calculator",
            description="Safely evaluate a math expression.",
            parameters=Schema(
                type=SchemaType.OBJECT,
                properties={"expression": Schema(type=SchemaType.STRING)},
                required=["expression"]
            )
        ),
        FunctionDeclaration(
            name="get_time",
            description="Get the current server time or a specific timezone.",
            parameters=Schema(
                type=SchemaType.OBJECT,
                properties={"timezone": Schema(type=SchemaType.STRING)},
            )
        ),
    ]
    web_funcs = [
        FunctionDeclaration(
            name="web_search",
            description="Perform a web search and return top results (Google CSE if configured, else DuckDuckGo Instant).",
            parameters=Schema(
                type=SchemaType.OBJECT,
                properties={"query": Schema(type=SchemaType.STRING), "num": Schema(type=SchemaType.NUMBER)},
                required=["query"]
            )
        ),
    ]
    return [Tool(function_declarations=memory_funcs + util_funcs + web_funcs)]

import time, ast, operator

_ALLOWED_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos, ast.FloorDiv: operator.floordiv,
}

def _eval_expr(expr: str) -> float:
    node = ast.parse(expr, mode="eval")
    def _eval(n):
        if isinstance(n, ast.Expression): return _eval(n.body)
        if hasattr(ast, "Num") and isinstance(n, ast.Num): return n.n
        if isinstance(n, ast.Constant): return n.value
        if isinstance(n, ast.BinOp): return _ALLOWED_OPS[type(n.op)](_eval(n.left), _eval(n.right))
        if isinstance(n, ast.UnaryOp): return _ALLOWED_OPS[type(n.op)](_eval(n.operand))
        raise ValueError("Unsupported expression")
    return float(_eval(node))

def dispatch_function(memory: MemoryStore, fn_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    record_tool_call(fn_name)
    if fn_name == "retrieve_memory":
        query = args.get("query", "")
        k = int(args.get("k", 6))
        channel_only = bool(args.get("channel_only", True))
        where = {}
        if channel_only and context.get("channel_id"):
            where["channel_id"] = str(context["channel_id"])
        res = memory.retrieve(query, k=k, where=where or None)
        items = []
        for doc, meta in zip(res.get("documents", []), res.get("metadatas", [])):
            items.append({"text": doc, "meta": meta})
        return {"items": items}
    if fn_name == "store_memory":
        text = args.get("text", "")
        tags = args.get("tags", [])
        meta = {
            "message_id": f"mem:{context.get('guild_id')}:{context.get('channel_id')}:{context.get('user_id')}",
            "guild_id": str(context.get("guild_id", "")),
            "channel_id": str(context.get("channel_id", "")),
            "user_id": str(context.get("user_id", "")),
            "role": "system",
            "modality": "text",
            "tags": tags or ["memo"],
        }
        from fibz_bot.memory.store import MessageMeta
        memory.upsert_message(meta["message_id"], text, MessageMeta(**meta))
        return {"status": "stored", "tags": tags}
    if fn_name == "calculator":
        expr = args.get("expression", "")
        try:
            return {"result": _eval_expr(expr)}
        except Exception as e:
            return {"error": str(e)}
    if fn_name == "get_time":
        tz = args.get("timezone") or "UTC"
        return {"timezone": tz, "epoch": int(time.time())}
    if fn_name == "web_search":
        query = args.get("query", "")
        num = int(args.get("num", 5))
        results = do_search(query, num=num) or []
        return {"results": results}
    return {"error": f"Unknown function {fn_name}"}
