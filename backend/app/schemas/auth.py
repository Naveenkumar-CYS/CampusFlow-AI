import uuid

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUser(BaseModel):
    """Identity extracted from a verified JWT — returned by GET /auth/me."""

    user_id: uuid.UUID
    email: EmailStr
    role: str
