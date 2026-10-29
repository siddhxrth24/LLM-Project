from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root: 3 levels up from backend/app/core (core -> app -> backend -> project_root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "sqlite:///./data/semestrack.db"

    # File storage
    UPLOAD_DIR: str = "./data/uploads"
    CHROMA_DIR: str = "./data/chroma"

    # Models
    LLM_MODEL_ID: str = "Qwen/Qwen3.5-0.8B"
    LLM_MODEL_PATH: str = "./models/llm"
    EMBEDDING_MODEL_ID: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_MODEL_PATH: str = "./models/embeddings"

    # LoRA
    LORA_ADAPTER_PATH: str = ""
    LORA_ENABLED: bool = False

    # Inference
    MAX_NEW_TOKENS: int = 1024
    TEMPERATURE: float = 0.7
    TOP_P: float = 0.9
    CONTEXT_WINDOW: int = 2048

    # Fine-tuning defaults
    FINETUNE_BATCH_SIZE: int = 1
    FINETUNE_GRAD_ACCUM_STEPS: int = 4
    FINETUNE_EPOCHS: int = 3
    FINETUNE_LR: float = 2e-4
    FINETUNE_LORA_RANK: int = 8
    FINETUNE_MAX_SEQ_LEN: int = 512

    # OCR (optional)
    TESSERACT_PATH: str = ""
    OCR_ENABLED: bool = False

    # Security
    SECRET_KEY: str = "change-me-in-production"

    # Application metadata
    APP_NAME: str = "SemesTrack Backend"
    APP_VERSION: str = "0.1.0"

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def resolved_upload_dir(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p.resolve()

    @property
    def resolved_chroma_dir(self) -> Path:
        p = Path(self.CHROMA_DIR)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p.resolve()

    @property
    def resolved_llm_model_path(self) -> Path:
        p = Path(self.LLM_MODEL_PATH)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p.resolve()

    @property
    def resolved_embedding_model_path(self) -> Path:
        p = Path(self.EMBEDDING_MODEL_PATH)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p.resolve()

    @property
    def resolved_lora_path(self) -> Optional[Path]:
        if not self.LORA_ADAPTER_PATH or not self.LORA_ADAPTER_PATH.strip():
            return None
        p = Path(self.LORA_ADAPTER_PATH.strip())
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p.resolve()

    @property
    def resolved_database_url(self) -> str:
        """Resolve SQLite relative paths to absolute paths to prevent DB fragmentation."""
        url = self.DATABASE_URL
        sqlite_prefix = "sqlite:///"
        if url.startswith(sqlite_prefix):
            raw_path = url[len(sqlite_prefix):]
            # Handle in-memory database
            if raw_path == ":memory:":
                return url
            db_path = Path(raw_path)
            if not db_path.is_absolute():
                db_path = (PROJECT_ROOT / db_path).resolve()
            # On Windows, path representation with forward slashes for sqlite url
            return f"sqlite:///{db_path.as_posix()}"
        return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
