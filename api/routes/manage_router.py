"""Manage routes - keys match exactly what the Discord cogs read/write"""
from __future__ import annotations
import json
import os
import pathlib
from fastapi import APIRouter, Depends, HTTPException
from api.deps import get_current_user
import db

router = APIRouter(prefix="/api/manage", tags=["manage"])

def get_guild_id() -> str:
    """Always read DISCORD_GUILD_ID fresh from env so Railway env vars work."""
    guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
    if not guild_id:
        guild_id = "1473963014309810350"  # fallback
    return guild_id

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

# ── Debug endpoint ────────────────────────────────────────────────────────────
@router.get("/debug/guild")
async def debug_guild(user=Depends(get_current_user)):
    """Check what guild ID the dashboard is using vs what's in DB."""
    guild_id = get_guild_id()
    mod_enabled = await db.get_moderation_config(guild_id, "MODERATION_ENABLED")
    welcome_enabled = await db.get_onboarding_config(guild_id, "WELCOME_ENABLED")
    perms = await db.get_all_command_permissions(guild_id)
    return {
        "dashboard_guild_id": guild_id,
        "env_DISCORD_GUILD_ID": os.getenv("DISCORD_GUILD_ID", "NOT SET"),
        "moderation_enabled_in_db": mod_enabled,
        "welcome_enabled_in_db": welcome_enabled,
        "command_permissions": perms,
        "hint": "dashboard_guild_id must match your Discord server ID exactly",
    }

# ── Channel Prompts ───────────────────────────────────────────────────────────
@router.get("/channel-prompts")
async def get_channel_prompts(user=Depends(get_current_user)):
    guild_id = get_guild_id()
    raw = await db.get_all_channel_prompts(guild_id)
    prompts = [{"channel_id": cid, "channel_name": "", "system_prompt": prompt, "enabled": True}
               for cid, prompt in raw.items()]
    return {"prompts": prompts}

@router.post("/channel-prompts")
async def save_channel_prompt(body: dict, user=Depends(get_current_user)):
    guild_id = get_guild_id()
    channel_id = body.get("channel_id", "").strip()
    prompt = body.get("system_prompt", "").strip()
    if not channel_id or not prompt:
        raise HTTPException(status_code=400, detail="channel_id and system_prompt required")
    await db.set_channel_prompt(guild_id, channel_id, prompt)
    return {"status": "ok"}

@router.delete("/channel-prompts/{channel_id}")
async def delete_channel_prompt(channel_id: str, user=Depends(get_current_user)):
    guild_id = get_guild_id()
    await db.delete_channel_prompt(guild_id, channel_id)
    return {"status": "ok"}

# ── Onboarding ────────────────────────────────────────────────────────────────
@router.get("/onboarding")
async def get_onboarding(user=Depends(get_current_user)):
    guild_id = get_guild_id()
    raw = await db.get_all_onboarding_config(guild_id)
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
    guild_id = get_guild_id()
    await db.set_onboarding_config(guild_id, "WELCOME_ENABLED", str(body.get("enabled", False)).lower())
    await db.set_onboarding_config(guild_id, "WELCOME_CHANNEL_ID", body.get("welcome_channel_id", ""))
    await db.set_onboarding_config(guild_id, "WELCOME_MESSAGE", body.get("welcome_message", ""))
    await db.set_onboarding_config(guild_id, "DM_ENABLED", str(body.get("dm_enabled", False)).lower())
    await db.set_onboarding_config(guild_id, "DM_MESSAGE", body.get("dm_message", ""))
    await db.set_onboarding_config(guild_id, "AUTO_ROLES", json.dumps(body.get("roles_to_assign", [])))
    await db.set_onboarding_config(guild_id, "ONBOARDING_STEPS", json.dumps(body.get("steps", [])))
    return {"status": "ok", "guild_id": guild_id}

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
@router.get("/faq")
async def get_faq(user=Depends(get_current_user)):
    guild_id = get_guild_id()
    faqs = await db.get_faqs(guild_id)
    return {"faqs": [dict(f) for f in faqs]}

@router.post("/faq")
async def save_faq_item(body: dict, user=Depends(get_current_user)):
    guild_id = get_guild_id()
    faq_id = body.get("id")
    question = body.get("question", "").strip()
    answer = body.get("answer", "").strip()
    keywords = body.get("match_keywords", body.get("category", "general"))
    if not question or not answer:
        raise HTTPException(status_code=400, detail="question and answer required")
    if faq_id:
        await db.delete_faq(guild_id, int(faq_id))
    await db.add_faq(guild_id, question, answer, keywords, "dashboard")
    faqs = await db.get_faqs(guild_id)
    return {"faqs": [dict(f) for f in faqs]}

