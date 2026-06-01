"""Handlers globais de exceção — respostas JSON limpas, sem vazar detalhes internos."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError

log = logging.getLogger("errors")

# Códigos Postgres/PostgREST -> status HTTP. O que não estiver aqui vira 500.
_PG_CODE_STATUS = {
    "23505": 409,  # unique_violation
    "23503": 409,  # foreign_key_violation
    "23502": 400,  # not_null_violation
    "22P02": 400,  # invalid_text_representation (ex.: UUID malformado)
    "PGRST116": 404,  # nenhuma linha encontrada
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _handle_api_error(request: Request, exc: APIError) -> JSONResponse:
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
        return JSONResponse(status_code=status, content={"detail": detail})

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Erro não tratado em %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor."})
