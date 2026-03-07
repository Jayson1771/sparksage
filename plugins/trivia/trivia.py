from __future__ import annotations

import random
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import db as database

TRIVIA_QUESTIONS = [
    {"q": "What is the capital of France?", "a": "paris", "choices": ["London", "Berlin", "Paris", "Madrid"]},
    {"q": "How many sides does a hexagon have?", "a": "6", "choices": ["5", "6", "7", "8"]},
    {"q": "What planet is known as the Red Planet?", "a": "mars", "choices": ["Venus", "Mars", "Jupiter", "Saturn"]},
    {"q": "Who wrote 'Romeo and Juliet'?", "a": "shakespeare", "choices": ["Dickens", "Shakespeare", "Hemingway", "Poe"]},
    {"q": "What is the chemical symbol for water?", "a": "h2o", "choices": ["H2O", "CO2", "O2", "NaCl"]},
    {"q": "What is the largest ocean on Earth?", "a": "pacific", "choices": ["Atlantic", "Indian", "Pacific", "Arctic"]},
    {"q": "How many colors are in a rainbow?", "a": "7", "choices": ["5", "6", "7", "8"]},
    {"q": "What is 12 x 12?", "a": "144", "choices": ["124", "132", "144", "156"]},
    {"q": "Which element has the symbol 'O'?", "a": "oxygen", "choices": ["Gold", "Osmium", "Oxygen", "Oganesson"]},
    {"q": "What year did World War II end?", "a": "1945", "choices": ["1943", "1944", "1945", "1946"]},
]

class Trivia(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._active: dict[int, dict] = {}  # channel_id -> question state

    @app_commands.command(name="trivia", description="Start a trivia question!")
    async def trivia(self, interaction: discord.Interaction):
        if interaction.channel_id in self._active:
            await interaction.response.send_message("⏳ A trivia question is already active in this channel!", ephemeral=True)
            return

        q = random.choice(TRIVIA_QUESTIONS)
        self._active[interaction.channel_id] = {
            "answer": q["a"],
            "user_id": str(interaction.user.id),
        }

        choices_text = "\n".join(f"{chr(65+i)}) {c}" for i, c in enumerate(q["choices"]))
        embed = discord.Embed(
            title="🎯 Trivia Time!",
            description=f"**{q['q']}**\n\n{choices_text}",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Type your answer (A, B, C, or D) within 30 seconds!")
        await interaction.response.send_message(embed=embed)

        # Auto-expire after 30 seconds
        await asyncio.sleep(30)
        if interaction.channel_id in self._active:
            del self._active[interaction.channel_id]
            await interaction.channel.send(f"⏰ Time's up! The answer was **{q['a'].capitalize()}**.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.channel.id not in self._active:
            return

        state = self._active[message.channel.id]
        answer = message.content.strip().lower()

        # Accept letter (A/B/C/D) or the actual answer text
        q_data = next((q for q in TRIVIA_QUESTIONS if q["a"] == state["answer"]), None)
        correct = False

        if q_data:
            letter_map = {chr(65+i).lower(): c.lower() for i, c in enumerate(q_data["choices"])}
            if answer in letter_map:
                correct = letter_map[answer] == state["answer"]
            else:
                correct = answer == state["answer"]

        if correct:
            del self._active[message.channel.id]
            guild_id = str(message.guild.id) if message.guild else "dm"
            await database.execute(
                "INSERT INTO trivia_scores (guild_id, user_id, correct) VALUES (?, ?, 1) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET correct = correct + 1",
                (guild_id, str(message.author.id))
            )
            await message.channel.send(f"✅ Correct! Well done {message.author.mention}! 🎉")

    @app_commands.command(name="trivia-score", description="Check your trivia score")
    async def trivia_score(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id) if interaction.guild_id else "dm"
        row = await database.execute(
            "SELECT correct FROM trivia_scores WHERE guild_id = ? AND user_id = ?",
            (guild_id, str(interaction.user.id)), fetch="one"
        )
        score = row["correct"] if row else 0
        await interaction.response.send_message(f"🏆 {interaction.user.mention} has **{score}** correct trivia answers!")

    @app_commands.command(name="trivia-leaderboard", description="Show the trivia leaderboard")
    async def trivia_leaderboard(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id) if interaction.guild_id else "dm"
        rows = await database.execute(
            "SELECT user_id, correct FROM trivia_scores WHERE guild_id = ? ORDER BY correct DESC LIMIT 10",
            (guild_id,), fetch="all"
        ) or []

        if not rows:
            await interaction.response.send_message("No trivia scores yet! Use `/trivia` to start.")
            return

        embed = discord.Embed(title="🏆 Trivia Leaderboard", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, row in enumerate(rows):
            medal = medals[i] if i < 3 else f"{i+1}."
            member = interaction.guild.get_member(int(row["user_id"])) if interaction.guild else None
            name = member.display_name if member else f"User {row['user_id']}"
            lines.append(f"{medal} **{name}** — {row['correct']} correct")
        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Trivia(bot))