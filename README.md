# DUOPEN 2026 — API

**Plataforma Inteligente de Análise de Eficiência de Obras Públicas — Macaé/RJ**

API REST construída em FastAPI para coletar, analisar e visualizar dados de
obras públicas, contratos e fornecedores, com recursos de Machine Learning
(predição de risco/atraso) e IA Generativa (RAG) sobre a base contratual.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Framework | FastAPI + Uvicorn |
| Linguagem | Python 3.11+ |
| Banco de dados | Supabase (PostgreSQL) + SQLAlchemy async (asyncpg) |
| Autenticação | JWT (python-jose) + bcrypt |
| IA Generativa / RAG | LangChain + OpenAI (pgvector) |
| Jobs assíncronos | Celery + Redis |
| Testes | pytest + pytest-asyncio + pytest-cov |
| Deploy | Docker / Railway (Procfile) |

## Arquitetura (Clean Architecture)

```
app/
├── main.py            # Bootstrap FastAPI, CORS, lifespan, /health
├── routers/           # Controllers — endpoints HTTP
│   ├── auth.py        #   /api/v1/auth
│   ├── obras.py       #   /api/v1/obras
│   ├── contratos.py   #   /api/v1/contratos
│   ├── fornecedores.py#   /api/v1/fornecedores
│   ├── mapa.py        #   /api/v1/mapa  (GeoJSON)
│   ├── dashboard.py   #   /api/v1/dashboard
│   ├── ml.py          #   /api/v1/ml
│   └── ia.py          #   /api/v1/ia    (RAG)
├── services/          # Use cases / regras de negócio (ml_service, rag_service)
├── schemas/           # Contratos Pydantic (entities)
├── core/              # Infraestrutura: config, database, security
└── tasks/             # Jobs Celery (embeddings, ml)
```

---

## Pré-requisitos

- Python **3.11+**
- Conta/projeto **Supabase** (`SUPABASE_URL`, `SUPABASE_KEY`)
- `OPENAI_API_KEY` (para embeddings / RAG)
- **Redis** (apenas para os jobs Celery — opcional para subir só a API)

## Configuração

1. **Crie o ambiente virtual e instale as dependências:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure as variáveis de ambiente** — copie o exemplo e preencha:

   ```bash
   cp .env.example .env
   ```

   | Variável | Descrição |
   |---|---|
   | `SUPABASE_URL` / `SUPABASE_KEY` | Credenciais do projeto Supabase (service_role) |
   | `DATABASE_URL` | Postgres direto via SQLAlchemy async (`postgresql+asyncpg://...`) |
   | `SECRET_KEY` | Segredo do JWT (mín. 32 caracteres) |
   | `ALGORITHM` | Algoritmo JWT (default `HS256`) |
   | `ACCESS_TOKEN_EXPIRE` / `REFRESH_TOKEN_EXPIRE` | Expiração dos tokens (minutos) |
   | `REDIS_URL` | Broker do Celery |
   | `OPENAI_API_KEY` / `EMBEDDING_MODEL` | IA Generativa / embeddings |
   | `LOG_LEVEL` / `ENVIRONMENT` / `CORS_ORIGINS` | Configuração da aplicação |

---

## Executando

### API (desenvolvimento)

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health check: <http://localhost:8000/health>

> O `/health` retorna `degraded` se o Postgres direto (`DATABASE_URL`) não estiver
> acessível, mesmo com o Supabase conectado.

### Worker Celery (jobs assíncronos)

