from fastapi import Request

from agent_runtime.store import AgentStore
from config import AgentConfig, Config


def get_store(request: Request) -> AgentStore:
    return request.app.state.store


def get_config(request: Request) -> Config:
    return request.app.state.config


def get_agent_config(request: Request) -> AgentConfig:
    return request.app.state.config.agent
