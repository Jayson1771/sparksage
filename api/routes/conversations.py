from fastapi import APIRouter, Depends
from api.deps import get_current_user
import db

router = APIRouter()


@router.get("")
async def list_conversations(user: dict = Depends(get_current_user)):
    if db.USE_POSTGRES:
        pool = await db.get_pg()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT channel_id, COUNT(*) as message_count, MAX(created_at) as last_active "
                "FROM conversations GROUP BY channel_id ORDER BY last_active DESC"
            )
            channels = [
                {
                    "channel_id": r["channel_id"],
                    "message_count": int(r["message_count"]),
                    "last_active": str(r["last_active"]),
                }
                for r in rows
            ]
    else:
        channels = await db.list_channels()

    return {"channels": channels}


@router.get("/{channel_id}")
async def get_conversation(channel_id: str, user: dict = Depends(get_current_user)):
    if db.USE_POSTGRES:
        pool = await db.get_pg()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT role, content, provider, created_at FROM conversations "
                "WHERE channel_id = $1 ORDER BY id ASC LIMIT 100",
                channel_id
            )
            messages = [
                {
                    "role": r["role"],
                    "content": r["content"],
                    "provider": r["provider"] or "",
                    "created_at": str(r["created_at"]),
                }
                for r in rows
            ]
    else:
        messages = await db.get_messages(channel_id, limit=100)

    return {"channel_id": channel_id, "messages": messages}


@router.delete("/{channel_id}")
async def delete_conversation(channel_id: str, user: dict = Depends(get_current_user)):
    await db.clear_messages(channel_id)
    return {"status": "ok"}