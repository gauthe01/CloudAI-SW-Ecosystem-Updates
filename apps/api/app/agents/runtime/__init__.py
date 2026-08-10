"""Shared AI runtime primitives."""

from app.agents.runtime.client import (
    AIClientRuntime,
    AIProviderUnsupportedError,
    AIRuntimeConfigurationError,
    build_ai_client_runtime,
    build_async_openai_client,
    get_ai_runtime_config,
    is_ai_enabled,
    normalize_ai_provider,
    require_ai_runtime_config,
)

__all__ = [
    "AIClientRuntime",
    "AIProviderUnsupportedError",
    "AIRuntimeConfigurationError",
    "build_ai_client_runtime",
    "build_async_openai_client",
    "get_ai_runtime_config",
    "is_ai_enabled",
    "normalize_ai_provider",
    "require_ai_runtime_config",
]
