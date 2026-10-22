from typing import Literal

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthStatusResponse(BaseModel):
    status: Literal["ok"] = "ok"


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    timezone: str
    csrf_token: str
