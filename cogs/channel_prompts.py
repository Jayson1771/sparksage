from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import db as database


class ChannelPrompts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    prompt_group = app_commands.Group(
        name="prompt",
        description="Set a custom AI personality for this channel (Admin only)"
    )

    @prompt_group.command(name="set", description="Set a custom system prompt for this channel")
    @app_commands.describe(prompt="The system prompt / AI personality for this channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def prompt_set(self, interaction: discord.Interaction, prompt: str):
        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel_id)

        await database.set_channel_prompt(guild_id, channel_id, prompt)

        embed = discord.Embed(
            title="✅ Channel Prompt Set",
            color=discord.Color.green()
        )
        embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
        embed.add_field(name="Prompt Preview", value=f"```{prompt[:500]}```", inline=False)
        embed.set_footer(text="SparkSage will use this personality in this channel from now on.")
        await interaction.response.send_message(embed=embed)

    @prompt_group.command(name="reset", description="Reset this channel to use the global system prompt")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def prompt_reset(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel_id)

        await database.delete_channel_prompt(guild_id, channel_id)
        await interaction.response.send_message(
            f"✅ Channel prompt reset. {interaction.channel.mention} will now use the global system prompt."
        )

    @prompt_group.command(name="view", description="View the current system prompt for this channel")
    async def prompt_view(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel_id)

        channel_prompt = await database.get_channel_prompt(guild_id, channel_id)

        embed = discord.Embed(
            title=f"🎭 System Prompt — {interaction.channel.name}",
            color=discord.Color.blurple()
        )

        if channel_prompt:
            embed.description = f"```{channel_prompt[:1500]}```"
            embed.set_footer(text="This channel has a custom prompt. Use /prompt reset to remove it.")
        else:
            import config
            embed.description = f"*(Using global prompt)*\n```{config.SYSTEM_PROMPT[:1500]}```"
            embed.set_footer(text="Use /prompt set to give this channel a custom personality.")

        await interaction.response.send_message(embed=embed)

    @prompt_group.command(name="list", description="List all channels with custom prompts in this server")
    async def prompt_list(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        all_prompts = await database.get_all_channel_prompts(guild_id)

        if not all_prompts:
            await interaction.response.send_message(
                "No channels have custom prompts. Use `/prompt set` in any channel to add one."
            )
            return

        embed = discord.Embed(
            title="🎭 Custom Channel Prompts",
            color=discord.Color.blurple()
        )

        for channel_id, prompt in all_prompts.items():
            embed.add_field(
                name=f"<#{channel_id}>",
                value=f"```{prompt[:150]}{'...' if len(prompt) > 150 else ''}```",
                inline=False
            )

        embed.set_footer(text=f"{len(all_prompts)} channel(s) with custom prompts")
        await interaction.response.send_message(embed=embed)

    @prompt_group.command(name="copy", description="Copy the prompt from another channel to this one")
    @app_commands.describe(source="The channel to copy the prompt from")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def prompt_copy(self, interaction: discord.Interaction, source: discord.TextChannel):
        guild_id = str(interaction.guild_id)
        source_prompt = await database.get_channel_prompt(guild_id, str(source.id))

        if not source_prompt:
            await interaction.response.send_message(
                f"❌ {source.mention} doesn't have a custom prompt to copy.", ephemeral=True
            )
            return

        await database.set_channel_prompt(guild_id, str(interaction.channel_id), source_prompt)
        await interaction.response.send_message(
            f"✅ Copied prompt from {source.mention} to {interaction.channel.mention}."
        )

    # --- Error Handler ---

    @prompt_set.error
    @prompt_reset.error
    @prompt_copy.error
    async def prompt_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Manage Channels** permission to use this command.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelPrompts(bot))