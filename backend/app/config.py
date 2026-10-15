from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    app_env: str = "local"
    api_prefix: str = "/api"
    supabase_url: str = ""
    supabase_key: str = ""
    upstage_api_key: str = ""
    cors_origins: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)
settings = Settings()
