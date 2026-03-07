from __future__ import annotations

import os
import json
import aiosqlite

DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "sparksage.db")

# Use PostgreSQL if DATABASE_URL is set, otherwise SQLite
USE_POSTGRES = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")

_db: aiosqlite.Connection | None = None
# Per-loop pool cache: {loop_id: pool}
_pg_pools: dict = {}


# ── Connection helpers ────────────────────────────────────────────────────────

async def get_db() -> aiosqlite.Connection:
    """Return SQLite connection (local dev)."""
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DATABASE_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def get_pg():
    """Return asyncpg pool for the CURRENT event loop.
    Each event loop (uvicorn, discord bot) gets its own pool.
    """
    import asyncio
    import asyncpg
    loop = asyncio.get_event_loop()
    loop_id = id(loop)
    if loop_id not in _pg_pools or _pg_pools[loop_id].is_closing():
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        _pg_pools[loop_id] = await asyncpg.create_pool(
            url,
            min_size=1,
            max_size=10,
            command_timeout=60,
            statement_cache_size=0,
        )
    return _pg_pools[loop_id]


class Row(dict):
    """Dict subclass that supports row['key'] and row.key access."""
    def __getattr__(self, key):
        return self[key]


async def execute(query: str, params: tuple = (), fetch: str = "none"):
    """
    Unified query executor for both SQLite and PostgreSQL.
    fetch: 'none' | 'one' | 'all'
    """
    if USE_POSTGRES:
        # Convert SQLite ? placeholders to $1, $2, ... for asyncpg
        pg_query = query
        idx = 0
        while "?" in pg_query:
            idx += 1
            pg_query = pg_query.replace("?", f"${idx}", 1)

        # Convert SQLite-specific syntax to PostgreSQL
        pg_query = pg_query.replace("INSERT OR IGNORE INTO", "INSERT INTO")
        pg_query = pg_query.replace("INSERT OR REPLACE INTO", "INSERT INTO")

        # Add ON CONFLICT DO NOTHING for INSERT OR IGNORE
        if "INSERT OR IGNORE" in query and "ON CONFLICT" not in pg_query:
            pg_query += " ON CONFLICT DO NOTHING"

        # Fix datetime functions — order matters (longest patterns first)
        pg_query = pg_query.replace("datetime('now', 'start of month')", "date_trunc('month', NOW())")
        pg_query = pg_query.replace("datetime('now', '-30 days')", "(NOW() - INTERVAL '30 days')")
        pg_query = pg_query.replace("datetime('now', '-7 days')", "(NOW() - INTERVAL '7 days')")
        pg_query = pg_query.replace("datetime('now')", "NOW()")
        pg_query = pg_query.replace("date(created_at)", "DATE(created_at)")
        # Convert dynamic datetime('now', $N) -> (NOW() + $N::interval)
        # This handles queries like: WHERE created_at >= datetime('now', ?) with param '-30 days'
        import re as _re
        pg_query = _re.sub(r"datetime\('now',\s*(\$\d+)\)", r"(NOW() + ::interval)", pg_query)

        pool = await get_pg()
        try:
            async with pool.acquire() as conn:
                if fetch == "one":
                    row = await conn.fetchrow(pg_query, *params)
                    return Row(dict(row)) if row else None
                elif fetch == "all":
                    rows = await conn.fetch(pg_query, *params)
                    return [Row(dict(r)) for r in rows]
                else:
                    await conn.execute(pg_query, *params)
                    return None
        except Exception as e:
            print(f"[DB Error] {e}\nQuery: {pg_query}\nParams: {params}")
            raise
    else:
        db = await get_db()
        cursor = await db.execute(query, params)
        if fetch == "one":
            row = await cursor.fetchone()
            return dict(row) if row else None
        elif fetch == "all":
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        else:
            await db.commit()
            return cursor


async def executemany(query: str, params_list: list):
    if USE_POSTGRES:
        pool = await get_pg()
        idx_query = query
        idx = 0
        while "?" in idx_query:
            idx += 1
            idx_query = idx_query.replace("?", f"${idx}", 1)
        async with pool.acquire() as conn:
            await conn.executemany(idx_query, params_list)
    else:
        db = await get_db()
        await db.executemany(query, params_list)
        await db.commit()


async def executescript(sql: str):
    """Execute multiple SQL statements (init only)."""
    if USE_POSTGRES:
        pool = await get_pg()
        # Split by semicolon and run each statement
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        async with pool.acquire() as conn:
            for stmt in statements:
                # Convert SQLite-specific syntax
                stmt = stmt.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
                stmt = stmt.replace("datetime('now')", "NOW()")
                stmt = stmt.replace("INSERT OR IGNORE INTO", "INSERT INTO")
                try:
                    await conn.execute(stmt)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        print(f"[DB Init Warning] {e}: {stmt[:80]}")
    else:
        db = await get_db()
        await db.executescript(sql)
        await db.commit()