@router.delete("/faq/{faq_id}")
async def delete_faq_item(faq_id: int, user=Depends(get_current_user)):
    guild_id = get_guild_id()
    deleted = await db.delete_faq(guild_id, faq_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return {"status": "ok"}

# ── Permissions ───────────────────────────────────────────────────────────────
@router.get("/permissions")
async def get_permissions(user=Depends(get_current_user)):
    guild_id = get_guild_id()
    command_permissions = await db.get_all_command_permissions(guild_id)
    extra = await get_json_config("permissions_extra_config", {"blocked_users": [], "admin_roles": []})
    return {
        "command_permissions": command_permissions,
        "blocked_users": extra.get("blocked_users", []),
        "admin_roles": extra.get("admin_roles", []),
    }

@router.post("/permissions")
async def save_permissions(body: dict, user=Depends(get_current_user)):
    guild_id = get_guild_id()
    new_perms = body.get("command_permissions", {})
    current_perms = await db.get_all_command_permissions(guild_id)
    for cmd in current_perms:
        if cmd not in new_perms:
            await db.clear_command_permissions(guild_id, cmd)
    for cmd, role_ids in new_perms.items():
        await db.clear_command_permissions(guild_id, cmd)
        for role_id in role_ids:
            await db.add_command_permission(guild_id, cmd, role_id)
    await set_json_config("permissions_extra_config", {
        "blocked_users": body.get("blocked_users", []),
        "admin_roles": body.get("admin_roles", []),
    })
    return {"status": "ok", "guild_id": guild_id}

# ── Moderation ────────────────────────────────────────────────────────────────
@router.get("/moderation")
async def get_moderation(user=Depends(get_current_user)):
    guild_id = get_guild_id()
    enabled = await db.get_moderation_config(guild_id, "MODERATION_ENABLED") or "false"
    sensitivity = await db.get_moderation_config(guild_id, "MODERATION_SENSITIVITY") or "medium"
    log_channel = await db.get_moderation_config(guild_id, "MOD_LOG_CHANNEL_ID") or ""
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
    guild_id = get_guild_id()
    await db.set_moderation_config(guild_id, "MODERATION_ENABLED", str(body.get("auto_mod_enabled", False)).lower())
    await db.set_moderation_config(guild_id, "MODERATION_SENSITIVITY", body.get("sensitivity", "medium"))
    await db.set_moderation_config(guild_id, "MOD_LOG_CHANNEL_ID", body.get("log_channel_id", ""))
    extra_keys = ["filter_profanity", "filter_spam", "filter_links", "filter_invites",
                  "max_mentions", "max_emojis", "warn_before_ban", "max_warnings",
                  "mute_duration_minutes", "banned_words"]
    await set_json_config("moderation_extra_config", {k: body[k] for k in extra_keys if k in body})
    return {"status": "ok", "guild_id": guild_id}

# ── Plugins ───────────────────────────────────────────────────────────────────
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
    guild_id = get_guild_id()
    plugins = _get_all_plugins()
    enabled = list(await db.get_enabled_plugins(guild_id))
    for p in plugins:
        p["enabled"] = p["_folder"] in enabled
    return {"plugins": plugins, "enabled": enabled}

@router.post("/plugins/{plugin_name}/enable")
async def enable_plugin(plugin_name: str, user=Depends(get_current_user)):
    guild_id = get_guild_id()
    await db.enable_plugin(guild_id, plugin_name)
    return {"status": "ok"}

@router.post("/plugins/{plugin_name}/disable")
async def disable_plugin(plugin_name: str, user=Depends(get_current_user)):
    guild_id = get_guild_id()
    await db.disable_plugin(guild_id, plugin_name)
    return {"status": "ok"}

# ── Daily Digest ──────────────────────────────────────────────────────────────
@router.get("/daily-digest")
async def get_daily_digest(user=Depends(get_current_user)):
    guild_id = get_guild_id()
    enabled = await db.get_digest_config(guild_id, "DIGEST_ENABLED") or "false"
    channel_id = await db.get_digest_config(guild_id, "DIGEST_CHANNEL_ID") or ""
    send_time = await db.get_digest_config(guild_id, "DIGEST_TIME") or "09:00"
    return {
        "enabled": enabled == "true",
        "channel_id": channel_id,
        "send_time": send_time,
    }

@router.post("/daily-digest")
async def save_daily_digest(body: dict, user=Depends(get_current_user)):
    guild_id = get_guild_id()
    await db.set_digest_config(guild_id, "DIGEST_ENABLED", str(body.get("enabled", False)).lower())
    await db.set_digest_config(guild_id, "DIGEST_CHANNEL_ID", body.get("channel_id", ""))
    await db.set_digest_config(guild_id, "DIGEST_TIME", body.get("send_time", "09:00"))
    return {"status": "ok"}

# ── Member Analytics ──────────────────────────────────────────────────────────
@router.get("/member-analytics/overview")
async def get_member_analytics_overview(days: int = 30, user=Depends(get_current_user)):
    guild_id = get_guild_id()
    overview = await db.get_member_overview(guild_id, days)
    return overview

@router.get("/member-analytics/history")
async def get_member_analytics_history(days: int = 30, user=Depends(get_current_user)):
    guild_id = get_guild_id()
    history = await db.get_member_join_leave_history(guild_id, days)
    return {"history": [dict(r) for r in history]}

@router.get("/member-analytics/top-members")
async def get_top_members(days: int = 30, limit: int = 10, user=Depends(get_current_user)):
    guild_id = get_guild_id()
    members = await db.get_top_active_members(guild_id, days, limit)
    return {"members": [dict(r) for r in members]}

@router.get("/member-analytics/peak-hours")
async def get_peak_hours(days: int = 30, user=Depends(get_current_user)):
    guild_id = get_guild_id()
    hours = await db.get_peak_hours(guild_id, days)
    return {"peak_hours": hours}

@router.get("/member-analytics")
async def get_member_analytics(days: int = 30, user=Depends(get_current_user)):
    """Combined endpoint - all member analytics in one call."""
    guild_id = get_guild_id()
    overview = await db.get_member_overview(guild_id, days)
    history = await db.get_member_join_leave_history(guild_id, days)
    top_members = await db.get_top_active_members(guild_id, days, 10)
    peak_hours = await db.get_peak_hours(guild_id, days)
    return {
        "guild_id": guild_id,
        "days": days,
        "overview": overview,
        "history": [dict(r) for r in history],
        "top_members": [dict(r) for r in top_members],
        "peak_hours": peak_hours,
    }