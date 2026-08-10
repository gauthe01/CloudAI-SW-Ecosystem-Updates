import pytest

from app.agents.runtime import client as ai_client
from app.core.config import Settings


def settings_with(**overrides: object) -> Settings:
    settings = Settings()
    return settings.model_copy(update=overrides)


def test_ai_runtime_is_disabled_by_default() -> None:
    settings = settings_with(ai_provider="disabled")

    assert ai_client.is_ai_enabled(settings) is False
    with pytest.raises(ai_client.AIRuntimeConfigurationError, match="disabled"):
        ai_client.require_ai_runtime_config(settings)


def test_ai_runtime_requires_enterprise_base_url_key_and_model() -> None:
    settings = settings_with(
        ai_provider="enterprise_openai_compatible",
        ai_base_url="",
        ai_api_key="secret",
        ai_model_update_extraction="model-a",
    )
    with pytest.raises(ai_client.AIRuntimeConfigurationError, match="AI_BASE_URL"):
        ai_client.require_ai_runtime_config(settings)

    settings = settings_with(
        ai_provider="enterprise_openai_compatible",
        ai_base_url="https://enterprise.example.com/v1",
        ai_api_key="",
        ai_model_update_extraction="model-a",
    )
    with pytest.raises(ai_client.AIRuntimeConfigurationError, match="AI_API_KEY"):
        ai_client.require_ai_runtime_config(settings)

    settings = settings_with(
        ai_provider="enterprise_openai_compatible",
        ai_base_url="https://enterprise.example.com/v1",
        ai_api_key="secret",
        ai_model_update_extraction="",
    )
    with pytest.raises(ai_client.AIRuntimeConfigurationError, match="AI_MODEL_UPDATE_EXTRACTION"):
        ai_client.require_ai_runtime_config(settings)


def test_ai_runtime_rejects_unknown_provider() -> None:
    settings = settings_with(
        ai_provider="random-provider",
        ai_base_url="https://enterprise.example.com/v1",
        ai_api_key="secret",
        ai_model_update_extraction="model-a",
    )

    with pytest.raises(ai_client.AIProviderUnsupportedError, match="not supported"):
        ai_client.require_ai_runtime_config(settings)


def test_openai_compatible_client_is_built_without_network_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, object] = {}

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured_kwargs.update(kwargs)

    monkeypatch.setattr(ai_client, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(ai_client, "build_system_trust_ssl_context", lambda: None)
    settings = settings_with(
        ai_provider="enterprise-openai-compatible",
        ai_base_url="https://enterprise.example.com/v1/",
        ai_api_key="secret",
        ai_model_update_extraction="updates-model",
        ai_model_reporting="reporting-model",
        ai_timeout_seconds=30.0,
        ai_max_retries=1,
        ai_ca_bundle=None,
    )

    runtime = ai_client.build_ai_client_runtime(settings)

    assert runtime.provider == "enterprise_openai_compatible"
    assert runtime.base_url == "https://enterprise.example.com/v1"
    assert runtime.update_extraction_model == "updates-model"
    assert runtime.reporting_model == "reporting-model"
    assert captured_kwargs == {
        "api_key": "secret",
        "base_url": "https://enterprise.example.com/v1",
        "timeout": 30.0,
        "max_retries": 1,
    }


def test_openai_compatible_client_supports_enterprise_ca_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_openai_kwargs: dict[str, object] = {}
    captured_httpx_kwargs: dict[str, object] = {}

    class FakeHttpClient:
        def __init__(self, **kwargs: object) -> None:
            captured_httpx_kwargs.update(kwargs)

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured_openai_kwargs.update(kwargs)

    monkeypatch.setattr(ai_client.httpx, "AsyncClient", FakeHttpClient)
    monkeypatch.setattr(ai_client, "AsyncOpenAI", FakeAsyncOpenAI)
    settings = settings_with(
        ai_provider="enterprise_openai_compatible",
        ai_base_url="https://enterprise.example.com/v1",
        ai_api_key="secret",
        ai_model_update_extraction="updates-model",
        ai_ca_bundle="/etc/ssl/certs/enterprise-ca.pem",
    )

    ai_client.build_async_openai_client(settings)

    assert captured_httpx_kwargs == {
        "verify": "/etc/ssl/certs/enterprise-ca.pem",
        "timeout": 45.0,
    }
    assert "http_client" in captured_openai_kwargs


def test_openai_compatible_client_uses_system_trust_store_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_openai_kwargs: dict[str, object] = {}
    captured_httpx_kwargs: dict[str, object] = {}
    fake_ssl_context = object()

    class FakeHttpClient:
        def __init__(self, **kwargs: object) -> None:
            captured_httpx_kwargs.update(kwargs)

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured_openai_kwargs.update(kwargs)

    monkeypatch.setattr(ai_client.httpx, "AsyncClient", FakeHttpClient)
    monkeypatch.setattr(ai_client, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(
        ai_client,
        "build_system_trust_ssl_context",
        lambda: fake_ssl_context,
    )
    settings = settings_with(
        ai_provider="enterprise_openai_compatible",
        ai_base_url="https://enterprise.example.com/v1",
        ai_api_key="secret",
        ai_model_update_extraction="updates-model",
        ai_ca_bundle=None,
    )

    ai_client.build_async_openai_client(settings)

    assert captured_httpx_kwargs == {
        "verify": fake_ssl_context,
        "timeout": 45.0,
    }
    assert "http_client" in captured_openai_kwargs
