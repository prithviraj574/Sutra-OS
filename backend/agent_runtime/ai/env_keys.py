from __future__ import annotations

import os


ENV_KEYS: dict[str, list[str]] = {
    "github-copilot": ["COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"],
    "anthropic": ["ANTHROPIC_OAUTH_TOKEN", "ANTHROPIC_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "azure-openai-responses": ["AZURE_OPENAI_API_KEY"],
    "deepseek": ["DEEPSEEK_API_KEY"],
    "google": ["GEMINI_API_KEY"],
    "google-vertex": ["GOOGLE_CLOUD_API_KEY"],
    "groq": ["GROQ_API_KEY"],
    "cerebras": ["CEREBRAS_API_KEY"],
    "xai": ["XAI_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "vercel-ai-gateway": ["AI_GATEWAY_API_KEY"],
    "zai": ["ZAI_API_KEY"],
    "mistral": ["MISTRAL_API_KEY"],
    "minimax": ["MINIMAX_API_KEY"],
    "minimax-cn": ["MINIMAX_CN_API_KEY"],
    "huggingface": ["HF_TOKEN"],
    "fireworks": ["FIREWORKS_API_KEY"],
    "opencode": ["OPENCODE_API_KEY"],
    "opencode-go": ["OPENCODE_API_KEY"],
    "kimi-coding": ["KIMI_API_KEY"],
}


def find_env_keys(provider: str) -> list[str] | None:
    keys = [key for key in ENV_KEYS.get(provider, []) if os.getenv(key)]
    return keys or None


def get_env_api_key(provider: str) -> str | None:
    keys = find_env_keys(provider)
    if keys:
        return os.getenv(keys[0])
    if provider == "amazon-bedrock" and (
        os.getenv("AWS_PROFILE")
        or (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))
        or os.getenv("AWS_BEARER_TOKEN_BEDROCK")
    ):
        return "<authenticated>"
    if provider == "google-vertex" and (
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        and (os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT"))
        and os.getenv("GOOGLE_CLOUD_LOCATION")
    ):
        return "<authenticated>"
    return None
