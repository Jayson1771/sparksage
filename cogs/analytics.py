from __future__ import annotations

import time
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import db as database


class Analytics(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="View bot usage statistics for this server")
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            guild_id = str(interaction.guild_id)
            summary = await database.get_analytics_summary(guild_id)

            embed = discord.Embed(
                title=f"📊 Analytics — {interaction.guild.name}",
                color=discord.Color.blurple()
            )
            embed.add_field(name="Total Messages", value=str(summary.get("total_messages", 0)), inline=True)
            embed.add_field(name="Commands Used", value=str(summary.get("total_commands", 0)), inline=True)
            embed.add_field(name="Mentions", value=str(summary.get("total_mentions", 0)), inline=True)
            embed.add_field(name="FAQs Triggered", value=str(summary.get("total_faqs", 0)), inline=True)
            embed.add_field(name="Messages Flagged", value=str(summary.get("total_moderation", 0)), inline=True)
            embed.add_field(name="Avg Latency", value=f"{summary.get('avg_latency', 0):.0f}ms", inline=True)

            # Top provider
            top_provider = summary.get("top_provider")
            if top_provider:
                embed.add_field(name="Most Used Provider", value=f"`{top_provider}`", inline=True)

            # Top channel
            top_channel = summary.get("top_channel")
            if top_channel:
                embed.add_field(name="Most Active Channel", value=f"<#{top_channel}>", inline=True)

            embed.set_footer(text="Full analytics available in the dashboard")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Error in /stats: {e}")
            await interaction.followup.send("❌ Could not load analytics. Please try again.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Analytics(bot))