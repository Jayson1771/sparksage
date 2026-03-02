from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import db as database
from utils.cost_calculator import format_cost, get_provider_pricing_display, PROVIDER_PRICING

try:
    import config
    THRESHOLD = getattr(config, "COST_ALERT_THRESHOLD", 10.0)
except Exception:
    THRESHOLD = 10.0


class CostTracking(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    cost_group = app_commands.Group(
        name="cost",
        description="View AI provider usage costs (Admin only)"
    )

    @cost_group.command(name="summary", description="View cost summary for the last 30 days")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cost_summary(self, interaction: discord.Interaction):
        await interaction.response.defer()

        by_provider = await database.get_total_cost_by_provider(days=30)
        projection = await database.get_monthly_projected_cost()
        alert = await database.get_cost_alert_status(THRESHOLD)

        embed = discord.Embed(
            title="💰 Cost Summary — Last 30 Days",
            color=discord.Color.gold()
        )

        if not by_provider:
            embed.description = "No cost data yet. Start using the bot to track spending."
        else:
            for row in by_provider:
                provider = row["provider"]
                cost = row["total_cost"] or 0.0
                requests = row["total_requests"]
                input_t = row["total_input_tokens"] or 0
                output_t = row["total_output_tokens"] or 0
                embed.add_field(
                    name=f"`{provider}`",
                    value=f"**{format_cost(cost)}**\n"
                          f"{requests} requests\n"
                          f"{input_t:,} in / {output_t:,} out tokens",
                    inline=True
                )

        # Projection section
        embed.add_field(
            name="📈 Projection",
            value=f"Daily avg: **{format_cost(projection['daily_avg_cost'])}**\n"
                  f"Projected monthly: **{format_cost(projection['projected_monthly'])}**\n"
                  f"Avg requests/day: {projection['daily_avg_requests']:.0f}",
            inline=False
        )

        # Alert status
        status_emoji = "🔴" if alert["exceeded"] else "🟠" if alert["warning"] else "🟢"
        embed.add_field(
            name=f"{status_emoji} This Month",
            value=f"Spent: **{format_cost(alert['month_cost'])}** / {format_cost(THRESHOLD)} threshold\n"
                  f"{alert['percentage']:.0f}% of budget used",
            inline=False
        )

        embed.set_footer(text="Costs are estimates based on token counts • Free providers show $0")
        await interaction.followup.send(embed=embed)

    @cost_group.command(name="pricing", description="View current provider pricing rates")
    async def cost_pricing(self, interaction: discord.Interaction):
        pricing = get_provider_pricing_display()

        embed = discord.Embed(
            title="💰 Provider Pricing (per 1M tokens)",
            color=discord.Color.gold()
        )

        for p in pricing:
            if p["free"]:
                value = "✅ **Free**"
            else:
                value = (
                    f"Input: **${p['input_per_1m']:.2f}**\n"
                    f"Output: **${p['output_per_1m']:.2f}**"
                )
            embed.add_field(name=f"`{p['provider']}`", value=value, inline=True)

        embed.set_footer(text="Tip: Use free providers (Gemini, Groq, OpenRouter) to minimize costs.")
        await interaction.response.send_message(embed=embed)

    @cost_group.command(name="setalert", description="Set a monthly cost alert threshold in USD")
    @app_commands.describe(threshold="Alert when monthly cost exceeds this amount in USD")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cost_setalert(self, interaction: discord.Interaction, threshold: float):
        global THRESHOLD
        THRESHOLD = threshold
        await database.set_config("COST_ALERT_THRESHOLD", str(threshold))
        await interaction.response.send_message(
            f"✅ Cost alert set. You'll be warned when monthly spend exceeds **${threshold:.2f}**."
        )

    @cost_group.command(name="history", description="View daily cost breakdown for the last 30 days")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cost_history(self, interaction: discord.Interaction):
        await interaction.response.defer()
        rows = await database.get_cost_summary(days=30)

        if not rows:
            await interaction.followup.send("No cost history yet.")
            return

        # Group by date and sum costs
        from collections import defaultdict
        by_date: dict[str, float] = defaultdict(float)
        for row in rows:
            by_date[row["date"]] += row["daily_cost"] or 0.0

        # Build a simple text table of the last 14 days
        sorted_dates = sorted(by_date.items())[-14:]
        lines = ["```", f"{'Date':<12} {'Cost':>10}", "-" * 24]
        for date, cost in sorted_dates:
            lines.append(f"{date:<12} {format_cost(cost):>10}")
        lines.append("```")

        embed = discord.Embed(
            title="📅 Daily Cost History (Last 14 Days)",
            description="\n".join(lines),
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed)

    # --- Error Handler ---

    @cost_summary.error
    @cost_setalert.error
    @cost_history.error
    async def cost_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(CostTracking(bot))