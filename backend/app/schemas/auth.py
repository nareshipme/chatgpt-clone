import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    # Length over complexity rules (NIST guidance); the upper bound stops absurdly long inputs being hashed.
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    # Demo only: which fictional company to join. A real product would assign this from an invitation or SSO.
    tenant_id: str = Field(default="northwind", min_length=1, max_length=40)

    @field_validator("display_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("display_name must not be blank")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    """Public view of a user. Deliberately has no password_hash field."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    tenant_id: str
    role: str
    persona: str | None = None  # the user's choice; the effective persona is what /personas marks as selected
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
