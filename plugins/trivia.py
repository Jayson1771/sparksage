from __future__ import annotations

import asyncio
import json
import random
import discord
from discord.ext import commands
from discord import app_commands
import providers
import db as database

TRIVIA_PROMPT = """Generate a trivia question. Respond ONLY with a valid JSON object in this format:
{
  "question": "The question text",
  "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
  "answer": "A",
  "explanation": "Brief explanation of the answer",
  "category": "Science / History / Geography / etc"
}

Pick a random category and difficulty. Make it fun and interesting!"""

CATEGORIES = [
    "Science", "History", "Geography", "Pop Culture",
    "Sports", "Technology", "Food & Drink", "Movies & TV"
]


class TriviaView(discord.ui.View):
    def __init__(self, answer: str, explanation: str, user_id: int):
        super().__init__(timeout=30)
        self.answer = answer
        self.explanation = explanation
        self.user_id = user_id
        self.answered = False

    async def _handle_answer(self, interaction: discord.Interaction, chosen: str):
        if self.answered:
            await interaction.response.send_message(
                "This question has already been answered!", ephemeral=True
            )
            return

        self.answered = True
        self.stop()

        is_correct = chosen == self.answer
        # Track score
        await database.update_trivia_score(
            guild_id=str(interaction.guild_id),
            user_id=str(interaction.user.id),
            correct=is_correct
        )

        if is_correct:
            await interaction.response.send_message(
                f"✅ **Correct!** Well done, {interaction.user.mention}!\n"
                f"💡 {self.explanation}"
            )
        else:
            await interaction.response.send_message(
                f"❌ **Wrong!** The correct answer was **{self.answer}**.\n"
                f"💡 {self.explanation}"
            )

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary)
    async def option_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_answer(interaction, "A")

    @discord.ui.button(label="B", style=discord.ButtonStyle.primary)
    async def option_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_answer(interaction, "B")

    @discord.ui.button(label="C", style=discord.ButtonStyle.primary)
    async def option_c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_answer(interaction, "C")

    @discord.ui.button(label="D", style=discord.ButtonStyle.primary)
    async def option_d(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_answer(interaction, "D")

    async def on_timeout(self):
        self.stop()


class Trivia(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="trivia", description="Start a trivia question!")
    @app_commands.describe(category="Optional category to focus on")
    @app_commands.choices(category=[
        app_commands.Choice(name=c, value=c) for c in CATEGORIES
    ])
    async def trivia(self, interaction: discord.Interaction, category: str | None = None):
        await interaction.response.defer()

        try:
            prompt = TRIVIA_PROMPT
            if category:
                prompt += f"\n\nCategory must be: {category}"

            loop = asyncio.get_event_loop()
            response, _ = await loop.run_in_executor(
                None,
                lambda: providers.chat([{"role": "user", "content": "Generate a trivia question"}], prompt)
            )

            # Parse JSON
            text = response.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text.strip())

            question = data["question"]
            options = data["options"]
            answer = data["answer"]
            explanation = data["explanation"]
            cat = data.get("category", category or random.choice(CATEGORIES))

            embed = discord.Embed(
                title=f"🧠 Trivia — {cat}",
                description=f"**{question}**",
                color=discord.Color.gold()
            )
            for option in options:
                embed.add_field(name=option[:option.index(")")+1], value=option[option.index(")")+2:], inline=True)
            embed.set_footer(text="You have 30 seconds to answer!")

            view = TriviaView(answer=answer, explanation=explanation, user_id=interaction.user.id)
            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            print(f"Trivia error: {e}")
            await interaction.followup.send("❌ Failed to generate a trivia question. Try again!")

    @app_commands.command(name="trivia-score", description="Check your trivia score")
    @app_commands.describe(user="User to check (defaults to yourself)")
    async def trivia_score(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        score = await database.get_trivia_score(str(interaction.guild_id), str(target.id))

        total = score["correct"] + score["wrong"]
        accuracy = (score["correct"] / total * 100) if total > 0 else 0

        embed = discord.Embed(
            title=f"🏆 Trivia Score — {target.display_name}",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="✅ Correct", value=str(score["correct"]), inline=True)
        embed.add_field(name="❌ Wrong", value=str(score["wrong"]), inline=True)
        embed.add_field(name="🎯 Accuracy", value=f"{accuracy:.1f}%", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="trivia-leaderboard", description="View the trivia leaderboard")
    async def trivia_leaderboard(self, interaction: discord.Interaction):
        leaders = await database.get_trivia_leaderboard(str(interaction.guild_id))

        if not leaders:
            await interaction.response.send_message("No trivia scores yet! Use `/trivia` to play.")
            return

        embed = discord.Embed(title="🏆 Trivia Leaderboard", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"]

        for i, row in enumerate(leaders[:10]):
            medal = medals[i] if i < 3 else f"#{i+1}"
            total = row["correct"] + row["wrong"]
            accuracy = (row["correct"] / total * 100) if total > 0 else 0
            embed.add_field(
                name=f"{medal} <@{row['user_id']}>",
                value=f"{row['correct']} correct • {accuracy:.0f}% accuracy",
                inline=False
            )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Trivia(bot))