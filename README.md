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

   | Variável | Obrigatória? | Descrição |
   |---|:---:|---|
   | `SUPABASE_URL` | ✅ | URL da **API REST** do projeto Supabase (`https://<ref>.supabase.co`) |
   | `SUPABASE_KEY` | ✅ | Chave do Supabase (service_role) |
   | `SECRET_KEY` | ✅ | Segredo do JWT (mín. 32 caracteres) |
   | `DATABASE_URL` | ⬜ | Conexão **Postgres direta** via SQLAlchemy (`postgresql+asyncpg://...`). **≠ SUPABASE_URL** — é a string de conexão do banco, usada só no check do `/health`. Sem ela, o app funciona via REST. |
   | `GOOGLE_API_KEY` | ⬜* | Chave do Gemini (AI Studio). *Obrigatória só para o RAG (`/api/v1/ia/*`). |
   | `LLM_MODEL` / `EMBEDDING_MODEL` | ⬜ | Modelo do Gemini / modelo de embeddings HF (têm default) |
   | `RAG_TOP_K` / `RAG_TEMPERATURE` / `HF_CACHE_FOLDER` | ⬜ | Ajustes do RAG |
   | `REDIS_URL` | ⬜ | Broker do Celery (default `redis://localhost:6379/0`) |
   | `ALGORITHM` / `ACCESS_TOKEN_EXPIRE` / `REFRESH_TOKEN_EXPIRE` | ⬜ | JWT (têm default) |
   | `LOG_LEVEL` / `ENVIRONMENT` / `CORS_ORIGINS` | ⬜ | Configuração da aplicação |

   > **`DATABASE_URL` não é o `SUPABASE_URL`.** `SUPABASE_URL` é o endpoint REST
   > (PostgREST); `DATABASE_URL` é a conexão Postgres direta
   > (`db.<ref>.supabase.co:5432`). O projeto usa principalmente o REST, então
   > `DATABASE_URL` é opcional para desenvolvimento.

---

## Rodando localmente do zero (passo a passo)

Pré-requisito: **Python 3.11+** e **internet** (a app fala com o Supabase na nuvem;
não precisa de Postgres local).

```bash
# 1. Ambiente virtual + dependências (puxa torch/sentence-transformers, ~1GB)
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Variáveis de ambiente
cp .env.example .env
#   Edite o .env e preencha no mínimo: SUPABASE_URL, SUPABASE_KEY, SECRET_KEY
#   (e GOOGLE_API_KEY se for usar o RAG)

# 3a. Só a API + testes:
uvicorn app.main:app --reload        # API em http://localhost:8000/docs
pytest -q                            # 128 testes, todos mockados (não precisam de Redis/Google/banco)

# 3b. Stack completo (API + Redis + worker Celery) num comando só:
./scripts/run_local.sh               # Ctrl+C encerra tudo
```

O [scripts/run_local.sh](scripts/run_local.sh) sobe **Redis (via redislite, sem Docker/sudo)**,
o **worker Celery** e a **API** juntos — útil para exercitar os jobs assíncronos
(re-treino ML, geração de embeddings) e o RAG.

| Quero… | Preciso de |
|---|---|
| Rodar **testes** | venv + deps + `.env` (SUPABASE_*, SECRET_KEY) |
| Subir a **API** (obras/dashboard/mapa/auth) | idem + internet/Supabase |
| **Jobs** (ML / embeddings) | + Redis + worker Celery (ou `run_local.sh`) |
| **RAG / consulta IA** | + `GOOGLE_API_KEY` (modelo HF baixa no 1º uso, ~420MB) |

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
| GET | `/predicoes` | Lista predições (filtro opcional `nivel_risco`) |
| GET | `/predicoes/{obra_id}` | Predição de risco (atraso/estouro) de uma obra |
| POST | `/reprocessar` | Dispara task Celery de re-treinamento do modelo |
| GET | `/status/{task_id}` | Status da task de re-treinamento |
| POST | `/analisar` | (compat) Dispara análise de risco de uma obra |

### IA / RAG — `/api/v1/ia`
Agente de IA generativa com RAG (LangChain + pgvector/Supabase) sobre contratos e obras.
**Stack gratuita:** embeddings locais HuggingFace `paraphrase-multilingual-MiniLM-L12-v2`
(384 dims) + LLM **Gemini 1.5 Flash** (Google AI Studio).

| Método | Rota | Perfil | Descrição |
|---|---|---|---|
| POST | `/consulta` | admin, gestor | Consulta em linguagem natural → `{"resposta", "modelo"}` |
| GET | `/consulta/stream` | admin, gestor | Mesma consulta com streaming SSE (`?pergunta=...`) |
| POST | `/embeddings/gerar` | admin | Dispara task Celery que indexa contratos sem embedding (enriquecidos com o contexto da obra: nome, secretaria, bairro, nível de risco) |
| GET | `/warmup` | autenticado | Pré-aquece o modelo de embedding (~420MB) |

**Pré-requisitos para rodar o RAG:**
1. `GOOGLE_API_KEY` no `.env` (gere em [aistudio.google.com](https://aistudio.google.com)).
2. Rodar [scripts/sql/rag_match_function.sql](scripts/sql/rag_match_function.sql) no Supabase
   (cria a função `match_documentos` + índice HNSW; exige `embeddings.vetor` como `VECTOR(384)`).
3. Popular os embeddings: `POST /api/v1/ia/embeddings/gerar` (ou rodar a task no worker).

---

## Testes

```bash
pytest -q                       # suíte completa
pytest --cov=app --cov-report=term-missing   # com cobertura
```

## Jobs assíncronos (Celery + Redis)

Tarefas pesadas (re-treino do modelo de risco, geração de embeddings) rodam em
background via **Celery**, usando **Redis** como broker e result backend
(`REDIS_URL`), sem bloquear a API.

**Tasks** (em `app/tasks/`):
| Task | Módulo | Disparada por |
|---|---|---|
| `run_ml_retraining` | `ml_tasks.py` | `POST /api/v1/ml/reprocessar` |
| `run_ml_analysis` | `ml_tasks.py` | `POST /api/v1/ml/analisar` |
| `generate_embeddings` | `embedding_tasks.py` | `POST /api/v1/ia/embeddings/gerar` |

**Retry automático com backoff exponencial** — em caso de falha, cada task tenta
novamente com atraso crescente: `2s → 4s → 8s → …` (limitado a 600s), até
`max_retries=3` (ver `backoff_countdown` em [celery_app.py](app/tasks/celery_app.py)).

**Subir o worker localmente:**
```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

**Monitorar uma task** — todo disparo retorna um `task_id`; consulte o estado em:
```bash
GET /api/v1/ml/status/{task_id}   # -> {"task_id": "...", "status": "SUCCESS", "resultado": {...}}
```

## Deploy

O `Procfile` define os processos para plataformas como Railway/Heroku:

```
web:    uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: celery -A app.tasks.celery_app worker --loglevel=info
```

**Railway:**
1. Adicione o **Redis** como plugin/addon — ele expõe a variável `REDIS_URL`,
   já consumida por [config.py](app/core/config.py).
2. Crie dois serviços a partir deste repositório: um **web** (start command do
   `web`) e um **worker** (start command do `worker`). Ambos compartilham a
   mesma imagem Docker.
3. Configure as variáveis de ambiente (`SUPABASE_*`, `DATABASE_URL`,
   `SECRET_KEY`, `OPENAI_API_KEY`, etc.) em ambos os serviços.
