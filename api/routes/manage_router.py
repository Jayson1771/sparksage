"""Manage routes - keys match exactly what the Discord cogs read/write"""
from __future__ import annotations
import json
import os
from fastapi import APIRouter, Depends, HTTPException
from api.deps import get_current_user
import db

router = APIRouter(prefix="/api/manage", tags=["manage"])
GUILD_ID = os.getenv("DISCORD_GUILD_ID", "1473963014309810350")

async def get_json_config(key: str, default=None):
    val = await db.get_config(key)
    if val is None:
        return default
    try:
        return json.loads(val)
    except Exception:
        return default

async def set_json_config(key: str, value):
    await db.set_config(key, json.dumps(value))

# ── Channel Prompts ───────────────────────────────────────────────────────────
# Cog uses: db.get_all_channel_prompts(guild_id), db.set_channel_prompt(guild_id, channel_id, prompt)

@router.get("/channel-prompts")
async def get_channel_prompts(user=Depends(get_current_user)):
    raw = await db.get_all_channel_prompts(GUILD_ID)
    prompts = [{"channel_id": cid, "channel_name": "", "system_prompt": prompt, "enabled": True}
               for cid, prompt in raw.items()]
    return {"prompts": prompts}

@router.post("/channel-prompts")
async def save_channel_prompt(body: dict, user=Depends(get_current_user)):
    channel_id = body.get("channel_id", "").strip()
    prompt = body.get("system_prompt", "").strip()
    if not channel_id or not prompt:
        raise HTTPException(status_code=400, detail="channel_id and system_prompt required")
    await db.set_channel_prompt(GUILD_ID, channel_id, prompt)
    return {"status": "ok"}

@router.delete("/channel-prompts/{channel_id}")
async def delete_channel_prompt(channel_id: str, user=Depends(get_current_user)):
    await db.delete_channel_prompt(GUILD_ID, channel_id)
    return {"status": "ok"}

# ── Onboarding ────────────────────────────────────────────────────────────────
# Cog uses: WELCOME_ENABLED, WELCOME_CHANNEL_ID, WELCOME_MESSAGE

@router.get("/onboarding")
async def get_onboarding(user=Depends(get_current_user)):
    raw = await db.get_all_onboarding_config(GUILD_ID)
    return {
        "enabled": raw.get("WELCOME_ENABLED", "false") == "true",
        "welcome_channel_id": raw.get("WELCOME_CHANNEL_ID", ""),
        "welcome_message": raw.get("WELCOME_MESSAGE", "Welcome to the server, {user}! 🎉"),
        "dm_enabled": raw.get("DM_ENABLED", "false") == "true",
        "dm_message": raw.get("DM_MESSAGE", ""),
        "roles_to_assign": json.loads(raw.get("AUTO_ROLES", "[]")),
        "steps": json.loads(raw.get("ONBOARDING_STEPS", "[]")),
    }

@router.post("/onboarding")
async def save_onboarding(body: dict, user=Depends(get_current_user)):
    await db.set_onboarding_config(GUILD_ID, "WELCOME_ENABLED", str(body.get("enabled", False)).lower())
    await db.set_onboarding_config(GUILD_ID, "WELCOME_CHANNEL_ID", body.get("welcome_channel_id", ""))
    await db.set_onboarding_config(GUILD_ID, "WELCOME_MESSAGE", body.get("welcome_message", ""))
    await db.set_onboarding_config(GUILD_ID, "DM_ENABLED", str(body.get("dm_enabled", False)).lower())
    await db.set_onboarding_config(GUILD_ID, "DM_MESSAGE", body.get("dm_message", ""))
    await db.set_onboarding_config(GUILD_ID, "AUTO_ROLES", json.dumps(body.get("roles_to_assign", [])))
    await db.set_onboarding_config(GUILD_ID, "ONBOARDING_STEPS", json.dumps(body.get("steps", [])))
    return {"status": "ok"}

# ── Rate Limits ───────────────────────────────────────────────────────────────