# ── Schema init ───────────────────────────────────────────────────────────────

async def init_db():
    """Create tables if they don't exist."""
    if USE_POSTGRES:
        import asyncpg
        # Use a fresh direct connection for init — never use the shared pool here
        # because init_db may be called from a different event loop (uvicorn lifespan)
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        conn = await asyncpg.connect(url)
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS conversations (id SERIAL PRIMARY KEY, channel_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, provider TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
                CREATE INDEX IF NOT EXISTS idx_conv_channel ON conversations(channel_id);
                CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), expires_at TIMESTAMPTZ NOT NULL);
                CREATE TABLE IF NOT EXISTS wizard_state (id INTEGER PRIMARY KEY CHECK (id = 1), completed INTEGER NOT NULL DEFAULT 0, current_step INTEGER NOT NULL DEFAULT 0, data TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS faqs (id SERIAL PRIMARY KEY, guild_id TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL, match_keywords TEXT NOT NULL, times_used INTEGER DEFAULT 0, created_by TEXT, created_at TIMESTAMPTZ DEFAULT NOW());
                CREATE TABLE IF NOT EXISTS onboarding_config (guild_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY (guild_id, key));
                CREATE TABLE IF NOT EXISTS command_permissions (command_name TEXT NOT NULL, guild_id TEXT NOT NULL, role_id TEXT NOT NULL, PRIMARY KEY (command_name, guild_id, role_id));
                CREATE TABLE IF NOT EXISTS digest_config (guild_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY (guild_id, key));
                CREATE TABLE IF NOT EXISTS moderation_config (guild_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY (guild_id, key));
                CREATE TABLE IF NOT EXISTS moderation_logs (id SERIAL PRIMARY KEY, guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, message_id TEXT NOT NULL, author_id TEXT NOT NULL, content TEXT NOT NULL, reason TEXT, severity TEXT, categories TEXT, created_at TIMESTAMPTZ DEFAULT NOW());
                CREATE TABLE IF NOT EXISTS auto_translate_channels (guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, target_language TEXT NOT NULL, PRIMARY KEY (guild_id, channel_id));
                CREATE TABLE IF NOT EXISTS channel_prompts (guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, system_prompt TEXT NOT NULL, PRIMARY KEY (guild_id, channel_id));
                CREATE TABLE IF NOT EXISTS channel_providers (guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, provider_name TEXT NOT NULL, PRIMARY KEY (guild_id, channel_id));
                CREATE TABLE IF NOT EXISTS analytics (id SERIAL PRIMARY KEY, event_type TEXT NOT NULL, guild_id TEXT, channel_id TEXT, user_id TEXT, provider TEXT, tokens_used INTEGER, input_tokens INTEGER, output_tokens INTEGER, estimated_cost REAL DEFAULT 0.0, latency_ms INTEGER, created_at TIMESTAMPTZ DEFAULT NOW());
                CREATE INDEX IF NOT EXISTS idx_analytics_guild ON analytics(guild_id);
                CREATE INDEX IF NOT EXISTS idx_analytics_created ON analytics(created_at);
                CREATE TABLE IF NOT EXISTS enabled_plugins (guild_id TEXT NOT NULL, plugin_name TEXT NOT NULL, PRIMARY KEY (guild_id, plugin_name));
                CREATE TABLE IF NOT EXISTS trivia_scores (guild_id TEXT NOT NULL, user_id TEXT NOT NULL, correct INTEGER DEFAULT 0, wrong INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id));
                CREATE TABLE IF NOT EXISTS member_events (id SERIAL PRIMARY KEY, guild_id TEXT NOT NULL, user_id TEXT NOT NULL, username TEXT NOT NULL, event_type TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW());
                CREATE TABLE IF NOT EXISTS member_messages (id SERIAL PRIMARY KEY, guild_id TEXT NOT NULL, user_id TEXT NOT NULL, username TEXT NOT NULL, hour INTEGER NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW());
                CREATE INDEX IF NOT EXISTS idx_member_events_guild ON member_events(guild_id);
                CREATE INDEX IF NOT EXISTS idx_member_messages_guild ON member_messages(guild_id);
                INSERT INTO wizard_state (id) VALUES (1) ON CONFLICT DO NOTHING;
            """)
        finally:
            await conn.close()
        # Pool is per-loop so no reset needed — each loop gets its own pool
    else:
        db = await get_db()
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, provider TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')));
            CREATE INDEX IF NOT EXISTS idx_conv_channel ON conversations(channel_id);
            CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')), expires_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS wizard_state (id INTEGER PRIMARY KEY CHECK (id = 1), completed INTEGER NOT NULL DEFAULT 0, current_step INTEGER NOT NULL DEFAULT 0, data TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS faqs (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL, match_keywords TEXT NOT NULL, times_used INTEGER DEFAULT 0, created_by TEXT, created_at TEXT DEFAULT (datetime('now')));
            CREATE TABLE IF NOT EXISTS onboarding_config (guild_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY (guild_id, key));
            CREATE TABLE IF NOT EXISTS command_permissions (command_name TEXT NOT NULL, guild_id TEXT NOT NULL, role_id TEXT NOT NULL, PRIMARY KEY (command_name, guild_id, role_id));
            CREATE TABLE IF NOT EXISTS digest_config (guild_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY (guild_id, key));
            CREATE TABLE IF NOT EXISTS moderation_config (guild_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY (guild_id, key));
            CREATE TABLE IF NOT EXISTS moderation_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, message_id TEXT NOT NULL, author_id TEXT NOT NULL, content TEXT NOT NULL, reason TEXT, severity TEXT, categories TEXT, created_at TEXT DEFAULT (datetime('now')));
            CREATE TABLE IF NOT EXISTS auto_translate_channels (guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, target_language TEXT NOT NULL, PRIMARY KEY (guild_id, channel_id));
            CREATE TABLE IF NOT EXISTS channel_prompts (channel_id TEXT NOT NULL, guild_id TEXT NOT NULL, system_prompt TEXT NOT NULL, PRIMARY KEY (guild_id, channel_id));
            CREATE TABLE IF NOT EXISTS channel_providers (guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, provider_name TEXT NOT NULL, PRIMARY KEY (guild_id, channel_id));
            CREATE TABLE IF NOT EXISTS analytics (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, guild_id TEXT, channel_id TEXT, user_id TEXT, provider TEXT, tokens_used INTEGER, input_tokens INTEGER, output_tokens INTEGER, estimated_cost REAL DEFAULT 0.0, latency_ms INTEGER, created_at TEXT DEFAULT (datetime('now')));
            CREATE INDEX IF NOT EXISTS idx_analytics_guild ON analytics(guild_id);
            CREATE INDEX IF NOT EXISTS idx_analytics_created ON analytics(created_at);
            CREATE TABLE IF NOT EXISTS enabled_plugins (guild_id TEXT NOT NULL, plugin_name TEXT NOT NULL, PRIMARY KEY (guild_id, plugin_name));
            CREATE TABLE IF NOT EXISTS trivia_scores (guild_id TEXT NOT NULL, user_id TEXT NOT NULL, correct INTEGER DEFAULT 0, wrong INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id));
            CREATE TABLE IF NOT EXISTS member_events (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT NOT NULL, user_id TEXT NOT NULL, username TEXT NOT NULL, event_type TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now')));
            CREATE TABLE IF NOT EXISTS member_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT NOT NULL, user_id TEXT NOT NULL, username TEXT NOT NULL, hour INTEGER NOT NULL, created_at TEXT DEFAULT (datetime('now')));
            CREATE INDEX IF NOT EXISTS idx_member_events_guild ON member_events(guild_id);
            CREATE INDEX IF NOT EXISTS idx_member_messages_guild ON member_messages(guild_id);
            INSERT OR IGNORE INTO wizard_state (id) VALUES (1);
        """)
        await db.commit()

