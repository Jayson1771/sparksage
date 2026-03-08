from fastapi import APIRouter, Depends
from api.deps import get_current_user
import db

router = APIRouter()


@router.get("")
async def list_conversations(user: dict = Depends(get_current_user)):
    channels = await db.list_channels()
    # Convert any non-serializable values
    result = []
    for ch in channels:
        result.append({
            "channel_id": str(ch.get("channel_id", "")),
            "message_count": int(ch.get("message_count", 0)),
            "last_active": str(ch.get("last_active", "")),
        })
    return {"channels": result}


@router.get("/{channel_id}")
async def get_conversation(channel_id: str, user: dict = Depends(get_current_user)):
    messages = await db.get_messages(channel_id, limit=100)
    result = []
    for m in messages:
        result.append({
            "role": str(m.get("role", "")),
            "content": str(m.get("content", "")),
            "provider": str(m.get("provider", "") or ""),
            "created_at": str(m.get("created_at", "")),
        })
    return {"channel_id": channel_id, "messages": result}


@router.delete("/{channel_id}")
async def delete_conversation(channel_id: str, user: dict = Depends(get_current_user)):
    await db.clear_messages(channel_id)
    return {"status": "ok"}