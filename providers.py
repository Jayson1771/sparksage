from __future__ import annotations

import time
from openai import OpenAI
import config


def _create_client(provider_name: str) -> OpenAI | None:
    """Create an OpenAI-compatible client for the given provider."""
    provider = config.PROVIDERS.get(provider_name)
    if not provider or not provider["api_key"]:
        return None

    extra_headers = {}
    if provider_name == "anthropic":
        extra_headers["anthropic-version"] = "2023-06-01"

    return OpenAI(
        base_url=provider["base_url"],
        api_key=provider["api_key"],
        default_headers=extra_headers or None,
    )


def _build_fallback_order() -> list[str]:
    """Build the provider fallback order: primary first, then free providers."""
    primary = config.AI_PROVIDER
    order = [primary]
    for name in config.FREE_FALLBACK_CHAIN:
        if name not in order:
            order.append(name)
    return order


def _build_clients() -> dict[str, OpenAI]:
    """Build clients for all configured providers."""
    clients = {}
    for name in set([config.AI_PROVIDER] + config.FREE_FALLBACK_CHAIN + list(config.PROVIDERS.keys())):
        client = _create_client(name)
        if client:
            clients[name] = client
    return clients


# Pre-build clients for all configured providers
_clients: dict[str, OpenAI] = _build_clients()
FALLBACK_ORDER = _build_fallback_order()


def reload_clients():
    """Rebuild all clients and fallback order from current config."""
    global _clients, FALLBACK_ORDER
    _clients = _build_clients()
    FALLBACK_ORDER = _build_fallback_order()


def get_available_providers() -> list[str]:
    """Return list of provider names that have valid API keys configured."""
    # Always rebuild from current config to avoid stale state
    order = _build_fallback_order()
    clients = _build_clients()
    return [name for name in order if name in clients]


def test_provider(name: str) -> dict:
    """Test a provider with a minimal API call."""
    provider = config.PROVIDERS.get(name)
    if not provider:
        return {"success": False, "latency_ms": 0, "error": f"Unknown provider: {name}"}

    client = _create_client(name)
    if not client:
        return {"success": False, "latency_ms": 0, "error": "No API key configured"}

    try:
        start = time.time()
        response = client.chat.completions.create(
            model=provider["model"],
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}],
        )
        latency = int((time.time() - start) * 1000)
        return {"success": True, "latency_ms": latency, "error": None}
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        return {"success": False, "latency_ms": latency, "error": str(e)}


def chat(messages: list[dict], system_prompt: str) -> tuple[str, str]:
    """Send messages to AI using current primary provider with fallback.
    Always rebuilds fallback order from current config.AI_PROVIDER.
    """
    # Always use current config - never stale module-level FALLBACK_ORDER
    fallback_order = _build_fallback_order()
    clients = _build_clients()
    errors = []

    print(f"[providers.chat] primary={config.AI_PROVIDER} order={fallback_order}")

    for provider_name in fallback_order:
        client = clients.get(provider_name)
        if not client:
            continue

        provider = config.PROVIDERS[provider_name]
        try:
            response = client.chat.completions.create(
                model=provider["model"],
                max_tokens=config.MAX_TOKENS,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages,
                ],
            )
            text = response.choices[0].message.content
            print(f"[providers.chat] succeeded with {provider_name}")
            return text, provider_name

        except Exception as e:
            errors.append(f"{provider['name']}: {e}")
            print(f"[providers.chat] {provider_name} failed: {e}")
            continue

    error_details = "\n".join(errors)
    raise RuntimeError(f"All providers failed:\n{error_details}")


def chat_with_provider(messages: list[dict], system_prompt: str, provider_name: str) -> tuple[str, str]:
    """Send messages to a specific provider, falling back to default chain if it fails."""
    client = _create_client(provider_name)
    if not client:
        return chat(messages, system_prompt)

    provider = config.PROVIDERS.get(provider_name)
    if not provider:
        return chat(messages, system_prompt)

    try:
        response = client.chat.completions.create(
            model=provider["model"],
            max_tokens=config.MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                *messages,
            ],
        )
        return response.choices[0].message.content, provider_name
    except Exception as e:
        print(f"Channel provider {provider_name} failed: {e}. Falling back.")
        return chat(messages, system_prompt)