from __future__ import annotations

import os
import json
import aiosqlite

from api.routes import config

DATABASE_PATH = os.getenv("DATABASE_PATH", "sparksage.db")

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    """Return the shared database connection, creating it if needed."""
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DATABASE_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def init_db():
    """Create tables if they don't exist."""
    db = await get_db()
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT    NOT NULL,
            role       TEXT    NOT NULL,
            content    TEXT    NOT NULL,
            provider   TEXT,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_conv_channel ON conversations(channel_id);

        CREATE TABLE IF NOT EXISTS sessions (
            token      TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS wizard_state (
            id           INTEGER PRIMARY KEY CHECK (id = 1),
            completed    INTEGER NOT NULL DEFAULT 0,
            current_step INTEGER NOT NULL DEFAULT 0,
            data         TEXT    NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS faqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            match_keywords TEXT NOT NULL,
            times_used INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS onboarding_config (
            guild_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (guild_id, key)
        );

        CREATE TABLE IF NOT EXISTS command_permissions (
            command_name TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            role_id TEXT NOT NULL,
            PRIMARY KEY (command_name, guild_id, role_id)
        );

        CREATE TABLE IF NOT EXISTS digest_config (
            guild_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (guild_id, key)
        );

        CREATE TABLE IF NOT EXISTS moderation_config (
            guild_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (guild_id, key)
        );

        CREATE TABLE IF NOT EXISTS moderation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            author_id TEXT NOT NULL,
            content TEXT NOT NULL,
            reason TEXT,
            severity TEXT,
            categories TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS auto_translate_channels (
            guild_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            target_language TEXT NOT NULL,
            PRIMARY KEY (guild_id, channel_id)
        );

        CREATE TABLE IF NOT EXISTS channel_prompts (
            channel_id TEXT PRIMARY KEY,
            guild_id TEXT NOT NULL,
            system_prompt TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS channel_providers (
            guild_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            provider_name TEXT NOT NULL,
            PRIMARY KEY (guild_id, channel_id)
        );

        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            guild_id TEXT,
            channel_id TEXT,
            user_id TEXT,
            provider TEXT,
            tokens_used INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            estimated_cost REAL DEFAULT 0.0,
            latency_ms INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_analytics_guild ON analytics(guild_id);
        CREATE INDEX IF NOT EXISTS idx_analytics_created ON analytics(created_at);

        CREATE TABLE IF NOT EXISTS enabled_plugins (
            guild_id TEXT NOT NULL,
            plugin_name TEXT NOT NULL,
            PRIMARY KEY (guild_id, plugin_name)
        );

        CREATE TABLE IF NOT EXISTS trivia_scores (
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            correct INTEGER DEFAULT 0,
            wrong INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );

        INSERT OR IGNORE INTO wizard_state (id) VALUES (1);
        """
    )
    await db.commit()


# --- Config helpers ---


async def get_config(key: str, default: str | None = None) -> str | None:
    """Get a config value from the database."""
    db = await get_db()
    cursor = await db.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = await cursor.fetchone()
    return row["value"] if row else default


async def get_all_config() -> dict[str, str]:
    """Return all config key-value pairs."""
    db = await get_db()
    cursor = await db.execute("SELECT key, value FROM config")
    rows = await cursor.fetchall()
    return {row["key"]: row["value"] for row in rows}


async def set_config(key: str, value: str):
    """Set a config value in the database."""
    db = await get_db()
    await db.execute(
        "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    await db.commit()


async def set_config_bulk(data: dict[str, str]):
    """Set multiple config values at once."""
    db = await get_db()
    await db.executemany(
        "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        list(data.items()),
    )
    await db.commit()


async def sync_env_to_db():
    """Seed the DB config table from current environment / .env values."""
    import config as cfg

    env_keys = {
        "DISCORD_TOKEN": cfg.DISCORD_TOKEN or "",
        "AI_PROVIDER": cfg.AI_PROVIDER,
        "GEMINI_API_KEY": cfg.GEMINI_API_KEY or "",
        "GEMINI_MODEL": cfg.GEMINI_MODEL,
        "GROQ_API_KEY": cfg.GROQ_API_KEY or "",
        "GROQ_MODEL": cfg.GROQ_MODEL,
        "OPENROUTER_API_KEY": cfg.OPENROUTER_API_KEY or "",
        "OPENROUTER_MODEL": cfg.OPENROUTER_MODEL,
        "ANTHROPIC_API_KEY": cfg.ANTHROPIC_API_KEY or "",
        "ANTHROPIC_MODEL": cfg.ANTHROPIC_MODEL,
        "OPENAI_API_KEY": cfg.OPENAI_API_KEY or "",
        "OPENAI_MODEL": cfg.OPENAI_MODEL,
        "BOT_PREFIX": cfg.BOT_PREFIX,
        "MAX_TOKENS": str(cfg.MAX_TOKENS),
        "SYSTEM_PROMPT": cfg.SYSTEM_PROMPT,
    }
    db = await get_db()
    for key, value in env_keys.items():
        await db.execute(
            "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
            (key, value),
        )
    await db.commit()


async def sync_db_to_env():
    """Write DB config back to the .env file."""
    from dotenv import dotenv_values, set_key

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    all_config = await get_all_config()

    for key, value in all_config.items():
        set_key(env_path, key, value)


# --- Conversation helpers ---


async def add_message(channel_id: str, role: str, content: str, provider: str | None = None):
    """Add a message to conversation history."""
    db = await get_db()
    await db.execute(
        "INSERT INTO conversations (channel_id, role, content, provider) VALUES (?, ?, ?, ?)",
        (channel_id, role, content, provider),
    )
    await db.commit()


async def get_messages(channel_id: str, limit: int = 20) -> list[dict]:
    """Get recent messages for a channel."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT role, content, provider, created_at FROM conversations WHERE channel_id = ? ORDER BY id DESC LIMIT ?",
        (channel_id, limit),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in reversed(rows)]


async def clear_messages(channel_id: str):
    """Delete all messages for a channel."""
    db = await get_db()
    await db.execute("DELETE FROM conversations WHERE channel_id = ?", (channel_id,))
    await db.commit()


async def list_channels() -> list[dict]:
    """List all channels with message counts."""
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT channel_id, COUNT(*) as message_count, MAX(created_at) as last_active
        FROM conversations
        GROUP BY channel_id
        ORDER BY last_active DESC
        """
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# --- Wizard helpers ---


async def get_wizard_state() -> dict:
    """Get the wizard state."""
    db = await get_db()
    cursor = await db.execute("SELECT completed, current_step, data FROM wizard_state WHERE id = 1")
    row = await cursor.fetchone()
    return {
        "completed": bool(row["completed"]),
        "current_step": row["current_step"],
        "data": json.loads(row["data"]),
    }


async def set_wizard_state(completed: bool | None = None, current_step: int | None = None, data: dict | None = None):
    """Update wizard state fields."""
    db = await get_db()
    updates = []
    params = []
    if completed is not None:
        updates.append("completed = ?")
        params.append(int(completed))
    if current_step is not None:
        updates.append("current_step = ?")
        params.append(current_step)
    if data is not None:
        updates.append("data = ?")
        params.append(json.dumps(data))
    if updates:
        await db.execute(f"UPDATE wizard_state SET {', '.join(updates)} WHERE id = 1", params)
        await db.commit()


# --- Session helpers ---


async def create_session(token: str, user_id: str, expires_at: str):
    """Store a session token."""
    db = await get_db()
    await db.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at),
    )
    await db.commit()


async def validate_session(token: str) -> dict | None:
    """Validate a session token, return session data or None."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT user_id, expires_at FROM sessions WHERE token = ? AND expires_at > datetime('now')",
        (token,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def delete_session(token: str):
    """Delete a session."""
    db = await get_db()
    await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
    await db.commit()


async def close_db():
    """Close the database connection."""
    global _db
    if _db:
        await _db.close()
        _db = None


# --- Permission helpers ---

async def add_command_permission(guild_id: str, command_name: str, role_id: str):
    """Add a role restriction to a command."""
    db = await get_db()
    await db.execute(
        """INSERT OR IGNORE INTO command_permissions (command_name, guild_id, role_id)
           VALUES (?, ?, ?)""",
        (command_name, guild_id, role_id)
    )
    await db.commit()

async def remove_command_permission(guild_id: str, command_name: str, role_id: str) -> bool:
    """Remove a role restriction from a command. Returns True if deleted."""
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM command_permissions WHERE command_name = ? AND guild_id = ? AND role_id = ?",
        (command_name, guild_id, role_id)
    )
    await db.commit()
    return cursor.rowcount > 0

async def clear_command_permissions(guild_id: str, command_name: str):
    """Remove all role restrictions from a command."""
    db = await get_db()
    await db.execute(
        "DELETE FROM command_permissions WHERE command_name = ? AND guild_id = ?",
        (command_name, guild_id)
    )
    await db.commit()

async def get_command_permissions(guild_id: str, command_name: str) -> list[str]:
    """Get all role IDs required for a command. Empty list means no restrictions."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT role_id FROM command_permissions WHERE command_name = ? AND guild_id = ?",
        (command_name, guild_id)
    )
    rows = await cursor.fetchall()
    return [row["role_id"] for row in rows]

async def get_all_command_permissions(guild_id: str) -> dict[str, list[str]]:
    """Get all command permissions for a guild as {command_name: [role_ids]}."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT command_name, role_id FROM command_permissions WHERE guild_id = ?",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["command_name"], []).append(row["role_id"])
    return result


# --- FAQ helpers ---


async def add_faq(guild_id: str, question: str, answer: str, keywords: str, created_by: str) -> int:
    """Add a new FAQ entry. Returns the new FAQ's ID."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO faqs (guild_id, question, answer, match_keywords, created_by)
           VALUES (?, ?, ?, ?, ?)""",
        (guild_id, question, answer, keywords, created_by)
    )
    await db.commit()
    return cursor.lastrowid


