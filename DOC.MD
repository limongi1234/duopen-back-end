# Setup do Backend — duopen-backend
# Instruções para AI Agent
# DUOPEN 2026

---

## Contexto

Este documento instrui um AI Agent a configurar e executar o projeto
`duopen-backend` do zero. Siga cada etapa na ordem apresentada.
Não pule etapas. Valide o resultado de cada etapa antes de avançar.

**Stack:**
- Framework: FastAPI
- Linguagem: Python 3.11+
- Banco de dados: Supabase (PostgreSQL)
- IA Generativa: LangChain + pgvector
- Jobs assíncronos: Celery + Redis
- Deploy: Railway

**Arquitetura:** Clean Architecture
- `routers/` → Controllers (interface com o mundo externo)
- `services/` → Use Cases (regras de negócio)
- `schemas/` → Entities (contratos Pydantic)
- `core/` → Infraestrutura (banco, JWT, config)
- `tasks/` → Jobs assíncronos (Celery)

---

## Pré-requisitos

Antes de iniciar, verifique se os seguintes itens estão disponíveis:

```bash
# Verificar Python >= 3.11
python --version

# Verificar Git
git --version

# Verificar Docker (para Redis local em desenvolvimento)
docker --version
```

Credenciais necessárias (solicitar ao responsável do projeto):
- `SUPABASE_URL` e `SUPABASE_KEY` (service_role) do projeto Supabase
- `OPENAI_API_KEY` para geração de embeddings
- Acesso ao repositório GitHub `duopen-backend`

---

## Etapa 1 — Clonar o repositório

```bash
git clone https://github.com/seu-org/duopen-backend.git
cd duopen-backend
```

**Validação:** o diretório `duopen-backend/` deve existir com o arquivo `requirements.txt`.

---

## Etapa 2 — Criar e ativar ambiente virtual

```bash
# Criar o ambiente virtual
python -m venv .venv

# Ativar — Linux/Mac
source .venv/bin/activate

# Ativar — Windows
.venv\Scripts\activate
```

**Validação:** o terminal deve exibir `(.venv)` no início da linha após ativar.

> O ambiente virtual deve estar ativo em TODOS os terminais usados no projeto.
> Nunca instale dependências sem ativar o ambiente virtual primeiro.

---

## Etapa 3 — Instalar dependências

```bash
pip install -r requirements.txt
```

**Conteúdo esperado do `requirements.txt`:**

```text
# API
fastapi>=0.111
uvicorn[standard]>=0.29
pydantic>=2.7
pydantic-settings>=2.2

# Banco de dados
supabase>=2.4
sqlalchemy[asyncio]>=2.0
asyncpg>=0.29

# Autenticação
python-jose[cryptography]>=3.3
passlib[bcrypt]>=1.7

# IA Generativa e RAG
langchain>=0.2
langchain-openai>=0.1
langchain-community>=0.2

# Jobs assíncronos
celery[redis]>=5.4
redis>=5.0

# Utilitários
httpx>=0.27
python-dotenv>=1.0

# Testes
pytest>=8.2
pytest-asyncio>=0.23
pytest-cov>=5.0
```

**Validação:**
```bash
pip list | grep fastapi
pip list | grep langchain
pip list | grep celery
```

---

## Etapa 4 — Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Editar o arquivo `.env` com os valores reais:

```env
# ── Supabase ──────────────────────────────────────────────────
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=eyJhbGc...          # service_role — NUNCA a anon key

# ── JWT ───────────────────────────────────────────────────────
SECRET_KEY=                      # gerar com: openssl rand -hex 32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE=15           # minutos
REFRESH_TOKEN_EXPIRE=10080       # minutos (7 dias)

# ── Redis / Celery ────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── IA Generativa ─────────────────────────────────────────────
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small

# ── Aplicação ─────────────────────────────────────────────────
LOG_LEVEL=INFO
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:5173
```

**Regras obrigatórias:**
- O arquivo `.env` NUNCA deve ser commitado no Git
- Confirmar que `.env` está listado no `.gitignore`
- Usar `SUPABASE_KEY` com a chave `service_role`, jamais a `anon`
- Gerar `SECRET_KEY` com `openssl rand -hex 32` — nunca usar uma string manual