async def init_member_analytics_tables():
    pass
async def init_member_analytics_tables():
    """Already included in init_db, this is kept for backwards compatibility."""
    pass


# ── Config helpers ────────────────────────────────────────────────────────────

async def get_config(key: str, default: str | None = None) -> str | None:
    row = await execute("SELECT value FROM config WHERE key = ?", (key,), fetch="one")
    return row["value"] if row else default

async def get_all_config() -> dict[str, str]:
    if USE_POSTGRES:
        import asyncpg
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        conn = await asyncpg.connect(url)
        try:
            rows = await conn.fetch("SELECT key, value FROM config")
            return {r["key"]: r["value"] for r in rows}
        finally:
            await conn.close()
    rows = await execute("SELECT key, value FROM config", fetch="all")
    return {r["key"]: r["value"] for r in rows}

async def set_config(key: str, value: str):
    await execute(
        "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value)
    )

async def set_config_bulk(data: dict[str, str]):
    await executemany(
        "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        list(data.items())
    )

async def sync_env_to_db():
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
    if USE_POSTGRES:
        import asyncpg
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        conn = await asyncpg.connect(url)
        try:
            for key, value in env_keys.items():
                await conn.execute(
                    "INSERT INTO config (key, value) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    key, value
                )
        finally:
            await conn.close()
    else:
        db = await get_db()
        for key, value in env_keys.items():
            await db.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

async def sync_db_to_env():
    from dotenv import set_key
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    all_config = await get_all_config()
    for key, value in all_config.items():
        set_key(env_path, key, value)


# ── Conversation helpers ──────────────────────────────────────────────────────

async def add_message(channel_id: str, role: str, content: str, provider: str | None = None):
    await execute(
        "INSERT INTO conversations (channel_id, role, content, provider) VALUES (?, ?, ?, ?)",
        (channel_id, role, content, provider)
    )

