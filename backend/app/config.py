from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/auth/github/callback"
    github_webhook_secret: str = ""

    session_secret: str = "change-me-in-production"
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"

    database_url: str = "sqlite+aiosqlite:///./codelens.db"

    cursor_api_key: str = ""
    cursor_model: str = "composer-2.5"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"


settings = Settings()
