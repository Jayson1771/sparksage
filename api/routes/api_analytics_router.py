"""Analytics API endpoints"""
from __future__ import annotations

from fastapi import APIRouter
import db

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary")
async def get_analytics_summary():
    summary = await db.get_global_analytics_summary()
    return summary


@router.get("/guild/{guild_id}/summary")
async def get_guild_summary(guild_id: str):
    summary = await db.get_analytics_summary(guild_id)
    return summary


@router.get("/guild/{guild_id}/history")
async def get_guild_history(guild_id: str, days: int = 30):
    history = await db.get_analytics_history(guild_id, days=days)
    return {"history": history}


@router.get("/guild/{guild_id}/providers")
async def get_guild_provider_distribution(guild_id: str):
    distribution = await db.get_analytics_provider_distribution(guild_id)
    return {"providers": distribution}


@router.get("/guild/{guild_id}/channels")
async def get_guild_top_channels(guild_id: str, limit: int = 10):
    channels = await db.get_analytics_top_channels(guild_id, limit=limit)
    return {"channels": channels}


@router.get("/history")
async def get_global_history(days: int = 30):
    summary = await db.get_global_analytics_summary()
    return {"history": summary.get("daily_history", [])}


@router.get("/costs/providers")
async def get_cost_by_provider(days: int = 30):
    providers = await db.get_total_cost_by_provider(days=days)
    return {"providers": providers}


@router.get("/costs/daily")
async def get_daily_costs(days: int = 30):
    history = await db.get_cost_summary(days=days)
    return {"history": history}


@router.get("/costs/projection")
async def get_cost_projection():
    projection = await db.get_monthly_projected_cost()
    return projection


@router.get("/costs/alert")
async def get_cost_alert(threshold: float = 10.0):
    alert = await db.get_cost_alert_status(threshold)
    return alert