async def get_messages(channel_id: str, limit: int = 20) -> list[dict]:
    if USE_POSTGRES:
        pool = await get_pg()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT role, content, provider, created_at FROM conversations WHERE channel_id = $1 ORDER BY id DESC LIMIT $2",
                channel_id, limit
            )
            return [dict(r) for r in reversed(rows)]
    else:
        db = await get_db()
        cursor = await db.execute(
            "SELECT role, content, provider, created_at FROM conversations WHERE channel_id = ? ORDER BY id DESC LIMIT ?",
            (channel_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in reversed(rows)]

async def clear_messages(channel_id: str):
    await execute("DELETE FROM conversations WHERE channel_id = ?", (channel_id,))

async def list_channels() -> list[dict]:
    return await execute(
        "SELECT channel_id, COUNT(*) as message_count, MAX(created_at) as last_active FROM conversations GROUP BY channel_id ORDER BY last_active DESC",
        fetch="all"
    ) or []


# ── Wizard helpers ────────────────────────────────────────────────────────────

async def get_wizard_state() -> dict:
    row = await execute("SELECT completed, current_step, data FROM wizard_state WHERE id = 1", fetch="one")
    return {
        "completed": bool(row["completed"]),
        "current_step": row["current_step"],
        "data": json.loads(row["data"]),
    }

async def set_wizard_state(completed=None, current_step=None, data=None):
    updates, params = [], []
    if completed is not None:
        updates.append("completed = ?"); params.append(int(completed))
    if current_step is not None:
        updates.append("current_step = ?"); params.append(current_step)
    if data is not None:
        updates.append("data = ?"); params.append(json.dumps(data))
    if updates:
        await execute(f"UPDATE wizard_state SET {', '.join(updates)} WHERE id = 1", tuple(params))


# ── Session helpers ───────────────────────────────────────────────────────────

async def create_session(token: str, user_id: str, expires_at: str):
    await execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at)
    )

