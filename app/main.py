from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import check_connection, dispose_db_engine, init_db_engine
from app.routers import auth, contratos, dashboard, fornecedores, ia, mapa, ml, obras
import logging

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)


def _warmup_embeddings() -> None:
    """Pré-carrega o modelo de embedding (~420MB) fora do event loop."""
    try:
        from app.services.rag_service import get_embeddings

        get_embeddings()
        logging.getLogger(__name__).info("Modelo de embedding pré-carregado")
    except Exception as exc:  # warmup é best-effort; não derruba o startup
        logging.getLogger(__name__).warning("Falha no warmup de embeddings: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    init_db_engine()
    # Aquece o modelo de embedding em background (evita ~30s na 1ª consulta RAG).
    # Só quando o RAG está configurado (evita baixar ~420MB em dev/testes sem key).
    if settings.google_api_key:
        asyncio.get_event_loop().run_in_executor(None, _warmup_embeddings)
    yield
    await dispose_db_engine()


app = FastAPI(
    title="DUOPEN 2026 — API",
    description="Plataforma Inteligente de Análise de Eficiência de Obras Públicas — Macaé/RJ",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,         prefix="/api/v1/auth",         tags=["Auth"])
app.include_router(obras.router,        prefix="/api/v1/obras",        tags=["Obras"])
app.include_router(contratos.router,    prefix="/api/v1/contratos",    tags=["Contratos"])
app.include_router(fornecedores.router, prefix="/api/v1/fornecedores", tags=["Fornecedores"])
app.include_router(mapa.router,         prefix="/api/v1/mapa",         tags=["Mapa"])
app.include_router(dashboard.router,    prefix="/api/v1/dashboard",    tags=["Dashboard"])
app.include_router(ml.router,           prefix="/api/v1/ml",           tags=["ML"])
app.include_router(ia.router,           prefix="/api/v1/ia",           tags=["IA"])


@app.get("/health", tags=["Health"])
async def health_check():
    checks: dict[str, Any] = await check_connection()
    healthy = all(checks.values())
    return {
        "status": "ok" if healthy else "degraded",
        "checks": {k: ("connected" if v else "error") for k, v in checks.items()},
        "version": "1.0.0",
        "environment": settings.environment,
    }
