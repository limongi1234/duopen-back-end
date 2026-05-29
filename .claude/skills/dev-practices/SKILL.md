---
name: dev-practices
description: Aplique ao implementar, refatorar ou revisar mudanças no duopen-backend. Garante TDD, clean code, clean architecture, design patterns, conventional commits, git flow, cibersegurança e atualização da documentação conforme o escopo atual. Use sempre que a tarefa envolver escrever/alterar código, criar endpoints/tasks/serviços, ou abrir commits/PRs.
---

# Boas práticas de desenvolvimento — duopen-backend

Stack: **FastAPI · Supabase (PostgREST + pgvector) · Celery/Redis · LangChain/Gemini · pytest**.
Aplique os princípios abaixo de forma proporcional ao tamanho da mudança — sem cerimônia
desnecessária, mas sem pular o essencial (testes e segurança nunca se pulam).

## 1. TDD (test-driven, ou no mínimo test-first-mind)
- **Antes de codar**: identifique o comportamento e escreva/ajuste o teste em `tests/unit/`
  (ou `tests/integration/`). Rode `pytest -q` e veja falhar pelo motivo certo.
- Implemente o mínimo para passar; depois refatore com os testes verdes.
- **Padrões deste repo** (siga-os para manter consistência):
  - Supabase é **sempre mockado** (`MagicMock`); nunca chame a rede em teste unitário.
    Espelhe a cadeia real: `db.table.return_value.select.return_value.eq.return_value.execute.return_value.data`.
  - Para LangChain/Gemini/embeddings: mocke os componentes (`buscar_documentos`, `get_llm`,
    `HuggingFaceEmbeddings`) — nada de baixar modelo nem chamar API em teste.
  - Endpoints autenticados: o fixture `client_with_auth` faz override de `get_current_user`;
    teste os gates de perfil (403) sobrescrevendo o perfil.
- **Sempre** rode a suíte inteira antes de commitar (`pytest -q`) e confirme robustez de
  ordem se mexer em singletons/imports globais (já tivemos vazamento via `get_settings`).
- Toda correção de bug ganha um teste que o reproduz.

## 2. Clean code
- Nomes em português coerentes com o domínio (obras, contratos, situacao, perfil…).
- Funções curtas e com responsabilidade única; early-return em vez de aninhar.
- Sem números/strings mágicos: extraia constantes (ex.: `RETRY_BACKOFF_BASE`, `MATCH_FUNCTION`).
- Comentário explica **porquê**, não o **o quê**. Densidade de comentários = a do arquivo vizinho.
- Não deixe código morto, `print` de debug, nem imports não usados.

## 3. Clean architecture (respeite as camadas)
```
routers/   → controllers (HTTP, validação, auth/gate de perfil) — sem regra de negócio pesada
services/  → casos de uso / regra de negócio (ex.: rag_service, ml_service)
schemas/   → contratos Pydantic (entrada/saída)
core/      → infraestrutura (config, database, security)
tasks/     → jobs assíncronos (Celery)
```
- Dependência aponta para dentro: `routers → services → core`. Nunca o contrário.
- Acesso a dados (Supabase) fica no router/service que o usa via `Depends(get_supabase_client)`;
  serviços que encapsulam leitura recebem o client por injeção (ex.: `MLService(db)`).
- **Resiliência a schema**: o banco (views materializadas) pode estar stale/não-populado.
  Trate erros do PostgREST (ex.: `APIError` código `55000`) com fallback sensato em vez de 500.

## 4. Design patterns (use quando agregam, não por enfeite)
- **Dependency Injection** via `Depends` (FastAPI) — já é o padrão do projeto.
- **Singleton** para recursos caros (modelo de embedding, LLM): `get_embeddings()/get_llm()`.
- **Factory/closure** para dependências parametrizadas: `require_perfil("admin", "gestor")`.
- **Strategy/fallback**: caminho primário (view) + alternativo (tabela base) quando indisponível.
- **Repository-ish**: serviços encapsulam a fonte de dados; o router não conhece nomes de tabela.

## 5. Conventional commits + git flow
- **Conventional Commits** (em português, imperativo): `tipo(escopo): resumo`.
  Tipos: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `build`, `ci`.
  Ex.: `feat(ia): streaming SSE na consulta RAG`.
- Corpo explica o **porquê** e o impacto; cite o que foi validado (testes, e2e).
- **Rodapé obrigatório** neste projeto:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- **Git flow**: trabalhe em branch (`feat/...`, `fix/...`) e abra PR para `master`;
  só faça push direto em `master` se o usuário pedir. **Commit/push apenas quando solicitado.**
- Commits pequenos e temáticos (um assunto por commit). Rode os testes antes de cada commit.
- PRs: descrição com contexto, o que mudou, como testar; rodapé
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

## 6. Cibersegurança
- **Nunca** commitar segredos: `.env` é ignorado; só versione `.env.example` com placeholders.
  Não imprima chaves/tokens em logs (mascare).
- **Autorização no servidor** (não confie no front): gateie ações por perfil com
  `require_perfil(...)` — admin para re-treino/ingestão, admin+gestor para RAG, readonly só leitura.
- **Menor privilégio**: `register` cria `readonly`; elevação só no banco. Sem auto-escalação via body.
- **Senhas**: sempre hash (bcrypt em `security.py`); nunca em texto puro nem em respostas.
- **Validação de entrada** via Pydantic; valide ranges/tipos (`Query(ge=, le=)`).
- **SQL/DDL**: prefira a API REST/RPC; ao escrever SQL, parametrize e evite injeção.
- Trate exceções sem vazar stack/detalhes sensíveis ao cliente (mensagem genérica + log interno).
- Dependências: fixe versões mínimas no `requirements.txt`; evite libs abandonadas.

## 7. Atualizar a documentação conforme o escopo atual
Ao terminar uma mudança, **sincronize a doc** (faz parte do "pronto"):
- `README.md`: tabelas de endpoints, variáveis de ambiente, fluxos de execução.
- `.env.example`: novas variáveis (com placeholder e comentário).
- `scripts/sql/*.sql` e `scripts/run_local.sh`: se mudar schema/infra/local-run.
- Docstrings dos endpoints/serviços novos ou alterados.
- Se o endpoint mudar contrato (campos/rotas), atualize a doc **e** os testes juntos.
- Documente pré-requisitos externos (chaves, migrations, popular dados) de forma honesta.

## Checklist de "pronto" (Definition of Done)
- [ ] Teste novo/ajustado cobrindo o comportamento; `pytest -q` 100% verde.
- [ ] Camadas respeitadas; sem regra de negócio no router; sem acesso a dados fora do lugar.
- [ ] Sem segredos, sem código morto, nomes claros, erros tratados.
- [ ] Gate de perfil/autorização aplicado quando a ação exige.
- [ ] Documentação (README/.env.example/docstrings) atualizada ao escopo.
- [ ] Commit Conventional + rodapé Co-Authored-By; em branch; push só se pedido.
