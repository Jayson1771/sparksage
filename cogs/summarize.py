from __future__ import annotations

import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import config
import providers
import db as database


class Summarize(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="summarize", description="Summarize the recent conversation in this channel")
    async def summarize(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            messages = await database.get_messages(str(interaction.channel_id), limit=20)
            history = [{"role": m["role"], "content": m["content"]} for m in messages]

            if not history:
                await interaction.followup.send("No conversation history to summarize.")
                return

            summary_prompt = "Please summarize the key points from this conversation so far in a concise bullet-point format."
            await database.add_message(str(interaction.channel_id), "user", summary_prompt)

            loop = asyncio.get_event_loop()
            response, provider_name = await loop.run_in_executor(
                None, providers.chat, history, config.SYSTEM_PROMPT
            )
            await database.add_message(str(interaction.channel_id), "assistant", response, provider=provider_name)
            await interaction.followup.send(f"**Conversation Summary:**\n{response}")
        except Exception as e:
            print(f"Error in /summarize: {e}")
            await interaction.followup.send("Something went wrong. Please try again.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Summarize(bot))