```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

### Docker

```bash
docker build -t duopen-backend .
docker run -p 8000:8000 --env-file .env duopen-backend
```

---

## Endpoints

Base: `/api/v1`. As rotas de domínio exigem autenticação via **Bearer token** JWT
(obtido em `/auth/login`).

### Auth — `/api/v1/auth`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/register` | Cadastro de usuário ([detalhes](#criação-de-usuário--post-apiv1authregister)) |
| POST | `/login` | Login → access + refresh token |
| POST | `/refresh` | Renova o access token |
| GET | `/me` | Dados do usuário autenticado |

#### Criação de usuário — `POST /api/v1/auth/register`

Cria um novo usuário na tabela `usuarios`. A senha **nunca** é armazenada em texto
puro — é gravada já com hash bcrypt (`senha_hash`). Endpoint **público** (não exige
autenticação).

**Request body** (`application/json`)

| Campo | Tipo | Obrigatório | Descrição |
|---|---|:---:|---|
| `email` | string (email) | ✅ | E-mail do usuário. Validado como e-mail e deve ser único. |
| `password` | string | ✅ | Senha em texto puro — convertida em hash bcrypt no servidor. |
| `nome` | string | ✅ | Nome do usuário. |

```json
{
  "email": "joao@exemplo.com",
  "password": "senha-super-secreta",
  "nome": "João Silva"
}
```

**Resposta `201 Created`** — `UserResponse` (não retorna a senha):

```json
{
  "id": "uuid-do-usuario",
  "email": "joao@exemplo.com",
  "nome": "João Silva"
}
```

**Erros**

| Status | Quando ocorre |
|:---:|---|
| `400 Bad Request` | E-mail já cadastrado (`{"detail": "Email já cadastrado"}`). |
| `422 Unprocessable Entity` | Corpo inválido (campo ausente ou e-mail malformado). |
| `500 Internal Server Error` | Falha ao acessar/gravar na base de dados. |

**Exemplo com `curl`**

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "joao@exemplo.com",
    "password": "senha-super-secreta",
    "nome": "João Silva"
  }'
```

> Após o cadastro, autentique-se em `POST /api/v1/auth/login` para receber o
> `access_token` e usá-lo como `Authorization: Bearer <token>` nas rotas protegidas.

### Obras — `/api/v1/obras`
| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Lista obras (filtros: `status`, `secretaria`, `bairro`, `nivel_risco`; paginação `page`/`size`) |
| GET | `/{obra_id}` | Detalhe da obra |
| GET | `/{obra_id}/contratos` | Contratos da obra |
| GET | `/{obra_id}/aditivos` | Aditivos da obra |
| POST | `/` | Cria obra |
| PATCH | `/{obra_id}` | Atualiza obra |
| DELETE | `/{obra_id}` | Remove obra |

### Contratos — `/api/v1/contratos`
| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Lista contratos |
| GET | `/{contrato_id}` | Detalhe do contrato |
| GET | `/obra/{obra_id}` | Contratos por obra |

### Fornecedores — `/api/v1/fornecedores`
| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Ranking de fornecedores (filtros: `taxa_aditivo_max`, `media_prob_atraso_max`; paginação) |
| GET | `/{cnpj}` | Perfil do fornecedor por CNPJ |
| GET | `/{cnpj}/obras` | Obras do fornecedor |

### Mapa — `/api/v1/mapa`
| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Obras como **GeoJSON FeatureCollection** (filtros: `status`, `nivel_risco`, `secretaria`) |
| GET | `/obras` | Obras geolocalizadas |

### Dashboard — `/api/v1/dashboard`
| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Visão geral |
| GET | `/resumo` | Métricas-resumo |
| GET | `/eficiencia` | Ranking de eficiência |
| GET | `/distribuicao-status` | Distribuição por status |
| GET | `/distribuicao-secretaria` | Distribuição por secretaria |
| GET | `/evolucao` | Evolução mensal |
| GET | `/alertas` | Obras em alerta |

### ML — `/api/v1/ml`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/analisar` | Dispara análise de ML |
| GET | `/predicoes/{obra_id}` | Predições da obra |

### IA / RAG — `/api/v1/ia`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/query` | Consulta em linguagem natural (RAG) |
| POST | `/embeddings` | Gera embeddings da base |

---

## Testes

```bash
pytest -q                       # suíte completa
pytest --cov=app --cov-report=term-missing   # com cobertura
```

## Deploy

O `Procfile` define os processos para plataformas como Railway/Heroku:

```
web:    uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: celery -A app.tasks.celery_app worker --loglevel=info
```
