from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import db as database


def _match_score(message: str, keywords: list[str]) -> float:
    """Return a confidence score (0.0 - 1.0) for how well a message matches keywords."""
    message_lower = message.lower()
    matched = sum(1 for kw in keywords if kw.lower() in message_lower)
    return matched / len(keywords) if keywords else 0.0


class FAQ(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Command Group ---

    faq_group = app_commands.Group(name="faq", description="Manage FAQ entries for this server")

    @faq_group.command(name="add", description="Add a new FAQ entry (Admin only)")
    @app_commands.describe(
        question="The frequently asked question",
        answer="The answer to the question",
        keywords="Comma-separated keywords to trigger this FAQ (e.g. 'refund,money back,return')"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def faq_add(
        self,
        interaction: discord.Interaction,
        question: str,
        answer: str,
        keywords: str,
    ):
        guild_id = str(interaction.guild_id)
        created_by = interaction.user.display_name

        faq_id = await database.add_faq(guild_id, question, answer, keywords, created_by)

        embed = discord.Embed(
            title="✅ FAQ Added",
            color=discord.Color.green()
        )
        embed.add_field(name="ID", value=f"`#{faq_id}`", inline=True)
        embed.add_field(name="Keywords", value=f"`{keywords}`", inline=True)
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=answer, inline=False)
        await interaction.response.send_message(embed=embed)

    @faq_group.command(name="list", description="List all FAQ entries for this server")
    async def faq_list(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        faqs = await database.get_faqs(guild_id)

        if not faqs:
            await interaction.response.send_message("No FAQs found for this server. Use `/faq add` to create one.")
            return

        embed = discord.Embed(
            title=f"📋 FAQs for {interaction.guild.name}",
            color=discord.Color.blue()
        )

        for faq in faqs[:10]:  # Discord embed limit
            embed.add_field(
                name=f"#{faq['id']} — {faq['question'][:50]}",
                value=f"**Keywords:** `{faq['match_keywords']}`\n**Used:** {faq['times_used']}x",
                inline=False
            )

        if len(faqs) > 10:
            embed.set_footer(text=f"Showing 10 of {len(faqs)} FAQs")

        await interaction.response.send_message(embed=embed)

    @faq_group.command(name="remove", description="Remove a FAQ entry by ID (Admin only)")
    @app_commands.describe(faq_id="The ID of the FAQ to remove (use /faq list to see IDs)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def faq_remove(self, interaction: discord.Interaction, faq_id: int):
        guild_id = str(interaction.guild_id)
        deleted = await database.delete_faq(guild_id, faq_id)

        if deleted:
            await interaction.response.send_message(f"✅ FAQ `#{faq_id}` has been removed.")
        else:
            await interaction.response.send_message(f"❌ FAQ `#{faq_id}` not found.")

    @faq_group.command(name="view", description="View the full answer for a specific FAQ")
    @app_commands.describe(faq_id="The ID of the FAQ to view")
    async def faq_view(self, interaction: discord.Interaction, faq_id: int):
        guild_id = str(interaction.guild_id)
        faq = await database.get_faq_by_id(guild_id, faq_id)

        if not faq:
            await interaction.response.send_message(f"❌ FAQ `#{faq_id}` not found.")
            return

        embed = discord.Embed(
            title=f"📌 FAQ #{faq['id']}",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Question", value=faq["question"], inline=False)
        embed.add_field(name="Answer", value=faq["answer"], inline=False)
        embed.add_field(name="Keywords", value=f"`{faq['match_keywords']}`", inline=True)
        embed.add_field(name="Times Used", value=str(faq["times_used"]), inline=True)
        embed.set_footer(text=f"Added by {faq['created_by']}")
        await interaction.response.send_message(embed=embed)

    # --- Error Handlers ---

    @faq_add.error
    @faq_remove.error
    async def faq_admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission to use this command.", ephemeral=True
            )

    # --- Auto-Detection in on_message ---

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        # Don't respond to commands
        if message.content.startswith("/"):
            return
        # Don't respond if bot is mentioned (handled by bot.py)
        if self.bot.user in message.mentions:
            return

        guild_id = str(message.guild.id)
        faqs = await database.get_faqs(guild_id)

        if not faqs:
            return

        best_faq = None
        best_score = 0.0
        CONFIDENCE_THRESHOLD = 0.6

        for faq in faqs:
            keywords = [kw.strip() for kw in faq["match_keywords"].split(",") if kw.strip()]
            score = _match_score(message.content, keywords)
            if score > best_score:
                best_score = score
                best_faq = faq

        if best_faq and best_score >= CONFIDENCE_THRESHOLD:
            # Increment usage counter
            await database.increment_faq_usage(best_faq["id"])

            embed = discord.Embed(
                title=f"📌 {best_faq['question']}",
                description=best_faq["answer"],
                color=discord.Color.blurple()
            )
            embed.set_footer(text=f"FAQ #{best_faq['id']} • Use /faq list to see all FAQs")
            await message.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(FAQ(bot))