**Validação:**
```bash
# Confirmar que .env não será commitado
cat .gitignore | grep ".env"

# Gerar SECRET_KEY se ainda não gerou
openssl rand -hex 32
```

---

## Etapa 5 — Criar estrutura de diretórios

Caso o repositório ainda não tenha a estrutura criada, criá-la:

```bash
mkdir -p app/routers
mkdir -p app/services
mkdir -p app/schemas
mkdir -p app/core
mkdir -p app/tasks
mkdir -p tests/unit
mkdir -p tests/integration

touch app/__init__.py
touch app/routers/__init__.py
touch app/services/__init__.py
touch app/schemas/__init__.py
touch app/core/__init__.py
touch app/tasks/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py
```

**Estrutura esperada ao final:**

```
duopen-backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py       # pydantic-settings
│   │   ├── database.py     # conexão Supabase async
│   │   └── security.py     # JWT + bcrypt
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── obras.py
│   │   ├── contratos.py
│   │   ├── fornecedores.py
│   │   ├── mapa.py
│   │   ├── dashboard.py
│   │   ├── ml.py
│   │   └── ia.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── rag_service.py
│   │   └── ml_service.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── obras.py
│   │   └── ml.py
│   └── tasks/
│       ├── __init__.py
│       ├── celery_app.py
│       ├── ml_tasks.py
│       └── embedding_tasks.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── Dockerfile
├── Procfile
├── requirements.txt
└── .env.example
```

---

## Etapa 6 — Implementar app/core/config.py

Criar o arquivo de configuração usando `pydantic-settings`:

```python
# app/core/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_key: str

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire: int = 15
    refresh_token_expire: int = 10080

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # IA
    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"

    # App
    log_level: str = "INFO"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

---

## Etapa 7 — Implementar app/core/database.py

```python
# app/core/database.py
from supabase import create_client, Client
from app.core.config import get_settings
import logging

log = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    """
    Dependency injection para o cliente Supabase.
    Usar com FastAPI Depends() nos routers.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


async def check_connection() -> bool:
    """Verifica se a conexão com o Supabase está ativa."""
    try:
        client = get_supabase_client()
        client.table("ingestoes").select("id").limit(1).execute()
        return True
    except Exception as e:
        log.error(f"Falha na conexão com Supabase: {e}")
        return False
```

---

## Etapa 8 — Implementar app/main.py

```python
# app/main.py
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
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
```

---

## Etapa 9 — Subir Redis local

```bash
# Subir container Redis
docker run -d --name redis-duopen -p 6379:6379 redis:7-alpine

# Verificar se está rodando
docker ps | grep redis-duopen

# Testar conexão
docker exec redis-duopen redis-cli ping
# Esperado: PONG
```

> Em produção no Railway, o Redis é um addon gerenciado.
> O `REDIS_URL` é injetado automaticamente — não precisa de Docker.

---

## Etapa 10 — Implementar app/tasks/celery_app.py

```python
# app/tasks/celery_app.py
from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "duopen",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.ml_tasks",
        "app.tasks.embedding_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,
    task_default_retry_delay=60,
)
```

---

## Etapa 11 — Rodar o servidor

Abrir **dois terminais** com o ambiente virtual ativado:

**Terminal 1 — API FastAPI:**
```bash
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Worker Celery:**
```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

**Validação — testar o health check:**
```bash
curl http://localhost:8000/health
```

Resposta esperada:
```json
{
  "status": "ok",
  "database": "connected",
  "version": "1.0.0",
  "environment": "development"
}
```

Se `database` retornar `"error"`, verificar `SUPABASE_URL` e `SUPABASE_KEY` no `.env`.

---

## Etapa 12 — Rodar os testes

```bash
# Todos os testes
pytest tests/ -v

# Com cobertura (meta: >= 80%)
pytest tests/ --cov=app --cov-report=term-missing

# Apenas unitários
pytest tests/unit/ -v

# Apenas integração
pytest tests/integration/ -v
```

**Validação:** todos os testes devem passar com cobertura >= 80%.

---

## Etapa 13 — Criar Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Etapa 14 — Criar Procfile (Railway)

```procfile
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: celery -A app.tasks.celery_app worker --loglevel=info
```

> O Railway injeta `$PORT` automaticamente.
> Nunca fixar a porta 8000 no Procfile de produção.

---

## Etapa 15 — Deploy no Railway

```bash
# Instalar CLI do Railway
npm install -g @railway/cli

# Login
railway login

# Linkar ao projeto existente ou criar novo
railway link
# ou
railway init

# Adicionar addon Redis
railway add redis

# Configurar variáveis de ambiente no Railway
# (pelo painel: Settings > Variables)
# SUPABASE_URL, SUPABASE_KEY, SECRET_KEY, OPENAI_API_KEY

# Deploy
railway up
```

**Validação pós-deploy:**
```bash
# Substituir pela URL gerada pelo Railway
curl https://duopen-backend.up.railway.app/health
```

---

## Etapa 16 — Configurar CI/CD no GitHub Actions

Criar o arquivo `.github/workflows/backend.yml`:

```yaml
name: Backend CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  testes:
    name: Testes
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=app --cov-fail-under=80
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          SECRET_KEY: ${{ secrets.SECRET_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          REDIS_URL: redis://localhost:6379/0
          ENVIRONMENT: test

  deploy:
    name: Deploy Railway
    runs-on: ubuntu-latest
    needs: testes
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: railwayapp/railway-github-action@v1
        with:
          railway-token: ${{ secrets.RAILWAY_TOKEN }}
```

**Secrets a configurar no GitHub (Settings > Secrets > Actions):**

| Secret | Descrição |
|---|---|
| `RAILWAY_TOKEN` | Token de acesso ao Railway |
| `SUPABASE_URL` | URL do Supabase de produção |
| `SUPABASE_KEY` | Chave service_role de produção |
| `SECRET_KEY` | Chave JWT de produção |
| `OPENAI_API_KEY` | Chave da API de embeddings |

---

## Troubleshooting — erros comuns

### ModuleNotFoundError
O ambiente virtual não está ativo ou as dependências não foram instaladas.
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Connection refused (Redis)
O container Redis não está rodando.
```bash
docker start redis-duopen
# ou subir novamente
docker run -d --name redis-duopen -p 6379:6379 redis:7-alpine
```

### 401 Unauthorized
O `access_token` expirou (15 minutos). Usar `/api/v1/auth/refresh` com o `refresh_token`.

### supabase APIError
Verificar `SUPABASE_URL` e `SUPABASE_KEY` no `.env`.
Confirmar que a chave usada é `service_role`, não `anon`.

### Celery não processa tasks
Verificar se o worker está rodando em terminal separado.
```bash
celery -A app.tasks.celery_app status
```

### Port already in use
Outra instância do uvicorn está rodando.
```bash
lsof -ti:8000 | xargs kill -9
uvicorn app.main:app --reload --port 8000
```

---

## Checklist de validação final

Antes de considerar o setup concluído, confirmar cada item:

```
[ ] python --version retorna >= 3.11
[ ] (.venv) aparece no terminal após ativar o ambiente virtual
[ ] pip list mostra fastapi, langchain e celery instalados
[ ] .env está preenchido com todos os valores reais
[ ] .env não aparece no git status (está no .gitignore)
[ ] Estrutura de diretórios criada conforme Etapa 5
[ ] GET /health retorna {"status": "ok", "database": "connected"}
[ ] Redis está rodando (docker ps mostra redis-duopen)
[ ] Worker Celery rodando sem erros no terminal 2
[ ] pytest tests/ passa com cobertura >= 80%
[ ] Dockerfile e Procfile criados
[ ] Deploy no Railway bem-sucedido
[ ] CI/CD configurado com secrets no GitHub
```

---

## Referências

- FastAPI: https://fastapi.tiangolo.com
- Supabase Python: https://supabase.com/docs/reference/python
- LangChain: https://python.langchain.com
- Celery: https://docs.celeryq.dev
- Railway: https://docs.railway.app
- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings

---

*DUOPEN 2026 · Gustavo Kozlowski & Renato Lemos Limongi de Aguiar Moraes · duopen-backend*