async def get_faqs(guild_id: str) -> list[dict]:
    """Get all FAQs for a guild."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM faqs WHERE guild_id = ? ORDER BY id ASC",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_faq_by_id(guild_id: str, faq_id: int) -> dict | None:
    """Get a specific FAQ by ID."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM faqs WHERE guild_id = ? AND id = ?",
        (guild_id, faq_id)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def delete_faq(guild_id: str, faq_id: int) -> bool:
    """Delete a FAQ entry. Returns True if deleted, False if not found."""
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM faqs WHERE guild_id = ? AND id = ?",
        (guild_id, faq_id)
    )
    await db.commit()
    return cursor.rowcount > 0


async def increment_faq_usage(faq_id: int):
    """Increment the times_used counter for a FAQ."""
    db = await get_db()
    await db.execute(
        "UPDATE faqs SET times_used = times_used + 1 WHERE id = ?",
        (faq_id,)
    )
    await db.commit()


# --- Onboarding helpers ---


async def get_onboarding_config(guild_id: str, key: str) -> str | None:
    """Get a single onboarding config value for a guild."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT value FROM onboarding_config WHERE guild_id = ? AND key = ?",
        (guild_id, key)
    )
    row = await cursor.fetchone()
    return row["value"] if row else None


async def set_onboarding_config(guild_id: str, key: str, value: str):
    """Set a single onboarding config value for a guild."""
    db = await get_db()
    await db.execute(
        """INSERT INTO onboarding_config (guild_id, key, value)
           VALUES (?, ?, ?)
           ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value""",
        (guild_id, key, value)
    )
    await db.commit()


async def get_all_onboarding_config(guild_id: str) -> dict[str, str]:
    """Get all onboarding config values for a guild."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT key, value FROM onboarding_config WHERE guild_id = ?",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    return {row["key"]: row["value"] for row in rows}


