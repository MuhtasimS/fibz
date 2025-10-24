from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Discord
    DISCORD_BOT_TOKEN: str = Field(..., description="Discord bot token")
    FIBZ_OWNER_ID: str = "0"

    # Vertex
    VERTEX_PROJECT_ID: str
    VERTEX_LOCATION: str = "us-west1"
    VERTEX_MODEL_FLASH: str = "gemini-2.5-flash"
    VERTEX_MODEL_PRO: str = "gemini-2.5-pro"
    VERTEX_EMBED_MODEL: str = "text-embedding-004"

    # Memory
    CHROMA_PATH: str = "./chroma_data"
    ENTITY_REVISION_ENABLED: bool = True
    ENTITY_MAX_FACTS: int = 12
    ENTITY_ALLOW_SENSITIVE: bool = False

    # Policy defaults
    CROSS_CHANNEL_SHARING_DEFAULT: bool = False
    DEFAULT_FLASH_RATIO: float = 0.5

    # Ingestion toggles
    ENABLE_VISION_OCR: bool = False
    SPEECH_LANGUAGE: str = "en-US"

    # Web search (optional)
    GOOGLE_CSE_API_KEY: str | None = None
    GOOGLE_CSE_CX: str | None = None

    # GCS (optional)
    GCS_BUCKET: str | None = None
    GCS_SIGN_URLS: bool = True
    GCS_SIGN_URL_EXPIRY_SECONDS: int = 86400

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()  # singleton
