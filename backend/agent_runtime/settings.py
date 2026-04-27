from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    postgres_url: str = Field(..., alias="POSTGRES_URL")
    default_provider: str = "faux"
    default_api: str = "faux"
    default_model: str = "faux-tool-model"
    default_system_prompt: str = "You are a helpful multi-tool agent."


@lru_cache
def get_settings() -> Settings:
    return Settings()
