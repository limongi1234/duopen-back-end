from typing import Any
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client
from app.core.database import get_supabase_client
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, UserCreate, UserResponse

router = APIRouter()
bearer = HTTPBearer()
log = logging.getLogger(__name__)


def _format_supabase_error(error: Any) -> str:
    message = getattr(error, "message", None) or getattr(error, "details", None)
    return message or str(error)


def _ensure_ok(result: Any, action: str) -> Any:
    error = getattr(result, "error", None)
    if error:
        detail = _format_supabase_error(error)
        log.error("Supabase error during %s: %s", action, detail)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao acessar base de dados: {detail}",
        )
    return result


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: Client = Depends(get_supabase_client)):
    existing = _ensure_ok(
        db.table("usuarios").select("id").eq("email", body.email).execute(),
        "check existing email",
    )
    if existing.data:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    result = _ensure_ok(
        db.table("usuarios").insert({
            "email": body.email,
            "senha_hash": hash_password(body.password),
            "nome": body.nome,
        }).execute(),
        "insert user",
    )
    if result.data:
        user: dict[str, Any] = result.data[0]  # type: ignore[assignment]
    else:
        created = _ensure_ok(
            db.table("usuarios").select("id,email,nome").eq("email", body.email).execute(),
            "fetch created user",
        )
        if not created.data:
            raise HTTPException(status_code=500, detail="Erro ao criar usuário")
        user = created.data[0]  # type: ignore[assignment]
    return UserResponse(id=user["id"], email=user["email"], nome=user["nome"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: Client = Depends(get_supabase_client)):
    result = _ensure_ok(
        db.table("usuarios").select("*").eq("email", body.email).execute(),
        "fetch user",
    )
    if not result.data:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    user: dict[str, Any] = result.data[0]  # type: ignore[assignment]
    if not verify_password(body.password, str(user["senha_hash"])):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    payload = {"sub": user["id"], "email": user["email"]}
    return TokenResponse(
        access_token=create_access_token(payload),
        refresh_token=create_refresh_token(payload),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    try:
        payload = decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Refresh token inválido")
    data = {"sub": payload["sub"], "email": payload["email"]}
    return TokenResponse(
        access_token=create_access_token(data),
        refresh_token=create_refresh_token(data),
    )


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        return decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")


@router.get("/me", response_model=UserResponse)
async def me(
    db: Client = Depends(get_supabase_client),
    user: dict = Depends(get_current_user),
):
    result = _ensure_ok(
        db.table("usuarios").select("id,email,nome").eq("id", user["sub"]).execute(),
        "fetch current user",
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    row: dict[str, Any] = result.data[0]  # type: ignore[assignment]
    return UserResponse(id=row["id"], email=row["email"], nome=row["nome"])