# --- Permission helpers ---

async def add_command_permission(guild_id: str, command_name: str, role_id: str):
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO command_permissions (command_name, guild_id, role_id) VALUES (?, ?, ?)",
        (command_name, guild_id, role_id)
    )
    await db.commit()

async def remove_command_permission(guild_id: str, command_name: str, role_id: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM command_permissions WHERE command_name = ? AND guild_id = ? AND role_id = ?",
        (command_name, guild_id, role_id)
    )
    await db.commit()
    return cursor.rowcount > 0

async def clear_command_permissions(guild_id: str, command_name: str):
    db = await get_db()
    await db.execute(
        "DELETE FROM command_permissions WHERE command_name = ? AND guild_id = ?",
        (command_name, guild_id)
    )
    await db.commit()

async def get_command_permissions(guild_id: str, command_name: str) -> list[str]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT role_id FROM command_permissions WHERE command_name = ? AND guild_id = ?",
        (command_name, guild_id)
    )
    rows = await cursor.fetchall()
    return [row["role_id"] for row in rows]

async def get_all_command_permissions(guild_id: str) -> dict[str, list[str]]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT command_name, role_id FROM command_permissions WHERE guild_id = ?",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["command_name"], []).append(row["role_id"])
    return result


# --- Digest helpers ---

