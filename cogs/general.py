from __future__ import annotations

import time
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import config
import providers
import db as database


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ask", description="Ask SparkSage a question")
    @app_commands.describe(question="Your question for SparkSage")
    async def ask(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        try:
            start = time.time()
            response, provider_name = await self._ask_ai(
                interaction.channel_id,
                interaction.user.display_name,
                question,
                guild_id=str(interaction.guild_id) if interaction.guild_id else None
            )
            latency_ms = int((time.time() - start) * 1000)

            print(f"[ANALYTICS DEBUG] Saving event: provider={provider_name} latency={latency_ms}ms")
            try:
                await database.add_analytics_event(
                    event_type="command",
                    guild_id=str(interaction.guild_id) if interaction.guild_id else None,
                    channel_id=str(interaction.channel_id),
                    user_id=str(interaction.user.id),
                    provider=provider_name,
                    input_tokens=0,
                    output_tokens=0,
                    estimated_cost=0.0,
                    latency_ms=latency_ms,
                )
                print(f"[ANALYTICS DEBUG] Event saved successfully!")
            except Exception as e:
                print(f"[ANALYTICS DEBUG] FAILED to save event: {e}")
                import traceback
                traceback.print_exc()

            provider_label = config.PROVIDERS.get(provider_name, {}).get("name", provider_name)
            footer = f"\n-# Powered by {provider_label}"

            for i in range(0, len(response), 1900):
                chunk = response[i: i + 1900]
                if i + 1900 >= len(response):
                    chunk += footer
                await interaction.followup.send(chunk)
        except Exception as e:
            print(f"Error in /ask: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send("Something went wrong. Please try again.")

    @app_commands.command(name="clear", description="Clear SparkSage's conversation memory for this channel")
    async def clear(self, interaction: discord.Interaction):
        await database.clear_messages(str(interaction.channel_id))
        await interaction.response.send_message("Conversation history cleared!")

    @app_commands.command(name="provider", description="Show which AI provider SparkSage is currently using")
    async def provider(self, interaction: discord.Interaction):
        primary = config.AI_PROVIDER
        provider_info = config.PROVIDERS.get(primary, {})
        available = providers.get_available_providers()

        msg = f"**Current Provider:** {provider_info.get('name', primary)}\n"
        msg += f"**Model:** `{provider_info.get('model', '?')}`\n"
        msg += f"**Free:** {'Yes' if provider_info.get('free') else 'No (paid)'}\n"
        msg += f"**Fallback Chain:** {' -> '.join(available)}"
        await interaction.response.send_message(msg)

    async def _ask_ai(
        self,
        channel_id: int,
        user_name: str,
        message: str,
        guild_id: str | None = None
    ) -> tuple[str, str]:
        await database.add_message(str(channel_id), "user", f"{user_name}: {message}")
        messages = await database.get_messages(str(channel_id), limit=20)
        history = [{"role": m["role"], "content": m["content"]} for m in messages]

        system_prompt = config.SYSTEM_PROMPT
        if guild_id:
            channel_prompt = await database.get_channel_prompt(guild_id, str(channel_id))
            if channel_prompt:
                system_prompt = channel_prompt

        channel_provider = None
        if guild_id:
            channel_provider = await database.get_channel_provider(guild_id, str(channel_id))

        try:
            loop = asyncio.get_event_loop()
            if channel_provider:
                response, provider_name = await loop.run_in_executor(
                    None, providers.chat_with_provider, history, system_prompt, channel_provider
                )
            else:
                response, provider_name = await loop.run_in_executor(
                    None, providers.chat, history, system_prompt
                )
            await database.add_message(str(channel_id), "assistant", response, provider=provider_name)
            return response, provider_name
        except RuntimeError as e:
            return f"Sorry, all AI providers failed:\n{e}", "none"


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))