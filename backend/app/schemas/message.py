import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    # Typed parts, e.g. [{"type": "text", "text": "..."}]. Other part types arrive in later slices.
    parts: list[dict[str, Any]]
    status: str
    created_at: datetime


class MessageList(BaseModel):
    items: list[MessageOut]
