"""Member Analytics API — add to api/main.py"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from api.auth import get_current_user
import db

router = APIRouter(prefix="/api/members", tags=["members"])


@router.get("/{guild_id}/overview")
async def get_overview(guild_id: str, days: int = 30, user=Depends(get_current_user)):
    return await db.get_member_overview(guild_id, days=days)


@router.get("/{guild_id}/history")
async def get_history(guild_id: str, days: int = 30, user=Depends(get_current_user)):
    history = await db.get_member_join_leave_history(guild_id, days=days)
    return {"history": history}


@router.get("/{guild_id}/top")
async def get_top_members(guild_id: str, days: int = 30, limit: int = 10, user=Depends(get_current_user)):
    members = await db.get_top_active_members(guild_id, days=days, limit=limit)
    return {"members": members}


@router.get("/{guild_id}/peak-hours")
async def get_peak_hours(guild_id: str, days: int = 30, user=Depends(get_current_user)):
    hours = await db.get_peak_hours(guild_id, days=days)
    return {"hours": hours}