async def get_digest_config(guild_id: str, key: str) -> str | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT value FROM digest_config WHERE guild_id = ? AND key = ?",
        (guild_id, key)
    )
    row = await cursor.fetchone()
    return row["value"] if row else None

async def set_digest_config(guild_id: str, key: str, value: str):
    db = await get_db()
    await db.execute(
        """INSERT INTO digest_config (guild_id, key, value)
           VALUES (?, ?, ?)
           ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value""",
        (guild_id, key, value)
    )
    await db.commit()

async def get_recent_messages_for_digest(guild_id: str, hours: int = 24) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT role, content, provider, created_at, channel_id
        FROM conversations
        WHERE created_at >= datetime('now', ?)
        ORDER BY created_at ASC
        """,
        (f"-{hours} hours",)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# --- Moderation helpers ---

async def get_moderation_config(guild_id: str, key: str) -> str | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT value FROM moderation_config WHERE guild_id = ? AND key = ?",
        (guild_id, key)
    )
    row = await cursor.fetchone()
    return row["value"] if row else None

async def set_moderation_config(guild_id: str, key: str, value: str):
    db = await get_db()
    await db.execute(
        """INSERT INTO moderation_config (guild_id, key, value)
           VALUES (?, ?, ?)
           ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value""",
        (guild_id, key, value)
    )
    await db.commit()

async def add_moderation_log(guild_id: str, channel_id: str, message_id: str,
                              author_id: str, content: str, reason: str,
                              severity: str, categories: str):
    db = await get_db()
    await db.execute(
        """INSERT INTO moderation_logs
           (guild_id, channel_id, message_id, author_id, content, reason, severity, categories)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (guild_id, channel_id, message_id, author_id, content, reason, severity, categories)
    )
    await db.commit()

async def get_moderation_count(guild_id: str) -> int:
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) as count FROM moderation_logs WHERE guild_id = ?",
        (guild_id,)
    )
    row = await cursor.fetchone()
    return row["count"] if row else 0

async def get_moderation_stats(guild_id: str) -> dict[str, int]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT severity, COUNT(*) as count FROM moderation_logs WHERE guild_id = ? GROUP BY severity",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    return {row["severity"]: row["count"] for row in rows}


# --- Auto-translate helpers ---

async def get_auto_translate_channel(guild_id: str, channel_id: str) -> str | None:
    """Get the target language for a channel's auto-translation, or None if not set."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT target_language FROM auto_translate_channels WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id)
    )
    row = await cursor.fetchone()
    return row["target_language"] if row else None

async def set_auto_translate_channel(guild_id: str, channel_id: str, target_language: str):
    """Enable auto-translation for a channel."""
    db = await get_db()
    await db.execute(
        """INSERT INTO auto_translate_channels (guild_id, channel_id, target_language)
           VALUES (?, ?, ?)
           ON CONFLICT(guild_id, channel_id) DO UPDATE SET target_language = excluded.target_language""",
        (guild_id, channel_id, target_language)
    )
    await db.commit()

async def remove_auto_translate_channel(guild_id: str, channel_id: str):
    """Disable auto-translation for a channel."""
    db = await get_db()
    await db.execute(
        "DELETE FROM auto_translate_channels WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id)
    )
    await db.commit()

async def get_all_auto_translate_channels(guild_id: str) -> dict[str, str]:
    """Get all auto-translate channels for a guild as {channel_id: target_language}."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT channel_id, target_language FROM auto_translate_channels WHERE guild_id = ?",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    return {row["channel_id"]: row["target_language"] for row in rows}


