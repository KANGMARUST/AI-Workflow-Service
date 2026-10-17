from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_env: str = "local"
    api_prefix: str = "/api"
    data_dir: Path = ROOT / ".runtime"
    database_url: SecretStr = SecretStr("")
    auto_create_schema: bool = False
    supabase_url: str = ""
    supabase_key: SecretStr = SecretStr("")
    upstage_api_key: SecretStr = SecretStr("")
    upstage_base_url: str = "https://api.upstage.ai/v2"
    chat_base_url: str = "https://api.upstage.ai/v1"
    chat_model: str = "solar-pro4"
    chat_allowed_models: str = "solar-pro4,solar-mini4"
    chat_timeout_seconds: float = Field(default=60, ge=1, le=180)
    chat_max_tokens: int = Field(default=2048, ge=256, le=8192)
    chat_max_context_characters: int = Field(default=60000, ge=2000, le=200000)
    chat_history_messages: int = Field(default=20, ge=2, le=100, multiple_of=2)
    extraction_provider: str = "auto"
    quote_extract_agent_id: str = "agt_PDRAagZCX2rzbqfEm7J5QA"
    quote_extract_config_id: str = "3"
    quote_compare_agent_id: str = "agt_Tm6UnDBS47q2W3EJ5NEQKQ"
    quote_compare_config_id: str = "1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    api_token: SecretStr = SecretStr("")
    max_upload_mb: int = Field(default=20, ge=1, le=100)
    max_document_pages: int = Field(default=100, ge=1, le=1000)
    agent_timeout_seconds: float = Field(default=180, ge=1, le=900)
    agent_poll_seconds: float = Field(default=2, ge=0.01, le=30)
    pdf_font_path: Path | None = None
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", case_sensitive=False)

    @property
    def available_chat_models(self):
        return list(dict.fromkeys([self.chat_model, *[m.strip() for m in self.chat_allowed_models.split(",") if m.strip()]]))


settings = Settings()
