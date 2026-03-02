from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import db as database


class MemberAnalytics(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await database.log_member_event(
            guild_id=str(member.guild.id),
            user_id=str(member.id),
            username=str(member),
            event_type="join"
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await database.log_member_event(
            guild_id=str(member.guild.id),
            user_id=str(member.id),
            username=str(member),
            event_type="leave"
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        await database.log_member_message(
            guild_id=str(message.guild.id),
            user_id=str(message.author.id),
            username=str(message.author),
            hour=message.created_at.hour
        )

    @app_commands.command(name="members", description="Show server member analytics")
    async def members(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        stats = await database.get_member_overview(guild_id)

        embed = discord.Embed(title="Member Analytics", color=discord.Color.blurple())
        embed.add_field(name="Total Members", value=interaction.guild.member_count, inline=True)
        embed.add_field(name="Joins (30d)", value=stats.get("joins_30d", 0), inline=True)
        embed.add_field(name="Leaves (30d)", value=stats.get("leaves_30d", 0), inline=True)
        embed.add_field(name="Net Growth", value=stats.get("joins_30d", 0) - stats.get("leaves_30d", 0), inline=True)
        embed.add_field(name="Active Members (30d)", value=stats.get("active_members", 0), inline=True)
        embed.add_field(name="Messages (30d)", value=stats.get("total_messages", 0), inline=True)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(MemberAnalytics(bot))