# --- Channel prompt helpers ---

async def get_channel_prompt(guild_id: str, channel_id: str) -> str | None:
    """Get the custom system prompt for a channel, or None if not set."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT system_prompt FROM channel_prompts WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id)
    )
    row = await cursor.fetchone()
    return row["system_prompt"] if row else None

async def set_channel_prompt(guild_id: str, channel_id: str, prompt: str):
    """Set a custom system prompt for a channel."""
    db = await get_db()
    await db.execute(
        """INSERT INTO channel_prompts (guild_id, channel_id, system_prompt)
           VALUES (?, ?, ?)
           ON CONFLICT(channel_id) DO UPDATE SET system_prompt = excluded.system_prompt""",
        (guild_id, channel_id, prompt)
    )
    await db.commit()

async def delete_channel_prompt(guild_id: str, channel_id: str):
    """Remove the custom system prompt for a channel."""
    db = await get_db()
    await db.execute(
        "DELETE FROM channel_prompts WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id)
    )
    await db.commit()

async def get_all_channel_prompts(guild_id: str) -> dict[str, str]:
    """Get all custom channel prompts for a guild as {channel_id: prompt}."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT channel_id, system_prompt FROM channel_prompts WHERE guild_id = ?",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    return {row["channel_id"]: row["system_prompt"] for row in rows}


# --- Channel provider helpers ---

async def get_channel_provider(guild_id: str, channel_id: str) -> str | None:
    """Get the custom AI provider for a channel, or None if not set."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT provider_name FROM channel_providers WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id)
    )
    row = await cursor.fetchone()
    return row["provider_name"] if row else None

async def set_channel_provider(guild_id: str, channel_id: str, provider_name: str):
    """Set a custom AI provider for a channel."""
    db = await get_db()
    await db.execute(
        """INSERT INTO channel_providers (guild_id, channel_id, provider_name)
           VALUES (?, ?, ?)
           ON CONFLICT(guild_id, channel_id) DO UPDATE SET provider_name = excluded.provider_name""",
        (guild_id, channel_id, provider_name)
    )
    await db.commit()

async def delete_channel_provider(guild_id: str, channel_id: str):
    """Remove the custom AI provider for a channel."""
    db = await get_db()
    await db.execute(
        "DELETE FROM channel_providers WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id)
    )
    await db.commit()

async def get_all_channel_providers(guild_id: str) -> dict[str, str]:
    """Get all channel provider overrides for a guild as {channel_id: provider_name}."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT channel_id, provider_name FROM channel_providers WHERE guild_id = ?",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    return {row["channel_id"]: row["provider_name"] for row in rows}


# --- Analytics helpers ---

