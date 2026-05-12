from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.database import check_connection
from app.routers import auth, obras, contratos, fornecedores, mapa, dashboard, ml, ia
import logging

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

app = FastAPI(
    title="DUOPEN 2026 — API",
    description="Plataforma Inteligente de Análise de Eficiência de Obras Públicas — Macaé/RJ",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
    db_ok = await check_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "version": "1.0.0",
        "environment": settings.environment,
    }
