from __future__ import annotations

import asyncio
import json
import discord
from discord.ext import commands
from discord import app_commands
import config
import providers
import db as database


MODERATION_PROMPT = """You are a content moderation assistant. Analyze the following Discord message and rate it for policy violations.

Respond ONLY with a valid JSON object in this exact format:
{
  "flagged": true or false,
  "reason": "brief explanation or null if not flagged",
  "severity": "low" or "medium" or "high" or null,
  "categories": ["toxicity", "spam", "harassment", "nsfw", "threats"] (only include relevant ones)
}

Be conservative — only flag clear violations. Do not flag mild rudeness, jokes, or off-topic messages.
Never auto-decide to delete or ban — only flag for human review."""

SENSITIVITY_THRESHOLDS = {
    "low": ["high"],
    "medium": ["medium", "high"],
    "high": ["low", "medium", "high"],
}

SEVERITY_COLORS = {
    "low": discord.Color.yellow(),
    "medium": discord.Color.orange(),
    "high": discord.Color.red(),
}

SEVERITY_EMOJIS = {
    "low": "🟡",
    "medium": "🟠",
    "high": "🔴",
}


async def _get_banned_words(guild_id: str) -> list[str]:
    """Read banned words from the moderation_extra_config JSON."""
    try:
        val = await database.get_config("moderation_extra_config")
        if val:
            data = json.loads(val)
            return [w.lower() for w in data.get("banned_words", [])]
    except Exception:
        pass
    return []


def _check_banned_words(content: str, banned_words: list[str]) -> str | None:
    """Return the matched banned word if found, else None."""
    content_lower = content.lower()
    for word in banned_words:
        if word and word in content_lower:
            return word
    return None