async def validate_session(token: str) -> dict | None:
    if USE_POSTGRES:
        pool = await get_pg()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT user_id, expires_at FROM sessions WHERE token = $1 AND expires_at > NOW()",
                token
            )
            return dict(row) if row else None
    else:
        db = await get_db()
        cursor = await db.execute(
            "SELECT user_id, expires_at FROM sessions WHERE token = ? AND expires_at > datetime('now')",
            (token,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

async def delete_session(token: str):
    await execute("DELETE FROM sessions WHERE token = ?", (token,))

async def close_db():
    import asyncio
    global _db, _pg_pools
    if _db:
        await _db.close()
        _db = None
    loop_id = id(asyncio.get_event_loop())
    if loop_id in _pg_pools:
        try:
            await _pg_pools[loop_id].close()
        except Exception:
            pass
        del _pg_pools[loop_id]


# ── Permission helpers ────────────────────────────────────────────────────────

async def add_command_permission(guild_id: str, command_name: str, role_id: str):
    await execute(
        "INSERT OR IGNORE INTO command_permissions (command_name, guild_id, role_id) VALUES (?, ?, ?)",
        (command_name, guild_id, role_id)
    )

async def remove_command_permission(guild_id: str, command_name: str, role_id: str) -> bool:
    result = await execute(
        "DELETE FROM command_permissions WHERE command_name = ? AND guild_id = ? AND role_id = ?",
        (command_name, guild_id, role_id)
    )
    if USE_POSTGRES:
        return True
    return result.rowcount > 0 if result else False

async def clear_command_permissions(guild_id: str, command_name: str):
    await execute(
        "DELETE FROM command_permissions WHERE command_name = ? AND guild_id = ?",
        (command_name, guild_id)
    )

async def get_command_permissions(guild_id: str, command_name: str) -> list[str]:
    rows = await execute(
        "SELECT role_id FROM command_permissions WHERE command_name = ? AND guild_id = ?",
        (command_name, guild_id), fetch="all"
    )
    return [r["role_id"] for r in (rows or [])]

async def get_all_command_permissions(guild_id: str) -> dict[str, list[str]]:
    rows = await execute(
        "SELECT command_name, role_id FROM command_permissions WHERE guild_id = ?",
        (guild_id,), fetch="all"
    )
    result: dict[str, list[str]] = {}
    for row in (rows or []):
        result.setdefault(row["command_name"], []).append(row["role_id"])
    return result


# ── FAQ helpers ───────────────────────────────────────────────────────────────

async def add_faq(guild_id: str, question: str, answer: str, keywords: str, created_by: str) -> int:
    if USE_POSTGRES:
        pool = await get_pg()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO faqs (guild_id, question, answer, match_keywords, created_by) VALUES ($1,$2,$3,$4,$5) RETURNING id",
                guild_id, question, answer, keywords, created_by
            )
            return row["id"]
    else:
        db = await get_db()
        cursor = await db.execute(
            "INSERT INTO faqs (guild_id, question, answer, match_keywords, created_by) VALUES (?, ?, ?, ?, ?)",
            (guild_id, question, answer, keywords, created_by)
        )
        await db.commit()
        return cursor.lastrowid

async def get_faqs(guild_id: str) -> list[dict]:
    return await execute("SELECT * FROM faqs WHERE guild_id = ? ORDER BY id ASC", (guild_id,), fetch="all") or []

async def get_faq_by_id(guild_id: str, faq_id: int) -> dict | None:
    return await execute("SELECT * FROM faqs WHERE guild_id = ? AND id = ?", (guild_id, faq_id), fetch="one")

async def delete_faq(guild_id: str, faq_id: int) -> bool:
    result = await execute("DELETE FROM faqs WHERE guild_id = ? AND id = ?", (guild_id, faq_id))
    if USE_POSTGRES:
        return True
    return result.rowcount > 0 if result else False

async def increment_faq_usage(faq_id: int):
    await execute("UPDATE faqs SET times_used = times_used + 1 WHERE id = ?", (faq_id,))


# ── Onboarding helpers ────────────────────────────────────────────────────────

async def get_onboarding_config(guild_id: str, key: str) -> str | None:
    row = await execute(
        "SELECT value FROM onboarding_config WHERE guild_id = ? AND key = ?",
        (guild_id, key), fetch="one"
    )
    return row["value"] if row else None

async def set_onboarding_config(guild_id: str, key: str, value: str):
    await execute(
        "INSERT INTO onboarding_config (guild_id, key, value) VALUES (?, ?, ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value",
        (guild_id, key, value)
    )

async def get_all_onboarding_config(guild_id: str) -> dict[str, str]:
    rows = await execute("SELECT key, value FROM onboarding_config WHERE guild_id = ?", (guild_id,), fetch="all")
    return {r["key"]: r["value"] for r in (rows or [])}


# ── Digest helpers ────────────────────────────────────────────────────────────

async def get_digest_config(guild_id: str, key: str) -> str | None:
    row = await execute(
        "SELECT value FROM digest_config WHERE guild_id = ? AND key = ?",
        (guild_id, key), fetch="one"
    )
    return row["value"] if row else None

async def set_digest_config(guild_id: str, key: str, value: str):
    await execute(
        "INSERT INTO digest_config (guild_id, key, value) VALUES (?, ?, ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value",
        (guild_id, key, value)
    )

async def get_recent_messages_for_digest(guild_id: str, hours: int = 24) -> list[dict]:
    if USE_POSTGRES:
        pool = await get_pg()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT role, content, provider, created_at, channel_id FROM conversations WHERE created_at >= NOW() - INTERVAL '1 hour' * $1 ORDER BY created_at ASC",
                hours
            )
            return [dict(r) for r in rows]
    else:
        db = await get_db()
        cursor = await db.execute(
            "SELECT role, content, provider, created_at, channel_id FROM conversations WHERE created_at >= datetime('now', ?) ORDER BY created_at ASC",
            (f"-{hours} hours",)
        )
        return [dict(r) for r in await cursor.fetchall()]


# ── Moderation helpers ────────────────────────────────────────────────────────

async def get_moderation_config(guild_id: str, key: str) -> str | None:
    row = await execute(
        "SELECT value FROM moderation_config WHERE guild_id = ? AND key = ?",
        (guild_id, key), fetch="one"
    )
    return row["value"] if row else None

async def set_moderation_config(guild_id: str, key: str, value: str):
    await execute(
        "INSERT INTO moderation_config (guild_id, key, value) VALUES (?, ?, ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value",
        (guild_id, key, value)
    )

async def add_moderation_log(guild_id, channel_id, message_id, author_id, content, reason, severity, categories):
    await execute(
        "INSERT INTO moderation_logs (guild_id, channel_id, message_id, author_id, content, reason, severity, categories) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (guild_id, channel_id, message_id, author_id, content, reason, severity, categories)
    )

async def get_moderation_count(guild_id: str) -> int:
    row = await execute("SELECT COUNT(*) as count FROM moderation_logs WHERE guild_id = ?", (guild_id,), fetch="one")
    return row["count"] if row else 0

async def get_moderation_stats(guild_id: str) -> dict[str, int]:
    rows = await execute(
        "SELECT severity, COUNT(*) as count FROM moderation_logs WHERE guild_id = ? GROUP BY severity",
        (guild_id,), fetch="all"
    )
    return {r["severity"]: r["count"] for r in (rows or [])}


# ── Auto-translate helpers ────────────────────────────────────────────────────

async def get_auto_translate_channel(guild_id: str, channel_id: str) -> str | None:
    row = await execute(
        "SELECT target_language FROM auto_translate_channels WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id), fetch="one"
    )
    return row["target_language"] if row else None

