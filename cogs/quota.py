from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
from utils.rate_limiter import get_limiter, reload_limiter
import db as database


class QuotaManagement(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    quota_group = app_commands.Group(
        name="quota",
        description="Manage rate limits and quotas (Admin only)"
    )

    @quota_group.command(name="status", description="View current rate limit configuration")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def quota_status(self, interaction: discord.Interaction):
        limiter = get_limiter()
        guild_status = limiter.get_guild_status(str(interaction.guild_id))

        embed = discord.Embed(title="⏳ Rate Limit Configuration", color=discord.Color.blurple())
        embed.add_field(
            name="Per User",
            value=f"**{limiter.user_limit}** requests / 60 seconds",
            inline=True
        )
        embed.add_field(
            name="Per Server",
            value=f"**{limiter.guild_limit}** requests / 60 seconds",
            inline=True
        )
        embed.add_field(
            name="Server Usage Now",
            value=f"{guild_status['remaining']}/{limiter.guild_limit} remaining",
            inline=True
        )
        embed.set_footer(text="Use /quota setlimit to change limits")
        await interaction.response.send_message(embed=embed)

    @quota_group.command(name="setlimit", description="Update rate limit values")
    @app_commands.describe(
        user_limit="Max requests per user per minute (default: 5)",
        guild_limit="Max requests per server per minute (default: 30)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def quota_setlimit(
        self,
        interaction: discord.Interaction,
        user_limit: int | None = None,
        guild_limit: int | None = None,
    ):
        if not user_limit and not guild_limit:
            await interaction.response.send_message(
                "❌ Please provide at least one limit to update.", ephemeral=True
            )
            return

        limiter = get_limiter()
        limiter.update_limits(user_limit=user_limit, guild_limit=guild_limit)

        # Save to DB config
        if user_limit:
            await database.set_config("RATE_LIMIT_USER", str(user_limit))
        if guild_limit:
            await database.set_config("RATE_LIMIT_GUILD", str(guild_limit))

        embed = discord.Embed(title="✅ Rate Limits Updated", color=discord.Color.green())
        if user_limit:
            embed.add_field(name="Per User", value=f"**{user_limit}** requests/min", inline=True)
        if guild_limit:
            embed.add_field(name="Per Server", value=f"**{guild_limit}** requests/min", inline=True)
        embed.set_footer(text="Changes take effect immediately.")
        await interaction.response.send_message(embed=embed)

    @quota_group.command(name="reset", description="Reset rate limit for a specific user")
    @app_commands.describe(user="The user to reset rate limits for")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def quota_reset(self, interaction: discord.Interaction, user: discord.Member):
        limiter = get_limiter()
        limiter.reset_user(str(user.id))
        await interaction.response.send_message(
            f"✅ Rate limit reset for {user.mention}. They can make requests again immediately."
        )

    @quota_group.command(name="resetserver", description="Reset rate limit for this entire server")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def quota_resetserver(self, interaction: discord.Interaction):
        limiter = get_limiter()
        limiter.reset_guild(str(interaction.guild_id))
        await interaction.response.send_message(
            "✅ Server rate limit reset. All users can make requests again immediately."
        )

    @quota_group.command(name="check", description="Check the rate limit status of a user")
    @app_commands.describe(user="The user to check (defaults to yourself)")
    async def quota_check(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        limiter = get_limiter()
        status = limiter.get_user_status(str(target.id))

        embed = discord.Embed(
            title=f"⏳ Rate Limit — {target.display_name}",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Remaining", value=f"{status['remaining']}/{status['limit']}", inline=True)
        embed.add_field(name="Window", value=f"{status['window_seconds']}s", inline=True)
        if status['retry_after'] > 0:
            embed.add_field(name="Retry After", value=f"{status['retry_after']:.0f}s", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Error Handler ---

    @quota_status.error
    @quota_setlimit.error
    @quota_reset.error
    @quota_resetserver.error
    async def quota_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(QuotaManagement(bot))