"""Cost calculation utilities for AI provider usage."""
from __future__ import annotations


# Pricing per 1M tokens in USD
# Update these when provider pricing changes
PROVIDER_PRICING: dict[str, dict[str, float]] = {
    "gemini": {"input_per_1m": 0.0, "output_per_1m": 0.0},
    "groq":   {"input_per_1m": 0.0, "output_per_1m": 0.0},
    "openrouter": {"input_per_1m": 0.0, "output_per_1m": 0.0},
    "anthropic": {"input_per_1m": 3.00, "output_per_1m": 15.00},
    "openai":    {"input_per_1m": 2.50, "output_per_1m": 10.00},
}


def calculate_cost(
    provider: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Calculate the estimated cost in USD for a provider API call."""
    pricing = PROVIDER_PRICING.get(provider, {"input_per_1m": 0.0, "output_per_1m": 0.0})
    input_cost  = (input_tokens  / 1_000_000) * pricing["input_per_1m"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_1m"]
    return round(input_cost + output_cost, 8)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return max(1, len(text) // 4)


def estimate_cost_from_text(
    provider: str,
    input_text: str,
    output_text: str,
) -> tuple[int, int, float]:
    """
    Estimate cost from raw text when exact token counts aren't available.
    Returns (input_tokens, output_tokens, estimated_cost).
    """
    input_tokens  = estimate_tokens(input_text)
    output_tokens = estimate_tokens(output_text)
    cost = calculate_cost(provider, input_tokens, output_tokens)
    return input_tokens, output_tokens, cost


def format_cost(cost: float) -> str:
    """Format a cost value for display."""
    if cost == 0.0:
        return "Free"
    if cost < 0.001:
        return f"${cost:.6f}"
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def get_provider_pricing_display() -> list[dict]:
    """Get provider pricing info for dashboard display."""
    return [
        {
            "provider": provider,
            "input_per_1m": pricing["input_per_1m"],
            "output_per_1m": pricing["output_per_1m"],
            "free": pricing["input_per_1m"] == 0 and pricing["output_per_1m"] == 0,
        }
        for provider, pricing in PROVIDER_PRICING.items()
    ]