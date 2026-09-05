from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:5173/auth/github/callback"
    github_webhook_secret: str = ""

    # GitHub App (production: webhooks, Checks API, PR comments)
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_app_private_key_path: str = ""
    github_app_slug: str = "codelens"
    enable_github_checks: bool = True
    enable_github_pr_comments: bool = False
    auto_post_pr_comment_on_webhook: bool = False

    # Signed embed URLs for github.com iframe / check details links
    embed_shared_secret: str = ""
    embed_allowed_frame_ancestors: str = "https://github.com"

    session_secret: str = "change-me-in-production"
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"

    database_url: str = "sqlite+aiosqlite:///./codelens.db"

    cursor_api_key: str = ""
    cursor_model: str = "composer-2.5"

    # AI summaries — provider: openai | groq | perplexity | openrouter
    ai_provider: str = "openai"
    ai_api_key: str = ""
    ai_base_url: str = ""
    ai_model: str = ""
    groq_api_key: str = ""
    # Legacy OpenAI vars (still supported)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    def resolved_ai_key(self) -> str:
        provider = (self.ai_provider or "openai").lower()
        if provider == "groq":
            return self.ai_api_key or self.groq_api_key or self.openai_api_key
        return self.ai_api_key or self.openai_api_key

    def resolved_ai_provider(self) -> str:
        if self.groq_api_key and not self.ai_api_key and self.ai_provider == "openai":
            return "groq"
        return (self.ai_provider or "openai").lower()

    def github_app_configured(self) -> bool:
        """True when GitHub App credentials exist (webhooks + Checks + app-authenticated API)."""
        return bool(self.github_app_id and (self.github_app_private_key or self.github_app_private_key_path))

    def embed_configured(self) -> bool:
        """True when signed embed tokens can be issued for github.com iframe/details links."""
        return bool(self.embed_shared_secret)


settings = Settings()
