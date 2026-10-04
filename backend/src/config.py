from __future__ import annotations

from pathlib import Path
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # "llm" now; "bhashini" / AI4Bharat not implemented yet
    indic_provider: str = "llm"

    app_env: str = "development"
    log_level: str = "INFO"
    # cors_origins: str = "http://localhost:3000"
    cors_origins: str = "https://hacknation7.vercel.app,http://localhost:3000"
    gateway_shared_secret: str = "change-me"

    # --- Small model tier: Gemini ---
    google_api_key: str = Field(default="", repr=False)
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_fallback_model: str = "gemini-3.1-flash-lite"
    gemini_thinking_level: str = ""
    gemini_timeout_s: float = 30.0

    # --- Fallback tier: Claude ---
    anthropic_api_key: str = Field(default="", repr=False)
    claude_model: str = "claude-sonnet-5-5"
    claude_timeout_s: float = 30.0

    confidence_threshold: float = 0.65
    small_llm_provider: str = "gemini"  # "gemini" | "local" (local is disabled)

    # --- Local AI: Ministral-8B (DISABLED, uncomment to re-enable) ---
    # local_ai_url: str = "http://localhost:8080"
    # local_ai_token: str = Field(default="", repr=False)
    # local_ai_model: str = "Ministral-8B-Instruct-2410-Q4_K_M.gguf"
    # local_ai_timeout_s: float = 30.0

    translator_backend: str = "gemini"  # "gemini" | "claude"

    sqlite_path: str = "./output/knowledge.db"
    data_dir: str = "../data"
    output_dir: str = "./output"

    emergency_webhook_url: str = ""

    @property
    def sqlite_file(self) -> Path:
        p = Path(self.sqlite_path)
        return p if p.is_absolute() else (BACKEND_ROOT / p).resolve()

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        return p if p.is_absolute() else (BACKEND_ROOT / p).resolve()

    @property
    def output_path(self) -> Path:
        p = Path(self.output_dir)
        return p if p.is_absolute() else (BACKEND_ROOT / p).resolve()

    def require_keys(self) -> None:
        """Fail fast at startup if a needed key is missing."""
        missing = []
        if self.small_llm_provider == "gemini" and not self.google_api_key:
            missing.append("GOOGLE_API_KEY")
        if not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
