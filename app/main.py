import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import check_connection, dispose_db_engine, init_db_engine
from app.core.errors import register_error_handlers
from app.routers import auth, contratos, dashboard, fornecedores, ia, mapa, ml, obras

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s [%(request_id)s] — %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Embeddings agora são via API do Gemini (sem modelo local/torch), então não
    # há warmup pesado no startup — a app sobe leve.
    init_db_engine()
    yield
    await dispose_db_engine()


API_DESCRIPTION = """
Plataforma Inteligente de Análise de Eficiência de Obras Públicas — **Macaé/RJ**.

### Autenticação
Quase todas as rotas exigem **Bearer token** JWT (obtido em `POST /api/v1/auth/login`).
Envie no header: `Authorization: Bearer <access_token>`.

### Perfis e permissões
- **admin** — acesso total (inclui re-treino de ML e indexação de embeddings)
- **gestor** — dashboard e consultas RAG
- **readonly** — apenas visualização (sem RAG)

Rotas sensíveis retornam **403** quando o perfil não tem permissão.
"""

tags_metadata = [
    {"name": "Auth", "description": "Cadastro, login, refresh e perfil do usuário (JWT)."},
    {
        "name": "Obras",
        "description": "Listagem (filtros, período, sort, paginação), detalhe, contratos e aditivos.",
    },
    {"name": "Contratos", "description": "Consulta de contratos (lista, detalhe e por obra)."},
    {"name": "Fornecedores", "description": "Ranking de fornecedores e obras por CNPJ."},
    {
        "name": "Mapa",
        "description": "Obras geolocalizadas em GeoJSON, com filtros e recorte por período.",
    },
    {
        "name": "Dashboard",
        "description": "Métricas agregadas (calculadas da tabela de obras) e distribuições.",
    },
    {
        "name": "ML",
        "description": "Predições de risco (XGBoost) e re-treino assíncrono — re-treino é admin.",
    },
    {
        "name": "IA",
        "description": "RAG (embeddings + LLM via Gemini) sobre contratos/obras — consulta é admin/gestor.",
    },
    {"name": "Health", "description": "Verificação de saúde (Supabase e banco direto)."},
]

app = FastAPI(
    title="DUOPEN 2026 — API",
    description=API_DESCRIPTION,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(obras.router, prefix="/api/v1/obras", tags=["Obras"])
app.include_router(contratos.router, prefix="/api/v1/contratos", tags=["Contratos"])
app.include_router(fornecedores.router, prefix="/api/v1/fornecedores", tags=["Fornecedores"])
app.include_router(mapa.router, prefix="/api/v1/mapa", tags=["Mapa"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(ml.router, prefix="/api/v1/ml", tags=["ML"])
app.include_router(ia.router, prefix="/api/v1/ia", tags=["IA"])


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    checks: dict[str, Any] = await check_connection()
    healthy = all(checks.values())
    return {
        "status": "ok" if healthy else "degraded",
        "checks": {k: ("connected" if v else "error") for k, v in checks.items()},
        "version": "1.0.0",
        "environment": settings.environment,
    }
