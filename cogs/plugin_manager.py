from __future__ import annotations

import os
import json
import discord
from discord.ext import commands
from discord import app_commands
import db as database

PLUGINS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")


def get_plugin_manifest(plugin_name: str) -> dict | None:
    """Load a plugin's manifest.json."""
    manifest_path = os.path.join(PLUGINS_DIR, plugin_name, "manifest.json")
    if not os.path.exists(manifest_path):
        return None
    try:
        with open(manifest_path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def get_all_plugins() -> list[dict]:
    """Scan the plugins directory and return all found plugin manifests."""
    plugins = []
    if not os.path.exists(PLUGINS_DIR):
        return plugins
    for folder in os.listdir(PLUGINS_DIR):
        folder_path = os.path.join(PLUGINS_DIR, folder)
        if os.path.isdir(folder_path):
            manifest = get_plugin_manifest(folder)
            if manifest:
                manifest["_folder"] = folder
                plugins.append(manifest)
    return plugins


def get_plugin_extension(plugin_name: str) -> str | None:
    """Get the Python extension path for a plugin."""
    manifest = get_plugin_manifest(plugin_name)
    if not manifest:
        return None
    cog_file = manifest.get("cog", "").replace(".py", "")
    return f"plugins.{plugin_name}.{cog_file}"


class PluginManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    plugin_group = app_commands.Group(
        name="plugin",
        description="Manage community plugins (Admin only)"
    )

    @plugin_group.command(name="list", description="List all available plugins")
    async def plugin_list(self, interaction: discord.Interaction):
        plugins = get_all_plugins()
        enabled_plugins = await database.get_enabled_plugins(str(interaction.guild_id))

        if not plugins:
            await interaction.response.send_message(
                f"No plugins found in `plugins/` directory.\n"
                f"Add plugin folders with a `manifest.json` to get started."
            )
            return

        embed = discord.Embed(
            title="🧩 Available Plugins",
            color=discord.Color.blurple()
        )

        for plugin in plugins:
            folder = plugin.get("_folder", "")
            is_enabled = folder in enabled_plugins
            status = "✅ Enabled" if is_enabled else "⏸️ Disabled"

            embed.add_field(
                name=f"{plugin.get('name', folder)} v{plugin.get('version', '?')}",
                value=f"{plugin.get('description', 'No description')}\n"
                      f"By: `{plugin.get('author', 'unknown')}` • {status}",
                inline=False
            )

        embed.set_footer(text=f"{len(plugins)} plugin(s) found • Use /plugin enable <name> to activate")
        await interaction.response.send_message(embed=embed)

    @plugin_group.command(name="enable", description="Enable a plugin for this server")
    @app_commands.describe(plugin_name="The plugin folder name to enable")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def plugin_enable(self, interaction: discord.Interaction, plugin_name: str):
        manifest = get_plugin_manifest(plugin_name)
        if not manifest:
            await interaction.response.send_message(
                f"❌ Plugin `{plugin_name}` not found or missing `manifest.json`.",
                ephemeral=True
            )
            return

        extension = get_plugin_extension(plugin_name)
        if not extension:
            await interaction.response.send_message(
                f"❌ Could not resolve extension path for `{plugin_name}`.",
                ephemeral=True
            )
            return

        # Load the extension if not already loaded
        try:
            if extension not in self.bot.extensions:
                await self.bot.load_extension(extension)
                await self.bot.tree.sync()

            await database.enable_plugin(str(interaction.guild_id), plugin_name)

            embed = discord.Embed(
                title="✅ Plugin Enabled",
                color=discord.Color.green()
            )
            embed.add_field(name="Plugin", value=manifest.get("name", plugin_name), inline=True)
            embed.add_field(name="Version", value=manifest.get("version", "?"), inline=True)
            embed.add_field(name="Author", value=manifest.get("author", "unknown"), inline=True)
            embed.set_footer(text="New commands are now available. Use / to see them.")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to load plugin `{plugin_name}`: {e}", ephemeral=True
            )

    @plugin_group.command(name="disable", description="Disable a plugin for this server")
    @app_commands.describe(plugin_name="The plugin folder name to disable")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def plugin_disable(self, interaction: discord.Interaction, plugin_name: str):
        extension = get_plugin_extension(plugin_name)

        try:
            if extension and extension in self.bot.extensions:
                await self.bot.unload_extension(extension)
                await self.bot.tree.sync()

            await database.disable_plugin(str(interaction.guild_id), plugin_name)
            await interaction.response.send_message(
                f"⏸️ Plugin `{plugin_name}` disabled. Its commands have been removed."
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to disable plugin `{plugin_name}`: {e}", ephemeral=True
            )

    @plugin_group.command(name="reload", description="Reload a plugin without restarting the bot")
    @app_commands.describe(plugin_name="The plugin folder name to reload")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def plugin_reload(self, interaction: discord.Interaction, plugin_name: str):
        extension = get_plugin_extension(plugin_name)
        if not extension:
            await interaction.response.send_message(
                f"❌ Plugin `{plugin_name}` not found.", ephemeral=True
            )
            return

        try:
            if extension in self.bot.extensions:
                await self.bot.reload_extension(extension)
            else:
                await self.bot.load_extension(extension)
            await self.bot.tree.sync()
            await interaction.response.send_message(
                f"🔄 Plugin `{plugin_name}` reloaded successfully."
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to reload plugin `{plugin_name}`: {e}", ephemeral=True
            )

    @plugin_group.command(name="info", description="View details about a specific plugin")
    @app_commands.describe(plugin_name="The plugin folder name to inspect")
    async def plugin_info(self, interaction: discord.Interaction, plugin_name: str):
        manifest = get_plugin_manifest(plugin_name)
        if not manifest:
            await interaction.response.send_message(
                f"❌ Plugin `{plugin_name}` not found.", ephemeral=True
            )
            return

        enabled_plugins = await database.get_enabled_plugins(str(interaction.guild_id))
        is_enabled = plugin_name in enabled_plugins
        extension = get_plugin_extension(plugin_name)
        is_loaded = extension in self.bot.extensions if extension else False

        embed = discord.Embed(
            title=f"🧩 {manifest.get('name', plugin_name)}",
            description=manifest.get("description", "No description"),
            color=discord.Color.blurple()
        )
        embed.add_field(name="Version", value=manifest.get("version", "?"), inline=True)
        embed.add_field(name="Author", value=manifest.get("author", "unknown"), inline=True)
        embed.add_field(name="Cog File", value=f"`{manifest.get('cog', '?')}`", inline=True)
        embed.add_field(name="Status", value="✅ Enabled" if is_enabled else "⏸️ Disabled", inline=True)
        embed.add_field(name="Loaded", value="Yes" if is_loaded else "No", inline=True)

        if manifest.get("commands"):
            embed.add_field(
                name="Commands",
                value="\n".join(f"`/{c}`" for c in manifest["commands"]),
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    # --- Error Handler ---

    @plugin_enable.error
    @plugin_disable.error
    @plugin_reload.error
    async def plugin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(PluginManager(bot))