async def add_analytics_event(
    event_type: str,
    guild_id: str | None = None,
    channel_id: str | None = None,
    user_id: str | None = None,
    provider: str | None = None,
    tokens_used: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    estimated_cost: float | None = None,
    latency_ms: int | None = None,
):
    """Record an analytics event."""
    db = await get_db()
    await db.execute(
        """INSERT INTO analytics
           (event_type, guild_id, channel_id, user_id, provider,
            tokens_used, input_tokens, output_tokens, estimated_cost, latency_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_type, guild_id, channel_id, user_id, provider,
         tokens_used, input_tokens, output_tokens, estimated_cost or 0.0, latency_ms)
    )
    await db.commit()

async def get_analytics_summary(guild_id: str) -> dict:
    """Get analytics summary for a guild."""
    db = await get_db()

    # Total counts by event type
    cursor = await db.execute(
        "SELECT event_type, COUNT(*) as count FROM analytics WHERE guild_id = ? GROUP BY event_type",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    counts = {row["event_type"]: row["count"] for row in rows}

    # Average latency
    cursor = await db.execute(
        "SELECT AVG(latency_ms) as avg_latency FROM analytics WHERE guild_id = ? AND latency_ms IS NOT NULL",
        (guild_id,)
    )
    row = await cursor.fetchone()
    avg_latency = row["avg_latency"] or 0

    # Top provider
    cursor = await db.execute(
        """SELECT provider, COUNT(*) as count FROM analytics
           WHERE guild_id = ? AND provider IS NOT NULL AND provider != 'none'
           GROUP BY provider ORDER BY count DESC LIMIT 1""",
        (guild_id,)
    )
    row = await cursor.fetchone()
    top_provider = row["provider"] if row else None

    # Top channel
    cursor = await db.execute(
        """SELECT channel_id, COUNT(*) as count FROM analytics
           WHERE guild_id = ? AND channel_id IS NOT NULL
           GROUP BY channel_id ORDER BY count DESC LIMIT 1""",
        (guild_id,)
    )
    row = await cursor.fetchone()
    top_channel = row["channel_id"] if row else None

    return {
        "total_messages": counts.get("command", 0) + counts.get("mention", 0),
        "total_commands": counts.get("command", 0),
        "total_mentions": counts.get("mention", 0),
        "total_faqs": counts.get("faq", 0),
        "total_moderation": counts.get("moderation", 0),
        "avg_latency": avg_latency,
        "top_provider": top_provider,
        "top_channel": top_channel,
    }

async def get_analytics_history(guild_id: str, days: int = 30) -> list[dict]:
    """Get daily analytics history for a guild."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT
               date(created_at) as date,
               COUNT(*) as total_events,
               SUM(CASE WHEN event_type = 'command' THEN 1 ELSE 0 END) as commands,
               SUM(CASE WHEN event_type = 'mention' THEN 1 ELSE 0 END) as mentions,
               AVG(latency_ms) as avg_latency
           FROM analytics
           WHERE guild_id = ? AND created_at >= datetime('now', ?)
           GROUP BY date(created_at)
           ORDER BY date ASC""",
        (guild_id, f"-{days} days")
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

async def get_analytics_provider_distribution(guild_id: str) -> list[dict]:
    """Get provider usage distribution for a guild."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT provider, COUNT(*) as count
           FROM analytics
           WHERE guild_id = ? AND provider IS NOT NULL AND provider != 'none'
           GROUP BY provider
           ORDER BY count DESC""",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

async def get_analytics_top_channels(guild_id: str, limit: int = 10) -> list[dict]:
    """Get top channels by activity for a guild."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT channel_id, COUNT(*) as count
           FROM analytics
           WHERE guild_id = ? AND channel_id IS NOT NULL
           GROUP BY channel_id
           ORDER BY count DESC
           LIMIT ?""",
        (guild_id, limit)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

async def get_global_analytics_summary() -> dict:
    """Get global analytics summary across all guilds (for dashboard)."""
    db = await get_db()

    cursor = await db.execute("SELECT COUNT(*) as total FROM analytics")
    row = await cursor.fetchone()
    total = row["total"] if row else 0

    cursor = await db.execute(
        "SELECT event_type, COUNT(*) as count FROM analytics GROUP BY event_type"
    )
    rows = await cursor.fetchall()
    counts = {row["event_type"]: row["count"] for row in rows}

    cursor = await db.execute(
        "SELECT AVG(latency_ms) as avg FROM analytics WHERE latency_ms IS NOT NULL"
    )
    row = await cursor.fetchone()
    avg_latency = row["avg"] or 0

    cursor = await db.execute(
        """SELECT provider, COUNT(*) as count FROM analytics
           WHERE provider IS NOT NULL AND provider != 'none'
           GROUP BY provider ORDER BY count DESC"""
    )
    rows = await cursor.fetchall()
    provider_dist = [dict(row) for row in rows]

    cursor = await db.execute(
        """SELECT date(created_at) as date, COUNT(*) as count
           FROM analytics
           WHERE created_at >= datetime('now', '-30 days')
           GROUP BY date(created_at)
           ORDER BY date ASC"""
    )
    rows = await cursor.fetchall()
    daily = [dict(row) for row in rows]

    return {
        "total_events": total,
        "counts": counts,
        "avg_latency": avg_latency,
        "provider_distribution": provider_dist,
        "daily_history": daily,
    }


# --- Plugin helpers ---

async def get_enabled_plugins(guild_id: str) -> list[str]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT plugin_name FROM enabled_plugins WHERE guild_id = ?",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    return [row["plugin_name"] for row in rows]

async def enable_plugin(guild_id: str, plugin_name: str):
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO enabled_plugins (guild_id, plugin_name) VALUES (?, ?)",
        (guild_id, plugin_name)
    )
    await db.commit()

async def disable_plugin(guild_id: str, plugin_name: str):
    db = await get_db()
    await db.execute(
        "DELETE FROM enabled_plugins WHERE guild_id = ? AND plugin_name = ?",
        (guild_id, plugin_name)
    )
    await db.commit()


# --- Trivia helpers ---

async def update_trivia_score(guild_id: str, user_id: str, correct: bool):
    db = await get_db()
    if correct:
        await db.execute(
            """INSERT INTO trivia_scores (guild_id, user_id, correct, wrong)
               VALUES (?, ?, 1, 0)
               ON CONFLICT(guild_id, user_id) DO UPDATE SET correct = correct + 1""",
            (guild_id, user_id)
        )
    else:
        await db.execute(
            """INSERT INTO trivia_scores (guild_id, user_id, correct, wrong)
               VALUES (?, ?, 0, 1)
               ON CONFLICT(guild_id, user_id) DO UPDATE SET wrong = wrong + 1""",
            (guild_id, user_id)
        )
    await db.commit()

async def get_trivia_score(guild_id: str, user_id: str) -> dict:
    db = await get_db()
    cursor = await db.execute(
        "SELECT correct, wrong FROM trivia_scores WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    row = await cursor.fetchone()
    return {"correct": row["correct"], "wrong": row["wrong"]} if row else {"correct": 0, "wrong": 0}

async def get_trivia_leaderboard(guild_id: str, limit: int = 10) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT user_id, correct, wrong FROM trivia_scores
           WHERE guild_id = ?
           ORDER BY correct DESC LIMIT ?""",
        (guild_id, limit)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# --- Cost tracking helpers ---

async def get_cost_summary(days: int = 30) -> list[dict]:
    """Get daily cost breakdown per provider for the last N days."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT
               date(created_at) as date,
               provider,
               SUM(estimated_cost) as daily_cost,
               SUM(input_tokens) as total_input,
               SUM(output_tokens) as total_output,
               COUNT(*) as requests
           FROM analytics
           WHERE created_at >= datetime('now', ?)
             AND provider IS NOT NULL AND provider != 'none'
           GROUP BY date(created_at), provider
           ORDER BY date ASC""",
        (f"-{days} days",)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_total_cost_by_provider(days: int = 30) -> list[dict]:
    """Get total cost per provider for the last N days."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT
               provider,
               SUM(estimated_cost) as total_cost,
               SUM(input_tokens) as total_input_tokens,
               SUM(output_tokens) as total_output_tokens,
               COUNT(*) as total_requests
           FROM analytics
           WHERE created_at >= datetime('now', ?)
             AND provider IS NOT NULL AND provider != 'none'
           GROUP BY provider
           ORDER BY total_cost DESC""",
        (f"-{days} days",)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_monthly_projected_cost() -> dict:
    """Estimate monthly cost based on last 7 days of usage."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT
               SUM(estimated_cost) as week_cost,
               COUNT(*) as week_requests
           FROM analytics
           WHERE created_at >= datetime('now', '-7 days')"""
    )
    row = await cursor.fetchone()
    week_cost = row["week_cost"] or 0.0
    week_requests = row["week_requests"] or 0

    daily_avg_cost = week_cost / 7
    daily_avg_requests = week_requests / 7
    projected_monthly = daily_avg_cost * 30

    return {
        "week_cost": round(week_cost, 4),
        "daily_avg_cost": round(daily_avg_cost, 4),
        "daily_avg_requests": round(daily_avg_requests, 1),
        "projected_monthly": round(projected_monthly, 4),
    }