async def set_auto_translate_channel(guild_id: str, channel_id: str, target_language: str):
    await execute(
        "INSERT INTO auto_translate_channels (guild_id, channel_id, target_language) VALUES (?, ?, ?) ON CONFLICT(guild_id, channel_id) DO UPDATE SET target_language = excluded.target_language",
        (guild_id, channel_id, target_language)
    )

async def remove_auto_translate_channel(guild_id: str, channel_id: str):
    await execute("DELETE FROM auto_translate_channels WHERE guild_id = ? AND channel_id = ?", (guild_id, channel_id))

async def get_all_auto_translate_channels(guild_id: str) -> dict[str, str]:
    rows = await execute("SELECT channel_id, target_language FROM auto_translate_channels WHERE guild_id = ?", (guild_id,), fetch="all")
    return {r["channel_id"]: r["target_language"] for r in (rows or [])}


# ── Channel prompt helpers ────────────────────────────────────────────────────

async def get_channel_prompt(guild_id: str, channel_id: str) -> str | None:
    row = await execute(
        "SELECT system_prompt FROM channel_prompts WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id), fetch="one"
    )
    return row["system_prompt"] if row else None

async def set_channel_prompt(guild_id: str, channel_id: str, prompt: str):
    await execute(
        "INSERT INTO channel_prompts (guild_id, channel_id, system_prompt) VALUES (?, ?, ?) ON CONFLICT(guild_id, channel_id) DO UPDATE SET system_prompt = excluded.system_prompt",
        (guild_id, channel_id, prompt)
    )

async def delete_channel_prompt(guild_id: str, channel_id: str):
    await execute("DELETE FROM channel_prompts WHERE guild_id = ? AND channel_id = ?", (guild_id, channel_id))

async def get_all_channel_prompts(guild_id: str) -> dict[str, str]:
    rows = await execute("SELECT channel_id, system_prompt FROM channel_prompts WHERE guild_id = ?", (guild_id,), fetch="all")
    return {r["channel_id"]: r["system_prompt"] for r in (rows or [])}


# ── Channel provider helpers ──────────────────────────────────────────────────

async def get_channel_provider(guild_id: str, channel_id: str) -> str | None:
    row = await execute(
        "SELECT provider_name FROM channel_providers WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id), fetch="one"
    )
    return row["provider_name"] if row else None

async def set_channel_provider(guild_id: str, channel_id: str, provider_name: str):
    await execute(
        "INSERT INTO channel_providers (guild_id, channel_id, provider_name) VALUES (?, ?, ?) ON CONFLICT(guild_id, channel_id) DO UPDATE SET provider_name = excluded.provider_name",
        (guild_id, channel_id, provider_name)
    )

async def delete_channel_provider(guild_id: str, channel_id: str):
    await execute("DELETE FROM channel_providers WHERE guild_id = ? AND channel_id = ?", (guild_id, channel_id))

async def get_all_channel_providers(guild_id: str) -> dict[str, str]:
    rows = await execute("SELECT channel_id, provider_name FROM channel_providers WHERE guild_id = ?", (guild_id,), fetch="all")
    return {r["channel_id"]: r["provider_name"] for r in (rows or [])}


# ── Analytics helpers ─────────────────────────────────────────────────────────

async def add_analytics_event(event_type, guild_id=None, channel_id=None, user_id=None,
                               provider=None, tokens_used=None, input_tokens=None,
                               output_tokens=None, estimated_cost=None, latency_ms=None):
    await execute(
        "INSERT INTO analytics (event_type, guild_id, channel_id, user_id, provider, tokens_used, input_tokens, output_tokens, estimated_cost, latency_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (event_type, guild_id, channel_id, user_id, provider, tokens_used, input_tokens, output_tokens, estimated_cost or 0.0, latency_ms)
    )

async def get_analytics_summary(guild_id: str) -> dict:
    rows = await execute("SELECT event_type, COUNT(*) as count FROM analytics WHERE guild_id = ? GROUP BY event_type", (guild_id,), fetch="all") or []
    counts = {r["event_type"]: r["count"] for r in rows}
    row = await execute("SELECT AVG(latency_ms) as avg_latency FROM analytics WHERE guild_id = ? AND latency_ms IS NOT NULL", (guild_id,), fetch="one")
    avg_latency = row["avg_latency"] or 0 if row else 0
    row = await execute("SELECT provider, COUNT(*) as count FROM analytics WHERE guild_id = ? AND provider IS NOT NULL AND provider != 'none' GROUP BY provider ORDER BY count DESC LIMIT 1", (guild_id,), fetch="one")
    top_provider = row["provider"] if row else None
    row = await execute("SELECT channel_id, COUNT(*) as count FROM analytics WHERE guild_id = ? AND channel_id IS NOT NULL GROUP BY channel_id ORDER BY count DESC LIMIT 1", (guild_id,), fetch="one")
    top_channel = row["channel_id"] if row else None
    return {"total_messages": counts.get("command", 0) + counts.get("mention", 0), "total_commands": counts.get("command", 0), "total_mentions": counts.get("mention", 0), "avg_latency": avg_latency, "top_provider": top_provider, "top_channel": top_channel}

