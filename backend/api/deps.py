from fastapi import Request

from agent_runtime.repository import AgentRepository
from agent_runtime.settings import Settings


def get_repository(request: Request) -> AgentRepository:
    return request.app.state.repository


def get_settings(request: Request) -> Settings:
    return request.app.state.settings