@router.get("/rate-limits")
async def get_rate_limits(user=Depends(get_current_user)):
    return await get_json_config("rate_limits_config", {
        "enabled": True, "messages_per_minute": 10, "messages_per_hour": 100,
        "messages_per_day": 500, "cooldown_seconds": 5, "max_tokens_per_message": 2000,
    })

@router.post("/rate-limits")
async def save_rate_limits(body: dict, user=Depends(get_current_user)):
    await set_json_config("rate_limits_config", body)
    return {"status": "ok"}

# ── FAQ ───────────────────────────────────────────────────────────────────────
# Cog uses: db.get_faqs(guild_id), db.add_faq(guild_id, question, answer, keywords, created_by)
# Field: match_keywords (comma-separated keywords string)

@router.get("/faq")
async def get_faq(user=Depends(get_current_user)):
    faqs = await db.get_faqs(GUILD_ID)
    return {"faqs": [dict(f) for f in faqs]}

@router.post("/faq")
async def save_faq_item(body: dict, user=Depends(get_current_user)):
    faq_id = body.get("id")
    question = body.get("question", "").strip()
    answer = body.get("answer", "").strip()
    keywords = body.get("match_keywords", body.get("category", "general"))
    if not question or not answer:
        raise HTTPException(status_code=400, detail="question and answer required")
    if faq_id:
        await db.delete_faq(GUILD_ID, int(faq_id))
    await db.add_faq(GUILD_ID, question, answer, keywords, "dashboard")
    faqs = await db.get_faqs(GUILD_ID)
    return {"faqs": [dict(f) for f in faqs]}

