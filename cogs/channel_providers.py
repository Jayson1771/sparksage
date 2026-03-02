from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import config
import providers
import db as database


PROVIDER_CHOICES = [
    app_commands.Choice(name="Google Gemini (Free)", value="gemini"),
    app_commands.Choice(name="Groq (Free)", value="groq"),
    app_commands.Choice(name="OpenRouter (Free)", value="openrouter"),
    app_commands.Choice(name="Anthropic Claude (Paid)", value="anthropic"),
    app_commands.Choice(name="OpenAI GPT (Paid)", value="openai"),
]


class ChannelProviders(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    channel_provider_group = app_commands.Group(
        name="channel-provider",
        description="Set a specific AI provider for this channel (Admin only)"
    )

    @channel_provider_group.command(name="set", description="Use a specific AI provider in this channel")
    @app_commands.describe(
        provider="The AI provider to use in this channel",
        channel="Channel to configure (defaults to current channel)"
    )
    @app_commands.choices(provider=PROVIDER_CHOICES)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def provider_set(
        self,
        interaction: discord.Interaction,
        provider: str,
        channel: discord.TextChannel | None = None,
    ):
        target_channel = channel or interaction.channel
        guild_id = str(interaction.guild_id)
        channel_id = str(target_channel.id)

        available = providers.get_available_providers()
        if provider not in config.PROVIDERS:
            provider_list = ", ".join(f"`{p}`" for p in config.PROVIDERS.keys())
            await interaction.response.send_message(
                f"❌ Unknown provider `{provider}`. Available: {provider_list}", ephemeral=True
            )
            return

        if provider not in available:
            await interaction.response.send_message(
                f"❌ Provider `{provider}` is not configured. Add its API key in the dashboard first.",
                ephemeral=True
            )
            return

        await database.set_channel_provider(guild_id, channel_id, provider)

        provider_info = config.PROVIDERS.get(provider, {})
        embed = discord.Embed(title="✅ Channel Provider Set", color=discord.Color.green())
        embed.add_field(name="Channel", value=target_channel.mention, inline=True)
        embed.add_field(name="Provider", value=provider_info.get("name", provider), inline=True)
        embed.add_field(name="Model", value=f"`{provider_info.get('model', '?')}`", inline=True)
        embed.add_field(name="Free", value="Yes ✅" if provider_info.get("free") else "No 💰", inline=True)
        embed.set_footer(text="This channel will use this provider instead of the global default.")
        await interaction.response.send_message(embed=embed)

    @channel_provider_group.command(name="reset", description="Reset this channel to use the global AI provider")
    @app_commands.describe(channel="Channel to reset (defaults to current channel)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def provider_reset(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ):
        target_channel = channel or interaction.channel
        guild_id = str(interaction.guild_id)
        await database.delete_channel_provider(guild_id, str(target_channel.id))
        await interaction.response.send_message(
            f"✅ {target_channel.mention} will now use the global provider (`{config.AI_PROVIDER}`)."
        )

    @channel_provider_group.command(name="view", description="View the AI provider for this channel")
    @app_commands.describe(channel="Channel to check (defaults to current channel)")
    async def provider_view(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ):
        target_channel = channel or interaction.channel
        guild_id = str(interaction.guild_id)
        channel_provider = await database.get_channel_provider(guild_id, str(target_channel.id))

        embed = discord.Embed(
            title=f"🤖 AI Provider — {target_channel.name}",
            color=discord.Color.blurple()
        )

        if channel_provider:
            provider_info = config.PROVIDERS.get(channel_provider, {})
            embed.add_field(name="Provider", value=provider_info.get("name", channel_provider), inline=True)
            embed.add_field(name="Model", value=f"`{provider_info.get('model', '?')}`", inline=True)
            embed.add_field(name="Free", value="Yes ✅" if provider_info.get("free") else "No 💰", inline=True)
            embed.set_footer(text="This channel has a custom provider. Use /channel-provider reset to remove it.")
        else:
            global_info = config.PROVIDERS.get(config.AI_PROVIDER, {})
            embed.add_field(name="Provider", value=f"{global_info.get('name', config.AI_PROVIDER)} *(global)*", inline=True)
            embed.add_field(name="Model", value=f"`{global_info.get('model', '?')}`", inline=True)
            embed.set_footer(text="Use /channel-provider set to override for this channel.")

        await interaction.response.send_message(embed=embed)

    @channel_provider_group.command(name="list", description="List all channels with custom AI providers")
    async def provider_list(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        all_providers = await database.get_all_channel_providers(guild_id)

        if not all_providers:
            await interaction.response.send_message(
                "No channels have custom providers. All channels use the global provider."
            )
            return

        embed = discord.Embed(title="🤖 Channel Provider Overrides", color=discord.Color.blurple())
        for channel_id, provider_name in all_providers.items():
            provider_info = config.PROVIDERS.get(provider_name, {})
            embed.add_field(
                name=f"<#{channel_id}>",
                value=f"{provider_info.get('name', provider_name)}\n`{provider_info.get('model', '?')}`",
                inline=True
            )
        embed.set_footer(text=f"Global default: {config.AI_PROVIDER} • {len(all_providers)} override(s)")
        await interaction.response.send_message(embed=embed)

    @channel_provider_group.command(name="available", description="Show all available AI providers")
    async def provider_available(self, interaction: discord.Interaction):
        available = providers.get_available_providers()
        embed = discord.Embed(title="🤖 Available AI Providers", color=discord.Color.blurple())
        for name, info in config.PROVIDERS.items():
            is_available = name in available
            is_primary = name == config.AI_PROVIDER
            status = "✅ Ready" if is_available else "❌ Not configured"
            primary_tag = " 🌟 Primary" if is_primary else ""
            embed.add_field(
                name=f"{info['name']}{primary_tag}",
                value=f"`{name}` • {status}\nModel: `{info['model']}`\nFree: {'Yes' if info['free'] else 'No'}",
                inline=True
            )
        embed.set_footer(text="Use /channel-provider set to assign a provider to a channel.")
        await interaction.response.send_message(embed=embed)

    @provider_set.error
    @provider_reset.error
    async def provider_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Manage Channels** permission to use this command.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelProviders(bot))