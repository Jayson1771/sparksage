from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import db as database


async def check_command_permission(interaction: discord.Interaction, command_name: str) -> bool:
    """Check if the user has permission to run a command based on role restrictions."""
    guild_id = str(interaction.guild_id)
    required_roles = await database.get_command_permissions(guild_id, command_name)

    # No restrictions set — everyone can use it
    if not required_roles:
        return True

    # Check if user has any of the required roles
    user_role_ids = {str(role.id) for role in interaction.user.roles}
    return bool(user_role_ids & set(required_roles))


def require_permission():
    """Decorator that checks role-based permissions before running a command."""
    async def predicate(interaction: discord.Interaction) -> bool:
        command_name = interaction.command.name if interaction.command else None
        if not command_name:
            return True

        allowed = await check_command_permission(interaction, command_name)
        if not allowed:
            guild_id = str(interaction.guild_id)
            required_roles = await database.get_command_permissions(guild_id, command_name)
            role_mentions = [f"<@&{r}>" for r in required_roles]
            await interaction.response.send_message(
                f"❌ You need one of these roles to use `/{command_name}`: {', '.join(role_mentions)}",
                ephemeral=True
            )
            return False
        return True

    return app_commands.check(predicate)


class Permissions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    permissions_group = app_commands.Group(
        name="permissions",
        description="Manage command permissions (Admin only)"
    )

    @permissions_group.command(name="set", description="Restrict a command to a specific role")
    @app_commands.describe(
        command="The command name to restrict (e.g. 'ask', 'review', 'summarize')",
        role="The role required to use this command"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def permissions_set(
        self,
        interaction: discord.Interaction,
        command: str,
        role: discord.Role,
    ):
        guild_id = str(interaction.guild_id)

        # Validate command exists
        valid_commands = [cmd.name for cmd in self.bot.tree.get_commands()]
        if command not in valid_commands:
            await interaction.response.send_message(
                f"❌ Unknown command `/{command}`. Available commands: {', '.join(f'`{c}`' for c in sorted(valid_commands))}",
                ephemeral=True
            )
            return

        await database.add_command_permission(guild_id, command, str(role.id))

        embed = discord.Embed(
            title="🔒 Permission Set",
            color=discord.Color.orange()
        )
        embed.add_field(name="Command", value=f"`/{command}`", inline=True)
        embed.add_field(name="Required Role", value=role.mention, inline=True)
        embed.set_footer(text="Users without this role will be denied access.")
        await interaction.response.send_message(embed=embed)

    @permissions_group.command(name="remove", description="Remove a role restriction from a command")
    @app_commands.describe(
        command="The command name to update",
        role="The role to remove from the restriction"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def permissions_remove(
        self,
        interaction: discord.Interaction,
        command: str,
        role: discord.Role,
    ):
        guild_id = str(interaction.guild_id)
        deleted = await database.remove_command_permission(guild_id, command, str(role.id))

        if deleted:
            await interaction.response.send_message(
                f"✅ Removed {role.mention} restriction from `/{command}`."
            )
        else:
            await interaction.response.send_message(
                f"❌ No restriction found for `/{command}` with role {role.mention}.",
                ephemeral=True
            )

    @permissions_group.command(name="clear", description="Remove ALL role restrictions from a command")
    @app_commands.describe(command="The command name to clear all restrictions from")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def permissions_clear(self, interaction: discord.Interaction, command: str):
        guild_id = str(interaction.guild_id)
        await database.clear_command_permissions(guild_id, command)
        await interaction.response.send_message(
            f"✅ All role restrictions removed from `/{command}`. Everyone can use it now."
        )

    @permissions_group.command(name="list", description="Show all command restrictions for this server")
    async def permissions_list(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        all_permissions = await database.get_all_command_permissions(guild_id)

        if not all_permissions:
            await interaction.response.send_message(
                "No command restrictions set. All commands are available to everyone.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🔒 Command Permissions — {interaction.guild.name}",
            color=discord.Color.orange()
        )

        for command_name, role_ids in all_permissions.items():
            role_mentions = []
            for role_id in role_ids:
                role = interaction.guild.get_role(int(role_id))
                role_mentions.append(role.mention if role else f"*(deleted role {role_id})*")

            embed.add_field(
                name=f"/{command_name}",
                value="\n".join(role_mentions) or "*(no restrictions)*",
                inline=False
            )

        embed.set_footer(text="Commands not listed are unrestricted.")
        await interaction.response.send_message(embed=embed)

    @permissions_group.command(name="check", description="Check who can use a specific command")
    @app_commands.describe(command="The command to check permissions for")
    async def permissions_check(self, interaction: discord.Interaction, command: str):
        guild_id = str(interaction.guild_id)
        role_ids = await database.get_command_permissions(guild_id, command)

        embed = discord.Embed(
            title=f"🔍 Permissions for /{command}",
            color=discord.Color.blurple()
        )

        if not role_ids:
            embed.description = "✅ No restrictions — everyone can use this command."
        else:
            role_mentions = []
            for role_id in role_ids:
                role = interaction.guild.get_role(int(role_id))
                role_mentions.append(role.mention if role else f"*(deleted role {role_id})*")
            embed.add_field(name="Required Roles (any one of)", value="\n".join(role_mentions), inline=False)
            embed.set_footer(text="Users need at least one of these roles.")

        await interaction.response.send_message(embed=embed)

    # --- Error Handler ---

    @permissions_set.error
    @permissions_remove.error
    @permissions_clear.error
    async def permissions_admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission to use this command.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Permissions(bot))