from __future__ import annotations

import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import config
import db as database


def format_welcome_message(template: str, user: discord.Member, guild: discord.Guild) -> str:
    """Replace placeholders in the welcome message template."""
    return (
        template
        .replace("{user}", user.mention)
        .replace("{username}", user.display_name)
        .replace("{server}", guild.name)
        .replace("{member_count}", str(guild.member_count))
    )


class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- on_member_join Event ---

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)

        # Check if onboarding is enabled
        enabled = await database.get_onboarding_config(guild_id, "WELCOME_ENABLED")
        if not enabled or enabled.lower() != "true":
            return

        welcome_channel_id = await database.get_onboarding_config(guild_id, "WELCOME_CHANNEL_ID")
        welcome_message = await database.get_onboarding_config(guild_id, "WELCOME_MESSAGE")

        if not welcome_message:
            welcome_message = (
                "👋 Welcome to **{server}**, {user}!\n\n"
                "We're glad to have you here. Feel free to introduce yourself and ask any questions.\n"
                "You can ask me anything by using `/ask` or mentioning me directly!"
            )

        formatted = format_welcome_message(welcome_message, member, member.guild)

        embed = discord.Embed(
            description=formatted,
            color=discord.Color.green()
        )
        embed.set_author(name=f"Welcome, {member.display_name}!", icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"{member.guild.name} • Member #{member.guild.member_count}")

        # Try to send to configured welcome channel
        if welcome_channel_id:
            channel = member.guild.get_channel(int(welcome_channel_id))
            if channel:
                try:
                    await channel.send(embed=embed)
                    return
                except discord.Forbidden:
                    print(f"Missing permissions to send in welcome channel {welcome_channel_id}")

        # Fallback: try system channel
        if member.guild.system_channel:
            try:
                await member.guild.system_channel.send(embed=embed)
            except discord.Forbidden:
                print(f"Missing permissions to send in system channel for guild {guild_id}")

    # --- Admin Commands ---

    onboarding_group = app_commands.Group(
        name="onboarding",
        description="Configure the welcome/onboarding system (Admin only)"
    )

    @onboarding_group.command(name="enable", description="Enable welcome messages for new members")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def onboarding_enable(self, interaction: discord.Interaction):
        await database.set_onboarding_config(str(interaction.guild_id), "WELCOME_ENABLED", "true")
        await interaction.response.send_message("✅ Onboarding enabled! New members will receive a welcome message.")

    @onboarding_group.command(name="disable", description="Disable welcome messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def onboarding_disable(self, interaction: discord.Interaction):
        await database.set_onboarding_config(str(interaction.guild_id), "WELCOME_ENABLED", "false")
        await interaction.response.send_message("⏸️ Onboarding disabled. No welcome messages will be sent.")

    @onboarding_group.command(name="setchannel", description="Set the channel for welcome messages")
    @app_commands.describe(channel="The channel to send welcome messages in")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def onboarding_setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_onboarding_config(str(interaction.guild_id), "WELCOME_CHANNEL_ID", str(channel.id))
        await interaction.response.send_message(f"✅ Welcome channel set to {channel.mention}")

    @onboarding_group.command(name="setmessage", description="Set a custom welcome message")
    @app_commands.describe(message="Welcome message template. Use {user}, {username}, {server}, {member_count}")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def onboarding_setmessage(self, interaction: discord.Interaction, message: str):
        await database.set_onboarding_config(str(interaction.guild_id), "WELCOME_MESSAGE", message)

        # Show preview
        preview = format_welcome_message(message, interaction.user, interaction.guild)
        embed = discord.Embed(
            title="✅ Welcome message updated!",
            color=discord.Color.green()
        )
        embed.add_field(name="Preview", value=preview, inline=False)
        embed.set_footer(text="Available placeholders: {user} {username} {server} {member_count}")
        await interaction.response.send_message(embed=embed)

    @onboarding_group.command(name="status", description="View current onboarding configuration")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def onboarding_status(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)

        enabled = await database.get_onboarding_config(guild_id, "WELCOME_ENABLED") or "false"
        channel_id = await database.get_onboarding_config(guild_id, "WELCOME_CHANNEL_ID")
        message = await database.get_onboarding_config(guild_id, "WELCOME_MESSAGE") or "*(default message)*"

        channel_display = f"<#{channel_id}>" if channel_id else "*(not set — uses system channel)*"

        embed = discord.Embed(
            title="⚙️ Onboarding Configuration",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Status", value="✅ Enabled" if enabled == "true" else "⏸️ Disabled", inline=True)
        embed.add_field(name="Welcome Channel", value=channel_display, inline=True)
        embed.add_field(name="Message Template", value=message[:500], inline=False)
        embed.set_footer(text="Use /onboarding setmessage and /onboarding setchannel to configure")
        await interaction.response.send_message(embed=embed)

    @onboarding_group.command(name="test", description="Simulate a welcome message for yourself")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def onboarding_test(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        welcome_message = await database.get_onboarding_config(guild_id, "WELCOME_MESSAGE")

        if not welcome_message:
            welcome_message = (
                "👋 Welcome to **{server}**, {user}!\n\n"
                "We're glad to have you here. Feel free to introduce yourself and ask any questions.\n"
                "You can ask me anything by using `/ask` or mentioning me directly!"
            )

        formatted = format_welcome_message(welcome_message, interaction.user, interaction.guild)

        embed = discord.Embed(
            description=formatted,
            color=discord.Color.green()
        )
        embed.set_author(
            name=f"Welcome, {interaction.user.display_name}!",
            icon_url=interaction.user.display_avatar.url
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"This is a test preview • {interaction.guild.name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Error Handler ---

    @onboarding_enable.error
    @onboarding_disable.error
    @onboarding_setchannel.error
    @onboarding_setmessage.error
    @onboarding_status.error
    @onboarding_test.error
    async def onboarding_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission to use this command.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))