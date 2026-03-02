from __future__ import annotations

import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import config
import providers
import db as database


TRANSLATION_PROMPT = """You are a professional translator. Translate the given text accurately and naturally.
Preserve the tone, style, and formatting of the original text.
Respond with ONLY the translated text — no explanations, no notes, no preamble."""

LANGUAGE_DETECT_PROMPT = """Detect the language of the following text. 
Respond with ONLY the language name in English (e.g. 'Spanish', 'Japanese', 'French').
Nothing else."""

SUPPORTED_LANGUAGES = [
    ("Afrikaans", "afrikaans"), ("Arabic", "arabic"), ("Bengali", "bengali"),
    ("Bulgarian", "bulgarian"), ("Chinese (Simplified)", "chinese simplified"),
    ("Chinese (Traditional)", "chinese traditional"), ("Croatian", "croatian"),
    ("Czech", "czech"), ("Danish", "danish"), ("Dutch", "dutch"),
    ("English", "english"), ("Filipino", "filipino"), ("Finnish", "finnish"),
    ("French", "french"), ("German", "german"), ("Greek", "greek"),
    ("Hebrew", "hebrew"), ("Hindi", "hindi"), ("Hungarian", "hungarian"),
    ("Indonesian", "indonesian"), ("Italian", "italian"), ("Japanese", "japanese"),
    ("Korean", "korean"), ("Malay", "malay"), ("Norwegian", "norwegian"),
    ("Persian", "persian"), ("Polish", "polish"), ("Portuguese", "portuguese"),
    ("Romanian", "romanian"), ("Russian", "russian"), ("Spanish", "spanish"),
    ("Swedish", "swedish"), ("Thai", "thai"), ("Turkish", "turkish"),
    ("Ukrainian", "ukrainian"), ("Urdu", "urdu"), ("Vietnamese", "vietnamese"),
]

# Language flag emojis for display
LANGUAGE_FLAGS = {
    "english": "🇬🇧", "spanish": "🇪🇸", "french": "🇫🇷", "german": "🇩🇪",
    "japanese": "🇯🇵", "korean": "🇰🇷", "chinese simplified": "🇨🇳",
    "chinese traditional": "🇹🇼", "portuguese": "🇵🇹", "russian": "🇷🇺",
    "arabic": "🇸🇦", "hindi": "🇮🇳", "italian": "🇮🇹", "dutch": "🇳🇱",
    "turkish": "🇹🇷", "polish": "🇵🇱", "vietnamese": "🇻🇳", "thai": "🇹🇭",
    "indonesian": "🇮🇩", "malay": "🇲🇾", "filipino": "🇵🇭", "swedish": "🇸🇪",
    "danish": "🇩🇰", "norwegian": "🇳🇴", "finnish": "🇫🇮", "greek": "🇬🇷",
    "hebrew": "🇮🇱", "ukrainian": "🇺🇦", "czech": "🇨🇿", "romanian": "🇷🇴",
    "hungarian": "🇭🇺", "bulgarian": "🇧🇬", "croatian": "🇭🇷", "persian": "🇮🇷",
    "urdu": "🇵🇰", "bengali": "🇧🇩", "afrikaans": "🇿🇦",
}