async def get_cost_alert_status(threshold: float) -> dict:
    """Check if current month cost is approaching or exceeding the threshold."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT SUM(estimated_cost) as month_cost
           FROM analytics
           WHERE created_at >= datetime('now', 'start of month')"""
    )
    row = await cursor.fetchone()
    month_cost = row["month_cost"] or 0.0
    percentage = (month_cost / threshold * 100) if threshold > 0 else 0

    return {
        "month_cost": round(month_cost, 4),
        "threshold": threshold,
        "percentage": round(percentage, 1),
        "exceeded": month_cost >= threshold,
        "warning": percentage >= 80,
    }
    
    # Add these to your db.py

async def init_member_analytics_tables():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS member_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            event_type TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS member_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            hour INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_member_events_guild ON member_events(guild_id);
        CREATE INDEX IF NOT EXISTS idx_member_events_created ON member_events(created_at);
        CREATE INDEX IF NOT EXISTS idx_member_messages_guild ON member_messages(guild_id);
        CREATE INDEX IF NOT EXISTS idx_member_messages_user ON member_messages(user_id);
    """)
    await db.commit()


async def log_member_event(guild_id: str, user_id: str, username: str, event_type: str) -> None:
    db = await get_db()
    await db.execute(
        "INSERT INTO member_events (guild_id, user_id, username, event_type) VALUES (?,?,?,?)",
        (guild_id, user_id, username, event_type)
    )
    await db.commit()


async def log_member_message(guild_id: str, user_id: str, username: str, hour: int) -> None:
    db = await get_db()
    await db.execute(
        "INSERT INTO member_messages (guild_id, user_id, username, hour) VALUES (?,?,?,?)",
        (guild_id, user_id, username, hour)
    )
    await db.commit()


async def get_member_overview(guild_id: str, days: int = 30) -> dict:
    db = await get_db()
    cursor = await db.execute("""
        SELECT
            SUM(CASE WHEN event_type='join' THEN 1 ELSE 0 END) as joins_30d,
            SUM(CASE WHEN event_type='leave' THEN 1 ELSE 0 END) as leaves_30d
        FROM member_events
        WHERE guild_id = ?
        AND created_at >= datetime('now', ?)
    """, (guild_id, f"-{days} days"))
    row = dict(await cursor.fetchone())
    cursor = await db.execute("""
        SELECT COUNT(DISTINCT user_id) as active_members,
               COUNT(*) as total_messages
        FROM member_messages
        WHERE guild_id = ?
        AND created_at >= datetime('now', ?)
    """, (guild_id, f"-{days} days"))
    msg_row = dict(await cursor.fetchone())
    return {**row, **msg_row}


async def get_member_join_leave_history(guild_id: str, days: int = 30) -> list[dict]:
    db = await get_db()
    cursor = await db.execute("""
        SELECT
            date(created_at) as date,
            SUM(CASE WHEN event_type='join' THEN 1 ELSE 0 END) as joins,
            SUM(CASE WHEN event_type='leave' THEN 1 ELSE 0 END) as leaves
        FROM member_events
        WHERE guild_id = ?
        AND created_at >= datetime('now', ?)
        GROUP BY date(created_at)
        ORDER BY date ASC
    """, (guild_id, f"-{days} days"))
    return [dict(r) for r in await cursor.fetchall()]


async def get_top_active_members(guild_id: str, days: int = 30, limit: int = 10) -> list[dict]:
    db = await get_db()
    cursor = await db.execute("""
        SELECT user_id, username, COUNT(*) as message_count
        FROM member_messages
        WHERE guild_id = ?
        AND created_at >= datetime('now', ?)
        GROUP BY user_id
        ORDER BY message_count DESC
        LIMIT ?
    """, (guild_id, f"-{days} days", limit))
    return [dict(r) for r in await cursor.fetchall()]


async def get_peak_hours(guild_id: str, days: int = 30) -> list[dict]:
    db = await get_db()
    cursor = await db.execute("""
        SELECT hour, COUNT(*) as message_count
        FROM member_messages
        WHERE guild_id = ?
        AND created_at >= datetime('now', ?)
        GROUP BY hour
        ORDER BY hour ASC
    """, (guild_id, f"-{days} days"))
    rows = {r["hour"]: r["message_count"] for r in await cursor.fetchall()}
    return [{"hour": h, "messages": rows.get(h, 0)} for h in range(24)]