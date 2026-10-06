import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    archived: bool | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self):
        if self.title is None and self.archived is None:
            raise ValueError("provide at least one of: title, archived")
        return self


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class ConversationPage(BaseModel):
    items: list[ConversationOut]
    next_cursor: str | None
