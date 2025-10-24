from __future__ import annotations

import random

import vertexai
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingModel

from fibz_bot.config import settings
from fibz_bot.utils.backoff import retry
from fibz_bot.utils.logging import get_logger
from fibz_bot.utils.metrics import record_model_choice

log = get_logger(__name__)

def init_vertex():
    vertexai.init(project=settings.VERTEX_PROJECT_ID, location=settings.VERTEX_LOCATION)
    aiplatform.init(project=settings.VERTEX_PROJECT_ID, location=settings.VERTEX_LOCATION)

class ModelRouter:
    """Route between Flash and Pro; escalate for long/complex turns."""
    def __init__(self):
        init_vertex()
        self.model_flash = GenerativeModel(settings.VERTEX_MODEL_FLASH)
        self.model_pro = GenerativeModel(settings.VERTEX_MODEL_PRO)
        self.embed_model = TextEmbeddingModel.from_pretrained(settings.VERTEX_EMBED_MODEL)

    def choose_model(self, prompt_tokens: int, needs_reasoning: bool = False) -> GenerativeModel:
        if needs_reasoning or prompt_tokens > 3000:
            model = self.model_pro
            tier = "pro"
        else:
            if random.random() < settings.DEFAULT_FLASH_RATIO:
                model = self.model_flash
                tier = "flash"
            else:
                model = self.model_pro
                tier = "pro"
        record_model_choice(tier)
        log.info("model_choice", extra={"extra_fields": {"tier": tier, "prompt_tokens": prompt_tokens}})
        return model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings = retry(
            lambda: self.embed_model.get_embeddings(texts),
            operation="vertex_embed",
        )
        return [e.values for e in embeddings]

try:
    from vertexai.generative_models import GenerativeModel, Part, Content, SafetySetting, GenerationConfig
except ImportError:
    # Older SDKs used the preview path; keep linters quiet too
    from vertexai.preview.generative_models import GenerativeModel, Part, Content, SafetySetting, GenerationConfig  # type: ignore[reportMissingImports]