async def get_analytics_history(guild_id: str, days: int = 30) -> list[dict]:
    return await execute(
        "SELECT date(created_at) as date, COUNT(*) as total_events, SUM(CASE WHEN event_type='command' THEN 1 ELSE 0 END) as commands, AVG(latency_ms) as avg_latency FROM analytics WHERE guild_id = ? AND created_at >= datetime('now', ?) GROUP BY date(created_at) ORDER BY date ASC",
        (guild_id, f"-{days} days"), fetch="all"
    ) or []

async def get_analytics_provider_distribution(guild_id: str) -> list[dict]:
    return await execute(
        "SELECT provider, COUNT(*) as count FROM analytics WHERE guild_id = ? AND provider IS NOT NULL AND provider != 'none' GROUP BY provider ORDER BY count DESC",
        (guild_id,), fetch="all"
    ) or []

async def get_analytics_top_channels(guild_id: str, limit: int = 10) -> list[dict]:
    return await execute(
        "SELECT channel_id, COUNT(*) as count FROM analytics WHERE guild_id = ? AND channel_id IS NOT NULL GROUP BY channel_id ORDER BY count DESC LIMIT ?",
        (guild_id, limit), fetch="all"
    ) or []

async def get_global_analytics_summary() -> dict:
    row = await execute("SELECT COUNT(*) as total FROM analytics", fetch="one")
    total = row["total"] if row else 0
    rows = await execute("SELECT event_type, COUNT(*) as count FROM analytics GROUP BY event_type", fetch="all") or []
    counts = {r["event_type"]: r["count"] for r in rows}
    row = await execute("SELECT AVG(latency_ms) as avg FROM analytics WHERE latency_ms IS NOT NULL", fetch="one")
    avg_latency = row["avg"] or 0 if row else 0
    provider_dist = await execute("SELECT provider, COUNT(*) as count FROM analytics WHERE provider IS NOT NULL AND provider != 'none' GROUP BY provider ORDER BY count DESC", fetch="all") or []
    daily = await execute("SELECT date(created_at) as date, COUNT(*) as count FROM analytics WHERE created_at >= datetime('now', '-30 days') GROUP BY date(created_at) ORDER BY date ASC", fetch="all") or []
    return {"total_events": total, "counts": counts, "avg_latency": avg_latency, "provider_distribution": provider_dist, "daily_history": daily}


# ── Plugin helpers ────────────────────────────────────────────────────────────

async def get_enabled_plugins(guild_id: str) -> list[str]:
    rows = await execute("SELECT plugin_name FROM enabled_plugins WHERE guild_id = ?", (guild_id,), fetch="all")
    return [r["plugin_name"] for r in (rows or [])]

async def enable_plugin(guild_id: str, plugin_name: str):
    await execute("INSERT OR IGNORE INTO enabled_plugins (guild_id, plugin_name) VALUES (?, ?)", (guild_id, plugin_name))

async def disable_plugin(guild_id: str, plugin_name: str):
    await execute("DELETE FROM enabled_plugins WHERE guild_id = ? AND plugin_name = ?", (guild_id, plugin_name))


# ── Trivia helpers ────────────────────────────────────────────────────────────

async def update_trivia_score(guild_id: str, user_id: str, correct: bool):
    if correct:
        await execute("INSERT INTO trivia_scores (guild_id, user_id, correct, wrong) VALUES (?, ?, 1, 0) ON CONFLICT(guild_id, user_id) DO UPDATE SET correct = correct + 1", (guild_id, user_id))
    else:
        await execute("INSERT INTO trivia_scores (guild_id, user_id, correct, wrong) VALUES (?, ?, 0, 1) ON CONFLICT(guild_id, user_id) DO UPDATE SET wrong = wrong + 1", (guild_id, user_id))

async def get_trivia_score(guild_id: str, user_id: str) -> dict:
    row = await execute("SELECT correct, wrong FROM trivia_scores WHERE guild_id = ? AND user_id = ?", (guild_id, user_id), fetch="one")
    return {"correct": row["correct"], "wrong": row["wrong"]} if row else {"correct": 0, "wrong": 0}

async def get_trivia_leaderboard(guild_id: str, limit: int = 10) -> list[dict]:
    return await execute("SELECT user_id, correct, wrong FROM trivia_scores WHERE guild_id = ? ORDER BY correct DESC LIMIT ?", (guild_id, limit), fetch="all") or []


# ── Cost tracking helpers ─────────────────────────────────────────────────────

