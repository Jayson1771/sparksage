from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class SlidingWindow:
    """Sliding window rate limiter for a single key."""
    limit: int
    window_seconds: int
    timestamps: list[float] = field(default_factory=list)

    def is_allowed(self) -> bool:
        """Check if a new request is allowed and record it if so."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Remove timestamps outside the window
        self.timestamps = [t for t in self.timestamps if t > cutoff]

        if len(self.timestamps) >= self.limit:
            return False

        self.timestamps.append(now)
        return True

    def retry_after(self) -> float:
        """Seconds until the next request is allowed."""
        if not self.timestamps:
            return 0
        oldest = min(self.timestamps)
        return max(0, self.window_seconds - (time.time() - oldest))

    def requests_remaining(self) -> int:
        """Number of requests remaining in the current window."""
        now = time.time()
        cutoff = now - self.window_seconds
        active = [t for t in self.timestamps if t > cutoff]
        return max(0, self.limit - len(active))


class RateLimiter:
    """
    Sliding-window rate limiter supporting per-user and per-guild limits.

    Usage:
        limiter = RateLimiter(user_limit=5, guild_limit=30, window_seconds=60)

        allowed, reason = limiter.check(user_id="123", guild_id="456")
        if not allowed:
            print(f"Rate limited: {reason}")
    """

    def __init__(
        self,
        user_limit: int = 5,
        guild_limit: int = 30,
        window_seconds: int = 60,
    ):
        self.user_limit = user_limit
        self.guild_limit = guild_limit
        self.window_seconds = window_seconds

        self._user_windows: dict[str, SlidingWindow] = defaultdict(
            lambda: SlidingWindow(limit=self.user_limit, window_seconds=self.window_seconds)
        )
        self._guild_windows: dict[str, SlidingWindow] = defaultdict(
            lambda: SlidingWindow(limit=self.guild_limit, window_seconds=self.window_seconds)
        )

    def check(self, user_id: str, guild_id: str | None = None) -> tuple[bool, str | None]:
        """
        Check if a request is allowed.
        Returns (allowed: bool, reason: str | None)
        """
        # Check guild limit first
        if guild_id:
            guild_window = self._guild_windows[guild_id]
            if not guild_window.is_allowed():
                retry = guild_window.retry_after()
                return False, f"This server is sending too many requests. Try again in {retry:.0f}s."

        # Check user limit
        user_window = self._user_windows[user_id]
        if not user_window.is_allowed():
            retry = user_window.retry_after()
            return False, f"You're sending too many requests. Try again in {retry:.0f}s."

        return True, None

    def get_user_status(self, user_id: str) -> dict:
        """Get rate limit status for a user."""
        window = self._user_windows[user_id]
        return {
            "limit": self.user_limit,
            "remaining": window.requests_remaining(),
            "window_seconds": self.window_seconds,
            "retry_after": window.retry_after(),
        }

    def get_guild_status(self, guild_id: str) -> dict:
        """Get rate limit status for a guild."""
        window = self._guild_windows[guild_id]
        return {
            "limit": self.guild_limit,
            "remaining": window.requests_remaining(),
            "window_seconds": self.window_seconds,
            "retry_after": window.retry_after(),
        }

    def reset_user(self, user_id: str):
        """Reset rate limit for a specific user."""
        if user_id in self._user_windows:
            del self._user_windows[user_id]

    def reset_guild(self, guild_id: str):
        """Reset rate limit for a specific guild."""
        if guild_id in self._guild_windows:
            del self._guild_windows[guild_id]

    def update_limits(self, user_limit: int | None = None, guild_limit: int | None = None):
        """Update rate limits at runtime."""
        if user_limit is not None:
            self.user_limit = user_limit
        if guild_limit is not None:
            self.guild_limit = guild_limit


# Global rate limiter instance — imported by cogs
_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    """Get or create the global rate limiter."""
    global _limiter
    if _limiter is None:
        import config
        user_limit = int(getattr(config, "RATE_LIMIT_USER", 5))
        guild_limit = int(getattr(config, "RATE_LIMIT_GUILD", 30))
        _limiter = RateLimiter(
            user_limit=user_limit,
            guild_limit=guild_limit,
            window_seconds=60,
        )
    return _limiter


def reload_limiter():
    """Recreate the limiter with updated config values."""
    global _limiter
    _limiter = None
    return get_limiter()