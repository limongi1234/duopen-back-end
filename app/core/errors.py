"""Observabilidade e handlers globais de exceção.

- X-Request-ID por requisição (header + logs + corpo de erro) para rastreabilidade.
- Respostas JSON limpas e consistentes, sem vazar detalhes internos.
"""

import contextvars
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError

log = logging.getLogger("errors")

# ID da requisição corrente (propagado para todos os logs via record factory).
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def _install_request_id_logging() -> None:
    """Garante que todo LogRecord carregue `request_id` (default '-')."""
    old_factory = logging.getLogRecordFactory()

    def factory(*args: object, **kwargs: object) -> logging.LogRecord:
        record = old_factory(*args, **kwargs)
        record.request_id = request_id_var.get()
        return record

    logging.setLogRecordFactory(factory)


# Instalado no import (antes do basicConfig em main) para o formato poder usar %(request_id)s.
_install_request_id_logging()


# Códigos Postgres/PostgREST -> status HTTP. O que não estiver aqui vira 500.
_PG_CODE_STATUS = {
    "23505": 409,  # unique_violation
    "23503": 409,  # foreign_key_violation
    "23502": 400,  # not_null_violation
    "22P02": 400,  # invalid_text_representation (ex.: UUID malformado)
    "PGRST116": 404,  # nenhuma linha encontrada
}


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def register_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def _request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = rid
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(APIError)
    async def _handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        rid = _request_id(request)
        code = getattr(exc, "code", None)
        status = _PG_CODE_STATUS.get(code or "", 500)
        log.error(
            "Erro Supabase em %s %s: code=%s msg=%s",
            request.method,
            request.url.path,
            code,
            getattr(exc, "message", str(exc)),
        )
        # 5xx não expõe o detalhe do banco; 4xx (erro do cliente) pode esclarecer.
        if status >= 500:
            detail = "Erro ao acessar a base de dados. Tente novamente em instantes."
        else:
            detail = getattr(exc, "message", None) or "Requisição inválida."
        return JSONResponse(
            status_code=status,
            content={"detail": detail, "request_id": rid},
            headers={"X-Request-ID": rid},
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = _request_id(request)
        erros = [
            {
                "campo": ".".join(
                    str(p) for p in e.get("loc", ()) if p not in ("body", "query", "path")
                ),
                "erro": e.get("msg", "valor inválido"),
            }
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"detail": "Dados inválidos na requisição.", "erros": erros, "request_id": rid},
            headers={"X-Request-ID": rid},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        rid = _request_id(request)
        log.exception("Erro não tratado em %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno do servidor.", "request_id": rid},
            headers={"X-Request-ID": rid},
        )