class Translate(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Slash Command ---

    @app_commands.command(name="translate", description="Translate text to another language")
    @app_commands.describe(
        text="The text to translate",
        target="The language to translate to",
        source="The source language (optional — auto-detected if omitted)"
    )
    @app_commands.choices(target=[
        app_commands.Choice(name=name, value=value)
        for name, value in SUPPORTED_LANGUAGES[:25]  # Discord limits to 25 choices
    ])
    async def translate(
        self,
        interaction: discord.Interaction,
        text: str,
        target: str,
        source: str | None = None,
    ):
        await interaction.response.defer()
        try:
            detected_source, translation = await self._translate(text, target, source)

            source_flag = LANGUAGE_FLAGS.get(detected_source.lower(), "🌐")
            target_flag = LANGUAGE_FLAGS.get(target.lower(), "🌐")
            target_display = next((n for n, v in SUPPORTED_LANGUAGES if v == target), target.capitalize())

            embed = discord.Embed(color=discord.Color.blurple())
            embed.add_field(
                name=f"{source_flag} Original ({detected_source.capitalize()})",
                value=text[:1000],
                inline=False
            )
            embed.add_field(
                name=f"{target_flag} Translation ({target_display})",
                value=translation[:1000],
                inline=False
            )
            provider_label = config.PROVIDERS.get(config.AI_PROVIDER, {}).get("name", config.AI_PROVIDER)
            embed.set_footer(text=f"Translated by {provider_label} • SparkSage")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"Translation error: {e}")
            await interaction.followup.send("❌ Translation failed. Please try again.")

    @app_commands.command(name="translate-more", description="Translate text to multiple languages at once")
    @app_commands.describe(text="The text to translate")
    async def translate_more(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer()
        try:
            # Translate to top 5 common languages
            targets = ["spanish", "french", "german", "japanese", "portuguese"]
            results = []

            for target in targets:
                _, translation = await self._translate(text, target)
                flag = LANGUAGE_FLAGS.get(target, "🌐")
                target_display = next((n for n, v in SUPPORTED_LANGUAGES if v == target), target.capitalize())
                results.append((flag, target_display, translation))

            embed = discord.Embed(
                title="🌐 Multi-Language Translation",
                color=discord.Color.blurple()
            )
            embed.add_field(name="Original", value=text[:500], inline=False)
            for flag, lang, translation in results:
                embed.add_field(
                    name=f"{flag} {lang}",
                    value=translation[:300],
                    inline=True
                )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Multi-translate error: {e}")
            await interaction.followup.send("❌ Translation failed. Please try again.")

    # --- Context Menu (Right-click on message) ---

    @app_commands.context_menu(name="Translate to English")
    async def translate_to_english(self, interaction: discord.Interaction, message: discord.Message):
        await interaction.response.defer(ephemeral=True)
        if not message.content:
            await interaction.followup.send("❌ This message has no text content.", ephemeral=True)
            return
        try:
            detected_source, translation = await self._translate(message.content, "english")
            source_flag = LANGUAGE_FLAGS.get(detected_source.lower(), "🌐")

            embed = discord.Embed(
                title="🇬🇧 Translated to English",
                color=discord.Color.blurple()
            )
            embed.add_field(
                name=f"{source_flag} Original ({detected_source.capitalize()})",
                value=message.content[:1000],
                inline=False
            )
            embed.add_field(name="🇬🇧 English", value=translation[:1000], inline=False)
            embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Translation failed: {e}", ephemeral=True)

    # --- Auto-Translation ---

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild or not message.content:
            return

        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)

        # Check if this channel has auto-translation enabled
        target_lang = await database.get_auto_translate_channel(guild_id, channel_id)
        if not target_lang:
            return

        try:
            detected_source, translation = await self._translate(message.content, target_lang)

            # Don't translate if already in target language
            if detected_source.lower() == target_lang.lower():
                return

            source_flag = LANGUAGE_FLAGS.get(detected_source.lower(), "🌐")
            target_flag = LANGUAGE_FLAGS.get(target_lang.lower(), "🌐")

            await message.reply(
                f"{source_flag} → {target_flag} *{translation[:500]}*",
                mention_author=False
            )
        except Exception as e:
            print(f"Auto-translate error: {e}")

    # --- Admin Commands ---

    autotranslate_group = app_commands.Group(
        name="autotranslate",
        description="Configure auto-translation for channels (Admin only)"
    )

    @autotranslate_group.command(name="set", description="Auto-translate all messages in a channel")
    @app_commands.describe(
        channel="Channel to enable auto-translation in",
        target="Language to translate messages to"
    )
    @app_commands.choices(target=[
        app_commands.Choice(name=name, value=value)
        for name, value in SUPPORTED_LANGUAGES[:25]
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def autotranslate_set(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        target: str
    ):
        guild_id = str(interaction.guild_id)
        await database.set_auto_translate_channel(guild_id, str(channel.id), target)
        target_display = next((n for n, v in SUPPORTED_LANGUAGES if v == target), target.capitalize())
        flag = LANGUAGE_FLAGS.get(target, "🌐")
        await interaction.response.send_message(
            f"✅ Auto-translation enabled in {channel.mention} → {flag} **{target_display}**"
        )

    @autotranslate_group.command(name="remove", description="Disable auto-translation in a channel")
    @app_commands.describe(channel="Channel to disable auto-translation in")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def autotranslate_remove(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild_id)
        await database.remove_auto_translate_channel(guild_id, str(channel.id))
        await interaction.response.send_message(f"✅ Auto-translation disabled in {channel.mention}")

    @autotranslate_group.command(name="list", description="List all channels with auto-translation")
    async def autotranslate_list(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        channels = await database.get_all_auto_translate_channels(guild_id)

        if not channels:
            await interaction.response.send_message("No channels have auto-translation enabled.")
            return

        embed = discord.Embed(title="🌐 Auto-Translation Channels", color=discord.Color.blurple())
        for channel_id, target_lang in channels.items():
            flag = LANGUAGE_FLAGS.get(target_lang, "🌐")
            target_display = next((n for n, v in SUPPORTED_LANGUAGES if v == target_lang), target_lang.capitalize())
            embed.add_field(name=f"<#{channel_id}>", value=f"{flag} {target_display}", inline=True)
        await interaction.response.send_message(embed=embed)

    @autotranslate_set.error
    @autotranslate_remove.error
    async def autotranslate_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission.", ephemeral=True
            )

    # --- Internal helpers ---

    async def _translate(self, text: str, target: str, source: str | None = None) -> tuple[str, str]:
        """Translate text and return (detected_source_language, translated_text)."""
        loop = asyncio.get_event_loop()

        # Detect source language if not provided
        if not source:
            detect_history = [{"role": "user", "content": text}]
            source = await loop.run_in_executor(
                None,
                lambda: providers.chat(detect_history, LANGUAGE_DETECT_PROMPT)[0].strip()
            )

        target_display = next((n for n, v in SUPPORTED_LANGUAGES if v == target), target.capitalize())
        translate_prompt = f"{TRANSLATION_PROMPT}\n\nTranslate to: {target_display}"
        translate_history = [{"role": "user", "content": text}]

        translation = await loop.run_in_executor(
            None,
            lambda: providers.chat(translate_history, translate_prompt)[0].strip()
        )

        return source, translation


async def setup(bot: commands.Bot):
    await bot.add_cog(Translate(bot))