async def get_cost_summary(days: int = 30) -> list[dict]:
    return await execute(
        "SELECT date(created_at) as date, provider, SUM(estimated_cost) as daily_cost, SUM(input_tokens) as total_input, SUM(output_tokens) as total_output, COUNT(*) as requests FROM analytics WHERE created_at >= datetime('now', ?) AND provider IS NOT NULL AND provider != 'none' GROUP BY date(created_at), provider ORDER BY date ASC",
        (f"-{days} days",), fetch="all"
    ) or []

async def get_total_cost_by_provider(days: int = 30) -> list[dict]:
    return await execute(
        "SELECT provider, SUM(estimated_cost) as total_cost, SUM(input_tokens) as total_input_tokens, SUM(output_tokens) as total_output_tokens, COUNT(*) as total_requests FROM analytics WHERE created_at >= datetime('now', ?) AND provider IS NOT NULL AND provider != 'none' GROUP BY provider ORDER BY total_cost DESC",
        (f"-{days} days",), fetch="all"
    ) or []

async def get_monthly_projected_cost() -> dict:
    row = await execute("SELECT SUM(estimated_cost) as week_cost, COUNT(*) as week_requests FROM analytics WHERE created_at >= datetime('now', '-7 days')", fetch="one")
    week_cost = row["week_cost"] or 0.0 if row else 0.0
    week_requests = row["week_requests"] or 0 if row else 0
    return {"week_cost": round(week_cost, 4), "daily_avg_cost": round(week_cost/7, 4), "daily_avg_requests": round(week_requests/7, 1), "projected_monthly": round(week_cost/7*30, 4)}

async def get_cost_alert_status(threshold: float) -> dict:
    row = await execute("SELECT SUM(estimated_cost) as month_cost FROM analytics WHERE created_at >= datetime('now', 'start of month')", fetch="one")
    month_cost = row["month_cost"] or 0.0 if row else 0.0
    percentage = (month_cost / threshold * 100) if threshold > 0 else 0
    return {"month_cost": round(month_cost, 4), "threshold": threshold, "percentage": round(percentage, 1), "exceeded": month_cost >= threshold, "warning": percentage >= 80}


# ── Member analytics helpers ──────────────────────────────────────────────────

async def log_member_event(guild_id: str, user_id: str, username: str, event_type: str):
    await execute("INSERT INTO member_events (guild_id, user_id, username, event_type) VALUES (?, ?, ?, ?)", (guild_id, user_id, username, event_type))

async def log_member_message(guild_id: str, user_id: str, username: str, hour: int):
    await execute("INSERT INTO member_messages (guild_id, user_id, username, hour) VALUES (?, ?, ?, ?)", (guild_id, user_id, username, hour))

async def get_member_overview(guild_id: str, days: int = 30) -> dict:
    row = await execute("SELECT SUM(CASE WHEN event_type='join' THEN 1 ELSE 0 END) as joins_30d, SUM(CASE WHEN event_type='leave' THEN 1 ELSE 0 END) as leaves_30d FROM member_events WHERE guild_id = ? AND created_at >= datetime('now', ?)", (guild_id, f"-{days} days"), fetch="one")
    msg_row = await execute("SELECT COUNT(DISTINCT user_id) as active_members, COUNT(*) as total_messages FROM member_messages WHERE guild_id = ? AND created_at >= datetime('now', ?)", (guild_id, f"-{days} days"), fetch="one")
    return {**(dict(row) if row else {}), **(dict(msg_row) if msg_row else {})}

async def get_member_join_leave_history(guild_id: str, days: int = 30) -> list[dict]:
    return await execute("SELECT date(created_at) as date, SUM(CASE WHEN event_type='join' THEN 1 ELSE 0 END) as joins, SUM(CASE WHEN event_type='leave' THEN 1 ELSE 0 END) as leaves FROM member_events WHERE guild_id = ? AND created_at >= datetime('now', ?) GROUP BY date(created_at) ORDER BY date ASC", (guild_id, f"-{days} days"), fetch="all") or []

async def get_top_active_members(guild_id: str, days: int = 30, limit: int = 10) -> list[dict]:
    return await execute("SELECT user_id, username, COUNT(*) as message_count FROM member_messages WHERE guild_id = ? AND created_at >= datetime('now', ?) GROUP BY user_id ORDER BY message_count DESC LIMIT ?", (guild_id, f"-{days} days", limit), fetch="all") or []

async def get_peak_hours(guild_id: str, days: int = 30) -> list[dict]:
    rows = await execute("SELECT hour, COUNT(*) as message_count FROM member_messages WHERE guild_id = ? AND created_at >= datetime('now', ?) GROUP BY hour ORDER BY hour ASC", (guild_id, f"-{days} days"), fetch="all") or []
    row_map = {r["hour"]: r["message_count"] for r in rows}
    return [{"hour": h, "messages": row_map.get(h, 0)} for h in range(24)]