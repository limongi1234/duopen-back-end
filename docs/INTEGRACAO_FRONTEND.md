# Guia de integração — Frontend ↔ API (DUOPEN)

**Decisão:** a **API é a fonte da verdade do contrato**. O frontend se alinha ao
**OpenAPI/Swagger** da API (não o contrário).

- Swagger UI: `GET /docs` · ReDoc: `GET /redoc` · Spec: `GET /openapi.json`
- **Gerar o cliente/tipos a partir do contrato** (recomendado — elimina drift):
  ```bash
  npx openapi-typescript http://localhost:8000/openapi.json -o src/api-types.ts
  # ou um cliente completo: orval / openapi-generator
  ```

---

## Ajustes que o frontend precisa fazer

> Os endpoints já existem e funcionam; o que muda são **nomes de campos/estrutura**
> no lado do front para casar com o contrato real.

### 1. `GET /api/v1/dashboard` (métricas globais)
**Retorna** (`DashboardResponse`):
```jsonc
{ "total_obras": 0, "valor_total": 0, "media_execucao_pct": 0,
  "obras_em_andamento": 0, "obras_concluidas": 0, "obras_atrasadas": 0 }
```
- `valor_total`  → o front usava `valor_total_contratado`
- `media_execucao_pct` → o front usava `media_execucao`
- **Não** vem `por_status` / `por_secretaria` / `evolucao_mensal` aninhados — buscar
  nos endpoints próprios (itens 2 e 3).
- Aceita período opcional `?data_inicio=YYYY-MM-DD&data_fim=YYYY-MM-DD` (tolera valor
  vazio: `data_fim=` é tratado como ausente).

### 2. Distribuições (em vez de `/dashboard/distribuicao` combinado)
- `GET /api/v1/dashboard/distribuicao-status`
- `GET /api/v1/dashboard/distribuicao-secretaria`

Cada um retorna `DistribuicaoItem[]`:
```jsonc
[{ "label": "Em andamento", "quantidade": 12, "valor_total": 0 }]
```
- `label` → mapear para `status` / `secretaria`
- `quantidade` → mapear para `total`

### 3. `GET /api/v1/dashboard/evolucao` → `EvolucaoMensalItem[]`
```jsonc
[{ "mes": "2026-01", "iniciadas": 3, "concluidas": 1 }]
```

### 4. `GET /api/v1/dashboard/ieop` → `IEOPStatsResponse` ✅ (já compatível)
```jsonc
{ "media_geral": 71.4, "classe_geral": "Bom",
  "distribuicao": { "Ótimo": 178, "Bom": 182, "Regular": 132, "Ruim": 3 },
  "ranking_secretarias": [{ "secretaria": "…", "media_ieop": 94.1 }],
  "piores_obras": [{ "id": "…", "nome": "…", "ieop_score": 28.0, "ieop_classe": "Ruim" }] }
```

---

## Já resolvido no backend (não precisa mexer no front)
- **Datas vazias** em `/obras`, `/dashboard`, `/mapa`: `data_fim=` (vazio) não dá mais
  **422** — é tratado como sem filtro.
- **`/dashboard/ieop`**: criado (antes dava **404**).
- **Obras** já expõem `ieop_*`, `tipo_sinapi` e campos de coleta (todos nullable);
  listagem aceita `sort=-ieop_score`.

## Autenticação e perfis (atenção ao 403)
- Toda rota de domínio exige **Bearer token** (`POST /api/v1/auth/login`).
- **RAG** (`/api/v1/ia/consulta*`) exige perfil **admin** ou **gestor**; **readonly**
  recebe **403**.
- **`POST /register` aceita `perfil`** (`admin`|`gestor`|`readonly`, default `readonly`)
  — o front pode enviar o perfil no cadastro. ⚠️ Isso permite auto-atribuição; em
  produção, gateie esse fluxo (ex.: só admin cria usuários com perfil elevado).
- Alternativa: promover via banco —
  ```sql
  UPDATE usuarios SET perfil = 'gestor' WHERE email = 'EMAIL_DO_USUARIO';
  ```
