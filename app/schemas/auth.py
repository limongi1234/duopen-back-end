from typing import Literal, Optional

from pydantic import BaseModel, EmailStr

Perfil = Literal["admin", "gestor", "readonly"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nome: str
    # ⚠️ Aceitar perfil no cadastro permite auto-atribuição (escalonamento).
    # Validado contra os valores permitidos; default = menor privilégio.
    perfil: Perfil = "readonly"


class UserResponse(BaseModel):
    id: str
    email: str
    nome: str
    perfil: Optional[str] = None