@router.delete("/faq/{faq_id}")
async def delete_faq_item(faq_id: int, user=Depends(get_current_user)):
    deleted = await db.delete_faq(GUILD_ID, faq_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return {"status": "ok"}

# ── Permissions ───────────────────────────────────────────────────────────────
# Cog uses: db.get_all_command_permissions(guild_id), db.add_command_permission, db.remove_command_permission

@router.get("/permissions")
async def get_permissions(user=Depends(get_current_user)):
    command_permissions = await db.get_all_command_permissions(GUILD_ID)
    extra = await get_json_config("permissions_extra_config", {"blocked_users": [], "admin_roles": []})
    return {
        "command_permissions": command_permissions,  # {"ask": ["role_id1"], "review": ["role_id2"]}
        "blocked_users": extra.get("blocked_users", []),
        "admin_roles": extra.get("admin_roles", []),
    }

@router.post("/permissions")
async def save_permissions(body: dict, user=Depends(get_current_user)):
    # Save command permissions
    new_perms = body.get("command_permissions", {})
    current_perms = await db.get_all_command_permissions(GUILD_ID)

    # Clear all removed commands
    for cmd in current_perms:
        if cmd not in new_perms:
            await db.clear_command_permissions(GUILD_ID, cmd)

    # Update each command's roles
    for cmd, role_ids in new_perms.items():
        await db.clear_command_permissions(GUILD_ID, cmd)
        for role_id in role_ids:
            await db.add_command_permission(GUILD_ID, cmd, role_id)

    # Save extra config
    await set_json_config("permissions_extra_config", {
        "blocked_users": body.get("blocked_users", []),
        "admin_roles": body.get("admin_roles", []),
    })
    return {"status": "ok"}

# ── Moderation ────────────────────────────────────────────────────────────────
# Cog uses: MODERATION_ENABLED, MODERATION_SENSITIVITY, MOD_LOG_CHANNEL_ID

@router.get("/moderation")
async def get_moderation(user=Depends(get_current_user)):
    enabled = await db.get_moderation_config(GUILD_ID, "MODERATION_ENABLED") or "false"
    sensitivity = await db.get_moderation_config(GUILD_ID, "MODERATION_SENSITIVITY") or "medium"
    log_channel = await db.get_moderation_config(GUILD_ID, "MOD_LOG_CHANNEL_ID") or ""
    extra = await get_json_config("moderation_extra_config", {
        "filter_profanity": True, "filter_spam": True, "filter_links": False,
        "filter_invites": True, "max_mentions": 5, "max_emojis": 10,
        "warn_before_ban": True, "max_warnings": 3, "mute_duration_minutes": 10,
        "banned_words": [],
    })
    return {
        "auto_mod_enabled": enabled == "true",
        "sensitivity": sensitivity,
        "log_channel_id": log_channel,
        **extra,
    }

@router.post("/moderation")
async def save_moderation(body: dict, user=Depends(get_current_user)):
    # These 3 are read directly by the cog
    await db.set_moderation_config(GUILD_ID, "MODERATION_ENABLED", str(body.get("auto_mod_enabled", False)).lower())
    await db.set_moderation_config(GUILD_ID, "MODERATION_SENSITIVITY", body.get("sensitivity", "medium"))
    await db.set_moderation_config(GUILD_ID, "MOD_LOG_CHANNEL_ID", body.get("log_channel_id", ""))
    # Extra settings stored as JSON
    extra_keys = ["filter_profanity", "filter_spam", "filter_links", "filter_invites",
                  "max_mentions", "max_emojis", "warn_before_ban", "max_warnings",
                  "mute_duration_minutes", "banned_words"]
    await set_json_config("moderation_extra_config", {k: body[k] for k in extra_keys if k in body})
    return {"status": "ok"}

# ── Plugins ───────────────────────────────────────────────────────────────────
# Reads real plugin manifests from plugins/ directory, same as plugin_manager cog

import pathlib

def _get_all_plugins() -> list[dict]:
    plugins_dir = pathlib.Path(__file__).parent.parent.parent / "plugins"
    plugins = []
    if not plugins_dir.exists():
        return plugins
    for folder in plugins_dir.iterdir():
        if folder.is_dir():
            manifest_path = folder / "manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                        manifest["_folder"] = folder.name
                        plugins.append(manifest)
                except Exception:
                    pass
    return plugins

@router.get("/plugins")
async def get_plugins(user=Depends(get_current_user)):
    plugins = _get_all_plugins()
    enabled = list(await db.get_enabled_plugins(GUILD_ID))
    for p in plugins:
        p["enabled"] = p["_folder"] in enabled
    return {"plugins": plugins, "enabled": enabled}

@router.post("/plugins/{plugin_name}/enable")
async def enable_plugin(plugin_name: str, user=Depends(get_current_user)):
    await db.enable_plugin(GUILD_ID, plugin_name)
    return {"status": "ok"}

@router.post("/plugins/{plugin_name}/disable")
async def disable_plugin(plugin_name: str, user=Depends(get_current_user)):
    await db.disable_plugin(GUILD_ID, plugin_name)
    return {"status": "ok"}

# ── Daily Digest ──────────────────────────────────────────────────────────────
# Cog uses: DIGEST_ENABLED, DIGEST_CHANNEL_ID, DIGEST_TIME via db.set_digest_config

@router.get("/daily-digest")
async def get_daily_digest(user=Depends(get_current_user)):
    enabled = await db.get_digest_config(GUILD_ID, "DIGEST_ENABLED") or "false"
    channel_id = await db.get_digest_config(GUILD_ID, "DIGEST_CHANNEL_ID") or ""
    send_time = await db.get_digest_config(GUILD_ID, "DIGEST_TIME") or "09:00"
    return {
        "enabled": enabled == "true",
        "channel_id": channel_id,
        "send_time": send_time,
    }

@router.post("/daily-digest")
async def save_daily_digest(body: dict, user=Depends(get_current_user)):
    await db.set_digest_config(GUILD_ID, "DIGEST_ENABLED", str(body.get("enabled", False)).lower())
    await db.set_digest_config(GUILD_ID, "DIGEST_CHANNEL_ID", body.get("channel_id", ""))
    await db.set_digest_config(GUILD_ID, "DIGEST_TIME", body.get("send_time", "09:00"))
    return {"status": "ok"}