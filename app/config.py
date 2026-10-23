from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required: no built-in default, so a missing setting fails fast instead of using guessed credentials
    database_url: str

    # URL pública de la web (a donde vuelve el navegador tras autorizar en el banco)
    public_url: str = "http://localhost:3000"

    # Sesión de login
    session_days: int = 14
    cookie_secure: bool = False  # True en cuanto se sirva por HTTPS

    # Enable Banking
    eb_api_url: str = "https://api.enablebanking.com"
    eb_application_id: str = ""
    eb_private_key_path: str = "/run/secrets/eb_private_key"
    eb_country: str = "ES"
    eb_consent_days: int = 180

    # Sincronización automática (horas, separadas por comas, hora local del contenedor)
    sync_hours: str = "7,19"
    initial_history_days: int = 730

    @property
    def eb_redirect_url(self) -> str:
        return f"{self.public_url}/api/banks/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
