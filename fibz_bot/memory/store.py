from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
import chromadb
from fibz_bot.config import settings
from fibz_bot.utils.logging import get_logger
from fibz_bot.llm.router import ModelRouter

log = get_logger(__name__)

class MessageMeta(BaseModel):
    message_id: str
    guild_id: Optional[str] = None
    channel_id: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    role: str = "user"
    modality: str = "text"
    reply_to: Optional[str] = None
    created_at: datetime = datetime.utcnow()
    tokens: Optional[int] = None
    persona: Optional[str] = None
    version: str = "0.5.0"
    consent: Dict[str, Any] = {}
    tags: List[str] = []

class MemoryStore:
    def __init__(self, router: ModelRouter):
        self.router = router
        self.client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
        self.messages = self.client.get_or_create_collection("messages", metadata={"hnsw:space":"cosine"})
        self.self_context = self.client.get_or_create_collection("self_context", metadata={"hnsw:space":"cosine"})
        self.entities = self.client.get_or_create_collection("entities", metadata={"hnsw:space":"cosine"})
        self.archives = self.client.get_or_create_collection("archives", metadata={"hnsw:space":"cosine"})

    def upsert_message(self, message_id: str, content: str, meta: MessageMeta) -> None:
        vec = self.router.embed_texts([content])[0]
        self.messages.upsert(ids=[message_id], documents=[content], embeddings=[vec], metadatas=[meta.model_dump()])

    def upsert_self_context(self, key: str, content: str, metadata: Dict[str, Any]) -> None:
        vec = self.router.embed_texts([content])[0]
        self.self_context.upsert(ids=[key], documents=[content], embeddings=[vec], metadatas=[metadata])

    def _get_self_context_by_id(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            res = self.self_context.get(ids=[key])
            if res and res.get("ids"):
                return {"id": res["ids"][0], "document": res["documents"][0], "metadata": res["metadatas"][0]}
        except Exception:
            return None
        return None

    # Personas
    def set_persona_core(self, text: str) -> None: self.upsert_self_context("persona:core", text, {"type":"persona","scope":"core"})
    def get_persona_core(self) -> str: return (self._get_self_context_by_id("persona:core") or {}).get("document") or ""
    def set_persona_user(self, user_id: str, text: str) -> None: self.upsert_self_context(f"persona:user:{user_id}", text, {"type":"persona","scope":"user","user_id":user_id})
    def get_persona_user(self, user_id: str) -> str: return (self._get_self_context_by_id(f"persona:user:{user_id}") or {}).get("document") or ""
    def set_persona_server(self, guild_id: str, text: str) -> None: self.upsert_self_context(f"persona:server:{guild_id}", text, {"type":"persona","scope":"server","guild_id":guild_id})
    def get_persona_server(self, guild_id: str) -> str: return (self._get_self_context_by_id(f"persona:server:{guild_id}") or {}).get("document") or ""

    # Cross-channel
    def set_cross_channel(self, guild_id: str, enabled: bool) -> None: self.upsert_self_context(f"policy:crosschannel:{guild_id}", f"cross_channel_enabled={enabled}", {"type":"policy","key":"cross_channel_enabled","value":enabled,"guild_id":guild_id})
    def get_cross_channel(self, guild_id: str) -> bool:
        row = self._get_self_context_by_id(f"policy:crosschannel:{guild_id}")
        if row and isinstance(row.get("metadata"), dict): return bool(row["metadata"].get("value", False))
        return False

    # Consent
    def set_consent(self, subject_user_id: str, scope: str, target: str, granted: bool) -> None:
        self.upsert_self_context(f"consent:{subject_user_id}:{scope}:{target}", f"consent scope={scope} target={target} granted={granted}", {"type":"consent","subject_user_id":subject_user_id,"scope":scope,"target":target,"granted":granted})
    def get_consent(self, subject_user_id: str, scope: str, target: str) -> Optional[bool]:
        row = self._get_self_context_by_id(f"consent:{subject_user_id}:{scope}:{target}")
        if row and isinstance(row.get("metadata"), dict): return bool(row["metadata"].get("granted", None))
        return None
    def list_consents_for_user(self, subject_user_id: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        try:
            # Chroma supports metadata filtering in get(); fall back gracefully
            offset = max(page-1, 0) * page_size
            res = self.self_context.get(where={"type":"consent","subject_user_id":subject_user_id})
            ids = res.get("ids", [])
            docs = res.get("documents", [])
            metas = res.get("metadatas", [])
            total = len(ids)
            sl = slice(offset, offset+page_size)
            return {"total": total, "items": [{"id": ids[i], "text": docs[i], "meta": metas[i]} for i in range(*sl.indices(total))]}
        except Exception:
            return {"total": 0, "items": []}

    # Ratings
    def set_rating(self, guild_id: str, message_id: str, up: bool, note: str | None):
        key = f"rating:{guild_id}:{message_id}"
        content = f"rating up={up} note={note or ''}"
        meta = {"type":"rating","guild_id":guild_id,"message_id":message_id,"up":up,"note":note or ""}
        self.upsert_self_context(key, content, meta)

    # Retrieval
    def retrieve(self, query: str, k: int = 6, where: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        qvec = self.router.embed_texts([query])[0]
        res = self.messages.query(query_embeddings=[qvec], n_results=k, where=where or {})
        docs = res.get("documents", [[]])[0]
        ids = res.get("ids", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        distances = res.get("distances", [[]])[0]

        def lexical_score(text: str, q: str) -> float:
            qset = set(w.lower() for w in q.split())
            tset = set(w.lower() for w in text.split())
            if not qset or not tset: return 0.0
            return len(qset & tset) / max(len(qset), 1)

        sims = [1.0 - min(max(d, 0.0), 2.0)/2.0 for d in distances]
        lex = [lexical_score(d, query) for d in docs]
        fused = [0.8*s + 0.2*l for s,l in zip(sims, lex)]
        ranked = sorted(zip(fused, ids, docs, metas), key=lambda x: x[0], reverse=True)[:k]
        return {"ids": [r[1] for r in ranked], "documents": [r[2] for r in ranked], "metadatas": [r[3] for r in ranked], "scores": [r[0] for r in ranked]}

    # Admin purge operations (best-effort, simple where)
    def list_messages(self, where: Optional[Dict[str, Any]] = None, limit: int = 50) -> Dict[str, Any]:
        try:
            res = self.messages.get(where=where or {}, limit=limit)
            items = [{"id": i, "text": d, "meta": m} for i, d, m in zip(res.get("ids", []), res.get("documents", []), res.get("metadatas", []))]
            return {"items": items}
        except Exception:
            return {"items": []}

    def delete_messages(self, where: Optional[Dict[str, Any]] = None) -> int:
        try:
            res = self.messages.get(where=where or {})
            ids = res.get("ids", [])
            if not ids: return 0
            self.messages.delete(ids=ids)
            return len(ids)
        except Exception:
            return 0

    def counts(self) -> Dict[str, int]:
        def safe_count(col):
            try: return col.count()
            except Exception: return 0
        return {"messages": safe_count(self.messages), "self_context": safe_count(self.self_context), "entities": safe_count(self.entities), "archives": safe_count(self.archives)}