class ModerationView(discord.ui.View):
    """Action buttons for mod log messages."""

    def __init__(self, message_author_id: int, channel_id: int, message_id: int):
        super().__init__(timeout=None)
        self.message_author_id = message_author_id
        self.channel_id = channel_id
        self.message_id = message_id

    @discord.ui.button(label="✅ Dismiss", style=discord.ButtonStyle.secondary)
    async def dismiss(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need Manage Messages permission.", ephemeral=True)
            return
        await interaction.message.edit(
            content=f"~~{interaction.message.content}~~ ✅ Dismissed by {interaction.user.mention}",
            view=None
        )
        await interaction.response.send_message("Flag dismissed.", ephemeral=True)

    @discord.ui.button(label="🗑️ Delete Message", style=discord.ButtonStyle.danger)
    async def delete_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need Manage Messages permission.", ephemeral=True)
            return
        try:
            channel = interaction.guild.get_channel(self.channel_id)
            if channel:
                msg = await channel.fetch_message(self.message_id)
                await msg.delete()
            await interaction.message.edit(
                content=f"🗑️ Message deleted by {interaction.user.mention}",
                view=None
            )
            await interaction.response.send_message("Message deleted.", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("Message already deleted.", ephemeral=True)

    @discord.ui.button(label="⚠️ Warn User", style=discord.ButtonStyle.primary)
    async def warn_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need Manage Messages permission.", ephemeral=True)
            return
        try:
            user = await interaction.guild.fetch_member(self.message_author_id)
            await user.send(
                f"⚠️ You have received a warning in **{interaction.guild.name}** for a message that violated server rules. "
                f"Please review the server rules and be mindful of your messages."
            )
            await interaction.message.edit(
                content=f"⚠️ User warned by {interaction.user.mention}",
                view=None
            )
            await interaction.response.send_message("User warned via DM.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Could not warn user: {e}", ephemeral=True)


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        if not message.content or len(message.content) < 2:
            return

        guild_id = str(message.guild.id)

        enabled = await database.get_moderation_config(guild_id, "MODERATION_ENABLED")
        if not enabled or enabled.lower() != "true":
            return

        mod_log_channel_id = await database.get_moderation_config(guild_id, "MOD_LOG_CHANNEL_ID")
        if not mod_log_channel_id:
            return

        mod_channel = message.guild.get_channel(int(mod_log_channel_id))
        if not mod_channel:
            return

        # ── 1. Check banned words first (fast, no AI needed) ──────────────────
        banned_words = await _get_banned_words(guild_id)
        matched_word = _check_banned_words(message.content, banned_words)

        if matched_word:
            await database.add_moderation_log(
                guild_id=guild_id,
                channel_id=str(message.channel.id),
                message_id=str(message.id),
                author_id=str(message.author.id),
                content=message.content[:500],
                reason=f"Banned word detected: '{matched_word}'",
                severity="high",
                categories="banned_word"
            )

            embed = discord.Embed(
                title="🔴 Banned Word Detected",
                color=discord.Color.red(),
                timestamp=message.created_at
            )
            embed.add_field(name="Author", value=f"{message.author.mention} (`{message.author}`)", inline=True)
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            embed.add_field(name="Severity", value="**HIGH**", inline=True)
            embed.add_field(name="Reason", value=f"Banned word: `{matched_word}`", inline=False)
            embed.add_field(name="Message Content", value=f"```{message.content[:900]}```", inline=False)
            embed.add_field(name="Jump to Message", value=f"[Click here]({message.jump_url})", inline=False)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.set_footer(text="SparkSage Moderation • Human review required")

            view = ModerationView(
                message_author_id=message.author.id,
                channel_id=message.channel.id,
                message_id=message.id
            )
            await mod_channel.send(embed=embed, view=view)
            return  # Don't double-flag with AI

        # ── 2. AI moderation check ─────────────────────────────────────────────
        if len(message.content) < 5:
            return

        sensitivity = await database.get_moderation_config(guild_id, "MODERATION_SENSITIVITY") or "medium"

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._check_message, message.content)

            if not result or not result.get("flagged"):
                return

            severity = result.get("severity")
            threshold = SENSITIVITY_THRESHOLDS.get(sensitivity, ["medium", "high"])

            if severity not in threshold:
                return

            await database.add_moderation_log(
                guild_id=guild_id,
                channel_id=str(message.channel.id),
                message_id=str(message.id),
                author_id=str(message.author.id),
                content=message.content[:500],
                reason=result.get("reason", ""),
                severity=severity,
                categories=",".join(result.get("categories", []))
            )

            emoji = SEVERITY_EMOJIS.get(severity, "🟡")
            color = SEVERITY_COLORS.get(severity, discord.Color.yellow())

            embed = discord.Embed(
                title=f"{emoji} Message Flagged for Review",
                color=color,
                timestamp=message.created_at
            )
            embed.add_field(name="Author", value=f"{message.author.mention} (`{message.author}`)", inline=True)
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            embed.add_field(name="Severity", value=f"**{severity.upper()}**", inline=True)
            embed.add_field(name="Reason", value=result.get("reason", "N/A"), inline=False)
            embed.add_field(name="Categories", value=", ".join(result.get("categories", [])) or "N/A", inline=False)
            embed.add_field(name="Message Content", value=f"```{message.content[:900]}```", inline=False)
            embed.add_field(name="Jump to Message", value=f"[Click here]({message.jump_url})", inline=False)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.set_footer(text="SparkSage Moderation • Human review required")

            view = ModerationView(
                message_author_id=message.author.id,
                channel_id=message.channel.id,
                message_id=message.id
            )
            await mod_channel.send(embed=embed, view=view)

        except Exception as e:
            print(f"Moderation error in guild {guild_id}: {e}")

    def _check_message(self, content: str) -> dict | None:
        try:
            history = [{"role": "user", "content": f"Message to moderate:\n{content}"}]
            response, _ = providers.chat(history, MODERATION_PROMPT)
            response = response.strip()
            if "```" in response:
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response.strip())
        except Exception as e:
            print(f"Moderation AI parse error: {e}")
            return None

    # --- Admin Commands ---

    moderation_group = app_commands.Group(
        name="moderation",
        description="Configure content moderation (Admin only)"
    )

    @moderation_group.command(name="enable", description="Enable AI content moderation")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mod_enable(self, interaction: discord.Interaction):
        await database.set_moderation_config(str(interaction.guild_id), "MODERATION_ENABLED", "true")
        await interaction.response.send_message("✅ Content moderation enabled!")

    @moderation_group.command(name="disable", description="Disable AI content moderation")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mod_disable(self, interaction: discord.Interaction):
        await database.set_moderation_config(str(interaction.guild_id), "MODERATION_ENABLED", "false")
        await interaction.response.send_message("⏹️ Content moderation disabled.")

    @moderation_group.command(name="setchannel", description="Set the mod-log channel for flagged messages")
    @app_commands.describe(channel="Channel to post moderation alerts in")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mod_setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_moderation_config(str(interaction.guild_id), "MOD_LOG_CHANNEL_ID", str(channel.id))
        await interaction.response.send_message(f"✅ Mod log channel set to {channel.mention}")

    @moderation_group.command(name="sensitivity", description="Set moderation sensitivity level")
    @app_commands.describe(level="low=only high severity, medium=medium+high, high=flag everything")
    @app_commands.choices(level=[
        app_commands.Choice(name="Low (only flag high severity)", value="low"),
        app_commands.Choice(name="Medium (flag medium + high)", value="medium"),
        app_commands.Choice(name="High (flag everything)", value="high"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mod_sensitivity(self, interaction: discord.Interaction, level: str):
        await database.set_moderation_config(str(interaction.guild_id), "MODERATION_SENSITIVITY", level)
        await interaction.response.send_message(f"✅ Moderation sensitivity set to **{level}**.")

    @moderation_group.command(name="status", description="View current moderation configuration")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mod_status(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        enabled = await database.get_moderation_config(guild_id, "MODERATION_ENABLED") or "false"
        channel_id = await database.get_moderation_config(guild_id, "MOD_LOG_CHANNEL_ID")
        sensitivity = await database.get_moderation_config(guild_id, "MODERATION_SENSITIVITY") or "medium"
        total_flags = await database.get_moderation_count(guild_id)
        banned_words = await _get_banned_words(guild_id)
        channel_display = f"<#{channel_id}>" if channel_id else "*(not set)*"

        embed = discord.Embed(title="⚙️ Moderation Configuration", color=discord.Color.blurple())
        embed.add_field(name="Status", value="✅ Enabled" if enabled == "true" else "⏹️ Disabled", inline=True)
        embed.add_field(name="Mod Log Channel", value=channel_display, inline=True)
        embed.add_field(name="Sensitivity", value=f"**{sensitivity.capitalize()}**", inline=True)
        embed.add_field(name="Total Flags", value=str(total_flags), inline=True)
        embed.add_field(name="Banned Words", value=str(len(banned_words)), inline=True)
        embed.set_footer(text="SparkSage always flags for human review — never auto-deletes.")
        await interaction.response.send_message(embed=embed)

    @moderation_group.command(name="test", description="Test moderation on a sample message")
    @app_commands.describe(message="The message to test moderation on")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mod_test(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        # Check banned words first
        banned_words = await _get_banned_words(guild_id)
        matched = _check_banned_words(message, banned_words)
        if matched:
            embed = discord.Embed(title="🔍 Moderation Test Result", color=discord.Color.red())
            embed.add_field(name="Flagged", value="Yes ⚠️", inline=True)
            embed.add_field(name="Reason", value=f"Banned word: `{matched}`", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._check_message, message)
            if not result:
                await interaction.followup.send("❌ Could not parse AI response.", ephemeral=True)
                return
            flagged = result.get("flagged", False)
            embed = discord.Embed(
                title="🔍 Moderation Test Result",
                color=discord.Color.red() if flagged else discord.Color.green()
            )
            embed.add_field(name="Flagged", value="Yes ⚠️" if flagged else "No ✅", inline=True)
            embed.add_field(name="Severity", value=result.get("severity") or "N/A", inline=True)
            embed.add_field(name="Reason", value=result.get("reason") or "N/A", inline=False)
            embed.add_field(name="Categories", value=", ".join(result.get("categories", [])) or "None", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    @mod_enable.error
    @mod_disable.error
    @mod_setchannel.error
    @mod_sensitivity.error
    @mod_status.error
    @mod_test.error
    async def mod_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission to use this command.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))