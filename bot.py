from __future__ import annotations

import asyncio
import time
import discord
from discord.ext import commands
import config
import providers
import db as database

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents)

COGS = [
    "cogs.general",
    "cogs.summarize",
    "cogs.code_review",
    "cogs.faq",
    "cogs.onboarding",
    "cogs.permissions",
    "cogs.digest",
    "cogs.moderation",
    "cogs.translate",
    "cogs.channel_prompts",
    "cogs.channel_providers",
    "cogs.analytics",
    "cogs.quota",
    "cogs.plugin_manager",
    "cogs.cost_tracking",
    "cogs.member_analytics",
]


def get_bot_status() -> dict:
    """Return bot status info for the dashboard API."""
    if bot.is_ready():
        return {
            "online": True,
            "username": str(bot.user),
            "latency_ms": round(bot.latency * 1000, 1),
            "guild_count": len(bot.guilds),
            "guilds": [{"id": str(g.id), "name": g.name, "member_count": g.member_count} for g in bot.guilds],
        }
    return {"online": False, "username": None, "latency_ms": None, "guild_count": 0, "guilds": []}


# --- Events ---


@bot.event
async def on_ready():
    await database.init_db()
    await database.sync_env_to_db()

    available = providers.get_available_providers()
    primary = config.AI_PROVIDER
    provider_info = config.PROVIDERS.get(primary, {})

    print(f"SparkSage is online as {bot.user}")
    print(f"Primary provider: {provider_info.get('name', primary)} ({provider_info.get('model', '?')})")
    print(f"Fallback chain: {' -> '.join(available)}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    if bot.user in message.mentions:
        clean_content = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if not clean_content:
            clean_content = "Hello!"

        # Check rate limit
        from utils.rate_limiter import get_limiter
        limiter = get_limiter()
        allowed, reason = limiter.check(
            user_id=str(message.author.id),
            guild_id=str(message.guild.id) if message.guild else None
        )
        if not allowed:
            await message.reply(f"⏳ **Rate limited:** {reason}", mention_author=False)
            await bot.process_commands(message)
            return

        start = time.time()
        async with message.channel.typing():
            cog = bot.cogs.get("General")
            if cog:
                response, provider_name = await cog._ask_ai(
                    message.channel.id,
                    message.author.display_name,
                    clean_content,
                    guild_id=str(message.guild.id) if message.guild else None
                )
            else:
                response = "I'm not ready yet. Please try again in a moment."
                provider_name = "none"

        latency_ms = int((time.time() - start) * 1000)

        # Track analytics
        await database.add_analytics_event(
            event_type="mention",
            guild_id=str(message.guild.id) if message.guild else None,
            channel_id=str(message.channel.id),
            user_id=str(message.author.id),
            provider=provider_name,
            latency_ms=latency_ms,
        )

        for i in range(0, len(response), 2000):
            await message.reply(response[i: i + 2000])

    await bot.process_commands(message)


# --- Cog Loader ---


async def load_cogs():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"Loaded cog: {cog}")
        except Exception as e:
            print(f"Failed to load cog {cog}: {e}")


async def start():
    async with bot:
        await load_cogs()
        await bot.start(config.DISCORD_TOKEN)


# --- Run ---


def main():
    if not config.DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not set.")
        return

    available = providers.get_available_providers()
    if not available:
        print("Error: No AI providers configured. Add at least one API key.")
        return

    asyncio.run(start())


if __name__ == "__main__":
    main()