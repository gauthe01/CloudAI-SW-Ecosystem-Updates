import ssl
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI

from app.core.config import Settings, get_settings

SUPPORTED_OPENAI_COMPATIBLE_PROVIDERS = {
    "enterprise_openai_compatible",
    "openai_compatible",
}
DISABLED_AI_PROVIDERS = {"", "disabled", "none"}


class AIRuntimeConfigurationError(RuntimeError):
    """Raised when AI runtime settings are incomplete or intentionally disabled."""


class AIProviderUnsupportedError(AIRuntimeConfigurationError):
    """Raised when a configured AI provider has no runtime implementation."""


@dataclass(frozen=True)
class AIClientRuntime:
    provider: str
    base_url: str
    update_extraction_model: str
    reporting_model: str | None
    timeout_seconds: float
    max_retries: int
    ca_bundle: str | None
    client: AsyncOpenAI


def normalize_ai_provider(provider: str | None) -> str:
    return (provider or "disabled").strip().lower().replace("-", "_")


def is_ai_enabled(settings: Settings | None = None) -> bool:
    runtime_settings = settings or get_settings()
    return normalize_ai_provider(runtime_settings.ai_provider) not in DISABLED_AI_PROVIDERS


def get_ai_runtime_config(settings: Settings | None = None) -> dict[str, str | float | int | None]:
    runtime_settings = settings or get_settings()
    provider = normalize_ai_provider(runtime_settings.ai_provider)
    return {
        "provider": provider,
        "base_url": runtime_settings.ai_base_url,
        "update_extraction_model": runtime_settings.ai_model_update_extraction,
        "reporting_model": runtime_settings.ai_model_reporting,
        "timeout_seconds": runtime_settings.ai_timeout_seconds,
        "max_retries": runtime_settings.ai_max_retries,
        "ca_bundle": runtime_settings.ai_ca_bundle,
    }


def require_ai_runtime_config(settings: Settings | None = None) -> Settings:
    runtime_settings = settings or get_settings()
    provider = normalize_ai_provider(runtime_settings.ai_provider)
    if provider in DISABLED_AI_PROVIDERS:
        raise AIRuntimeConfigurationError(
            "AI runtime is disabled. Set AI_PROVIDER=enterprise_openai_compatible to enable it.",
        )
    if provider not in SUPPORTED_OPENAI_COMPATIBLE_PROVIDERS:
        raise AIProviderUnsupportedError(
            f"AI_PROVIDER={runtime_settings.ai_provider!r} is not supported.",
        )
    if not clean_setting(runtime_settings.ai_base_url):
        raise AIRuntimeConfigurationError("AI_BASE_URL is required for the AI runtime.")
    if not clean_setting(runtime_settings.ai_api_key):
        raise AIRuntimeConfigurationError("AI_API_KEY is required for the AI runtime.")
    if not clean_setting(runtime_settings.ai_model_update_extraction):
        raise AIRuntimeConfigurationError(
            "AI_MODEL_UPDATE_EXTRACTION is required for source-event extraction.",
        )
    if runtime_settings.ai_timeout_seconds <= 0:
        raise AIRuntimeConfigurationError("AI_TIMEOUT_SECONDS must be greater than zero.")
    if runtime_settings.ai_max_retries < 0:
        raise AIRuntimeConfigurationError("AI_MAX_RETRIES cannot be negative.")
    return runtime_settings


def build_async_openai_client(settings: Settings | None = None) -> AsyncOpenAI:
    runtime_settings = require_ai_runtime_config(settings)
    kwargs: dict[str, object] = {
        "api_key": runtime_settings.ai_api_key,
        "base_url": clean_setting(runtime_settings.ai_base_url).rstrip("/"),
        "timeout": runtime_settings.ai_timeout_seconds,
        "max_retries": runtime_settings.ai_max_retries,
    }
    http_client = build_openai_http_client(runtime_settings)
    if http_client is not None:
        kwargs["http_client"] = http_client
    return AsyncOpenAI(**kwargs)


def build_openai_http_client(settings: Settings) -> httpx.AsyncClient | None:
    ca_bundle = clean_setting(settings.ai_ca_bundle)
    if ca_bundle:
        return httpx.AsyncClient(
            verify=ca_bundle,
            timeout=settings.ai_timeout_seconds,
        )

    ssl_context = build_system_trust_ssl_context()
    if ssl_context is None:
        return None

    return httpx.AsyncClient(
        verify=ssl_context,
        timeout=settings.ai_timeout_seconds,
    )


def build_system_trust_ssl_context() -> ssl.SSLContext | None:
    try:
        import truststore
    except ImportError:
        return None

    try:
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        return None


def build_ai_client_runtime(settings: Settings | None = None) -> AIClientRuntime:
    runtime_settings = require_ai_runtime_config(settings)
    return AIClientRuntime(
        provider=normalize_ai_provider(runtime_settings.ai_provider),
        base_url=clean_setting(runtime_settings.ai_base_url).rstrip("/"),
        update_extraction_model=clean_setting(runtime_settings.ai_model_update_extraction),
        reporting_model=clean_setting(runtime_settings.ai_model_reporting),
        timeout_seconds=runtime_settings.ai_timeout_seconds,
        max_retries=runtime_settings.ai_max_retries,
        ca_bundle=clean_setting(runtime_settings.ai_ca_bundle),
        client=build_async_openai_client(runtime_settings),
    )


def clean_setting(value: str | None) -> str:
    return (value or "").strip()
