from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required: no built-in default, so a missing setting fails fast instead of using guessed credentials
    database_url: str

    # Public URL of the web app (where the browser returns after authorizing at the bank)
    public_url: str = "http://localhost:3000"

    # Login session
    session_days: int = 14
    cookie_secure: bool = False  # True as soon as it is served over HTTPS

    # Enable Banking
    eb_api_url: str = "https://api.enablebanking.com"
    eb_application_id: str = ""
    eb_private_key_path: str = "/run/secrets/eb_private_key"
    eb_country: str = "ES"
    eb_consent_days: int = 180

    # Automatic sync (comma-separated hours, container local time)
    sync_hours: str = "7,19"
    initial_history_days: int = 730

    @property
    def eb_redirect_url(self) -> str:
        return f"{self.public_url}/api/banks/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
