"""Konfigurasi aplikasi. Semua secret hanya dibaca dari environment variable."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    app_name: str = "AI Recruitment Assistant"
    environment: str = "development"

    # --- Database ---
    database_url: str = "sqlite:///./data/app.db"

    # --- Auth ---
    secret_key: str = Field(default="", alias="SECRET_KEY")
    jwt_secret: str = Field(default="", alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 8
    admin_email: str = "admin@example.com"
    admin_password: str = Field(default="", alias="ADMIN_PASSWORD")
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- File upload ---
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 5
    retention_days: int = 180

    # --- Embedding ---
    # auto = pakai sentence-transformers bila terpasang, kalau tidak pakai HashingEmbedder (offline).
    embedding_backend: str = "auto"  # auto | sentence-transformers | hashing
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # --- LLM ---
    # none = analisis berbasis aturan (tanpa jaringan). anthropic | openai_compatible untuk LLM sungguhan.
    llm_provider: str = "none"
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-5-5"
    llm_base_url: str = ""  # untuk openai_compatible (Ollama/vLLM, mis. http://ollama:11434/v1)
    llm_timeout_s: int = 60

    output_language: str = "id"  # bahasa penjelasan AI: id | en

    # --- Matching ---
    w_skill: float = 0.40
    w_experience: float = 0.30
    w_education: float = 0.15
    w_project: float = 0.15

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
