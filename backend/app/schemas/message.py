import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("content")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank")
        return v
