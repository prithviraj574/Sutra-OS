from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=("backend/.env", ".env", "../.env"), extra="ignore")

    postgres_url: str = Field(..., alias="POSTGRES_URL")
    frontend_origin: str = Field("http://localhost:5173", alias="SUTRA_FRONTEND_URL")
    openapi_url: str = "http://localhost:8000/openapi.json"

    @property
    def cors_origins(self) -> list[str]:
        origins = {
            self.frontend_origin.rstrip("/"),
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        }
        return sorted(origins)


class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=("backend/.env", ".env", "../.env"), extra="ignore")

    default_provider: str = "faux"
    default_api: str = "faux"
    default_model: str = "faux-tool-model"
    default_system_prompt: str = "You are a helpful multi-tool agent."


class Config:
    def __init__(
        self,
        *,
        app: AppConfig | None = None,
        agent: AgentConfig | None = None,
    ) -> None:
        self.app = app or AppConfig()
        self.agent = agent or AgentConfig()


@lru_cache
def get_config() -> Config:
    return Config()
