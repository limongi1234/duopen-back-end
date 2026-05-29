import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

FAKE_USER = {"sub": "test-uid", "email": "test@example.com", "perfil": "admin"}

OBRA_FIXTURE = {
    "id": "obra-1",
    "nome": "Obra Teste",
    "descricao": None,
    "valor_contrato": 100000.0,
    "data_inicio": "2026-01-01",
    "data_prevista_fim": "2026-12-31",
    "status": "em_andamento",
    "municipio": "Macaé",
    "secretaria": "Infraestrutura",
    "bairro": "Centro",
    "nivel_risco": "baixo",
    "latitude": None,
    "longitude": None,
    "created_at": "2026-01-01T00:00:00",
}


@pytest.fixture
def client_with_auth():
    mock_db = MagicMock()
    from app.main import app
    from app.core.database import get_supabase_client
    from app.routers.auth import get_current_user

    app.dependency_overrides[get_supabase_client] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER

    with patch("app.core.database.init_db_engine"), \
         patch("app.core.database.dispose_db_engine"):
        with TestClient(app) as c:
            yield c, mock_db

    app.dependency_overrides.pop(get_supabase_client, None)
    app.dependency_overrides.pop(get_current_user, None)


# ── Obras ──────────────────────────────────────────────────────────────────────

def _mock_lista(db, data, total=None):
    mock_result = MagicMock()
    mock_result.data = data
    mock_result.count = total if total is not None else len(data)
    # sem filtros: select().range().execute()
    db.table.return_value.select.return_value.range.return_value.execute.return_value = mock_result
    # com filtros: select().eq().range().execute()
    db.table.return_value.select.return_value.eq.return_value.range.return_value.execute.return_value = mock_result
    return mock_result


def test_listar_obras(client_with_auth):
    client, db = client_with_auth
    _mock_lista(db, [OBRA_FIXTURE], total=1)

    resp = client.get("/api/v1/obras/")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["size"] == 20
    assert body["pages"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "obra-1"


def test_listar_obras_paginacao(client_with_auth):
    client, db = client_with_auth
    _mock_lista(db, [OBRA_FIXTURE], total=50)

    resp = client.get("/api/v1/obras/?page=2&size=10")

    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 2
    assert body["size"] == 10
    assert body["total"] == 50
    assert body["pages"] == 5


def test_listar_obras_filtro_status(client_with_auth):
    client, db = client_with_auth
    _mock_lista(db, [OBRA_FIXTURE], total=1)

    resp = client.get("/api/v1/obras/?status=em_andamento")

    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_listar_obras_filtro_secretaria(client_with_auth):
    client, db = client_with_auth
    _mock_lista(db, [OBRA_FIXTURE], total=1)

    resp = client.get("/api/v1/obras/?secretaria=Infraestrutura")

    assert resp.status_code == 200


def test_listar_obras_filtro_bairro(client_with_auth):
    client, db = client_with_auth
    _mock_lista(db, [OBRA_FIXTURE], total=1)

    resp = client.get("/api/v1/obras/?bairro=Centro")

    assert resp.status_code == 200


def test_listar_obras_filtro_nivel_risco(client_with_auth):
    client, db = client_with_auth
    _mock_lista(db, [OBRA_FIXTURE], total=1)

    resp = client.get("/api/v1/obras/?nivel_risco=baixo")

    assert resp.status_code == 200


def test_listar_obras_vazia(client_with_auth):
    client, db = client_with_auth
    _mock_lista(db, [], total=0)

    resp = client.get("/api/v1/obras/")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["pages"] == 1
    assert body["items"] == []


def test_listar_obras_sort(client_with_auth):
    client, db = client_with_auth
    mock_result = MagicMock()
    mock_result.data = [OBRA_FIXTURE]
    mock_result.count = 1
    db.table.return_value.select.return_value.order.return_value.range.return_value.execute.return_value = mock_result

    resp = client.get("/api/v1/obras/?sort=-prob_atraso")

    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    db.table.return_value.select.return_value.order.assert_called_with("prob_atraso", desc=True)


def test_listar_obras_limit(client_with_auth):
    client, db = client_with_auth
    mock_result = MagicMock()
    mock_result.data = [OBRA_FIXTURE]
    mock_result.count = 1
    db.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

    resp = client.get("/api/v1/obras/?sort=-prob_atraso&limit=5")

    assert resp.status_code == 200
    body = resp.json()
    assert body["size"] == 5
    assert len(body["items"]) == 1
    db.table.return_value.select.return_value.order.return_value.limit.assert_called_with(5)


def test_obter_obra_found(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [OBRA_FIXTURE]

    resp = client.get("/api/v1/obras/obra-1")

    assert resp.status_code == 200
    assert resp.json()["id"] == "obra-1"
    assert resp.json()["secretaria"] == "Infraestrutura"
    assert resp.json()["bairro"] == "Centro"
    assert resp.json()["nivel_risco"] == "baixo"


def test_obter_obra_not_found(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    resp = client.get("/api/v1/obras/nao-existe")

    assert resp.status_code == 404


def test_contratos_por_obra(client_with_auth):
    client, db = client_with_auth
    contrato = {"id": "cont-1", "obra_id": "obra-1", "valor": 50000.0}
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [contrato]

    resp = client.get("/api/v1/obras/obra-1/contratos")

    assert resp.status_code == 200
    assert resp.json()[0]["obra_id"] == "obra-1"


def test_contratos_por_obra_vazio(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    resp = client.get("/api/v1/obras/nao-existe/contratos")

    assert resp.status_code == 200
    assert resp.json() == []


def test_aditivos_por_obra(client_with_auth):
    client, db = client_with_auth
    aditivo = {"id": "adit-1", "obra_id": "obra-1", "valor_aditivo": 10000.0}
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [aditivo]

    resp = client.get("/api/v1/obras/obra-1/aditivos")

    assert resp.status_code == 200
    assert resp.json()[0]["obra_id"] == "obra-1"


def test_aditivos_por_obra_vazio(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    resp = client.get("/api/v1/obras/nao-existe/aditivos")

    assert resp.status_code == 200
    assert resp.json() == []


def test_criar_obra(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.insert.return_value.execute.return_value.data = [OBRA_FIXTURE]

    resp = client.post("/api/v1/obras/", json={
        "nome": "Obra Teste",
        "valor_contrato": 100000.0,
        "data_inicio": "2026-01-01",
        "data_prevista_fim": "2026-12-31",
    })

    assert resp.status_code == 201
    assert resp.json()["nome"] == "Obra Teste"


def test_atualizar_obra_found(client_with_auth):
    client, db = client_with_auth
    updated = {**OBRA_FIXTURE, "status": "concluida"}
    db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [updated]

    resp = client.patch("/api/v1/obras/obra-1", json={"status": "concluida"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "concluida"


def test_atualizar_obra_not_found(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []

    resp = client.patch("/api/v1/obras/nao-existe", json={"status": "concluida"})

    assert resp.status_code == 404


def test_deletar_obra(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

    resp = client.delete("/api/v1/obras/obra-1")

    assert resp.status_code == 204


# ── Contratos ──────────────────────────────────────────────────────────────────

CONTRATO_FIXTURE = {"id": "cont-1", "obra_id": "obra-1", "valor": 50000.0}


def test_listar_contratos(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.execute.return_value.data = [CONTRATO_FIXTURE]

    resp = client.get("/api/v1/contratos/")

    assert resp.status_code == 200


def test_obter_contrato_found(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [CONTRATO_FIXTURE]

    resp = client.get("/api/v1/contratos/cont-1")

    assert resp.status_code == 200
    assert resp.json()["id"] == "cont-1"


def test_obter_contrato_not_found(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    resp = client.get("/api/v1/contratos/nao-existe")

    assert resp.status_code == 404


def test_contratos_por_obra(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [CONTRATO_FIXTURE]

    resp = client.get("/api/v1/contratos/obra/obra-1")

    assert resp.status_code == 200


# ── Dashboard ─────────────────────────────────────────────────────────────────

def test_resumo_dashboard(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.execute.return_value.data = [
        {"id": "o1", "status": "em_andamento", "valor_contrato": 100000.0},
        {"id": "o2", "status": "concluida", "valor_contrato": 50000.0},
    ]

    resp = client.get("/api/v1/dashboard/resumo")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_obras"] == 2
    assert body["em_andamento"] == 1
    assert body["concluidas"] == 1
    assert body["valor_total_contratos"] == 150000.0


def test_ranking_eficiencia(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"obra_id": "o1", "score_eficiencia": 0.95}
    ]

    resp = client.get("/api/v1/dashboard/eficiencia")

    assert resp.status_code == 200


# Espelha a view real mv_dashboard_geral
DASHBOARD_FIXTURE = {
    "total_obras": 42,
    "valor_total_contratos": 5_000_000.0,
    "media_execucao": 67.5,
    "obras_em_andamento": 30,
    "obras_concluidas": 10,
    "obras_paralisadas": 2,
    "media_dias_atraso": 12.0,
    "atualizado_em": "2026-05-07T02:25:07+00:00",
}


def test_metricas_globais(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.execute.return_value.data = [DASHBOARD_FIXTURE]
    # 2ª query: contagem de obras atrasadas (dias_atraso > 0)
    db.table.return_value.select.return_value.gt.return_value.execute.return_value.count = 7

    resp = client.get("/api/v1/dashboard/")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_obras"] == 42
    assert body["valor_total"] == 5_000_000.0
    assert body["media_execucao_pct"] == 67.5
    assert body["obras_atrasadas"] == 7


def test_metricas_globais_sem_dados(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.execute.return_value.data = []

    resp = client.get("/api/v1/dashboard/")

    assert resp.status_code == 503


def test_distribuicao_status(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.execute.return_value.data = [
        {"status": "em_andamento", "valor_contrato": 100_000.0},
        {"status": "em_andamento", "valor_contrato": 80_000.0},
        {"status": "concluida", "valor_contrato": 50_000.0},
    ]

    resp = client.get("/api/v1/dashboard/distribuicao-status")

    assert resp.status_code == 200
    items = {i["label"]: i for i in resp.json()}
    assert items["em_andamento"]["quantidade"] == 2
    assert items["em_andamento"]["valor_total"] == 180_000.0
    assert items["concluida"]["quantidade"] == 1


def test_distribuicao_status_campo_nulo(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.execute.return_value.data = [
        {"status": None, "valor_contrato": 10_000.0},
    ]

    resp = client.get("/api/v1/dashboard/distribuicao-status")

    assert resp.status_code == 200
    assert resp.json()[0]["label"] == "indefinido"


def test_distribuicao_secretaria(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.execute.return_value.data = [
        {"secretaria": "Infraestrutura", "valor_contrato": 200_000.0},
        {"secretaria": "Infraestrutura", "valor_contrato": 100_000.0},
        {"secretaria": None, "valor_contrato": 50_000.0},
    ]

    resp = client.get("/api/v1/dashboard/distribuicao-secretaria")

    assert resp.status_code == 200
    items = {i["label"]: i for i in resp.json()}
    assert items["Infraestrutura"]["quantidade"] == 2
    assert items["Não informado"]["quantidade"] == 1


def test_evolucao_mensal(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.execute.return_value.data = [
        {"data_inicio": "2026-01-15", "status": "em_andamento"},
        {"data_inicio": "2026-01-20", "status": "concluida"},
        {"data_inicio": "2026-02-05", "status": "em_andamento"},
        {"data_inicio": None, "status": "em_andamento"},
    ]

    resp = client.get("/api/v1/dashboard/evolucao")

    assert resp.status_code == 200
    items = {i["mes"]: i for i in resp.json()}
    assert items["2026-01"]["iniciadas"] == 2
    assert items["2026-01"]["concluidas"] == 1
    assert items["2026-02"]["iniciadas"] == 1
    assert items["2026-02"]["concluidas"] == 0
    assert "None" not in items


def test_evolucao_mensal_ordenada(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.execute.return_value.data = [
        {"data_inicio": "2026-03-01", "status": "em_andamento"},
        {"data_inicio": "2026-01-01", "status": "concluida"},
        {"data_inicio": "2026-02-01", "status": "em_andamento"},
    ]

    resp = client.get("/api/v1/dashboard/evolucao")

    meses = [i["mes"] for i in resp.json()]
    assert meses == sorted(meses)


def test_alertas(client_with_auth):
    client, db = client_with_auth
    alerta = {
        "id": "obra-2",
        "nome": "Obra Crítica",
        "nivel_risco": "critico",
        "secretaria": "Infraestrutura",
        "bairro": "Centro",
        "valor_contrato": 500_000.0,
        "data_prevista_fim": "2026-03-01",
    }
    (
        db.table.return_value.select.return_value
        .in_.return_value.order.return_value.limit.return_value.execute.return_value.data
    ) = [alerta]

    resp = client.get("/api/v1/dashboard/alertas")

    assert resp.status_code == 200
    assert resp.json()[0]["nivel_risco"] == "critico"


def test_alertas_vazio(client_with_auth):
    client, db = client_with_auth
    (
        db.table.return_value.select.return_value
        .in_.return_value.order.return_value.limit.return_value.execute.return_value.data
    ) = []

    resp = client.get("/api/v1/dashboard/alertas")

    assert resp.status_code == 200
    assert resp.json() == []


def test_alertas_limit(client_with_auth):
    client, db = client_with_auth
    (
        db.table.return_value.select.return_value
        .in_.return_value.order.return_value.limit.return_value.execute.return_value.data
    ) = []

    resp = client.get("/api/v1/dashboard/alertas?limit=5")

    assert resp.status_code == 200


# ── Fornecedores ──────────────────────────────────────────────────────────────

FORNECEDOR_FIXTURE = {
    "cnpj": "12345678000195",
    "nome": "Fornecedor A",
    "total_contratos": 5,
    "valor_total": 500_000.0,
    "taxa_aditivo": 0.1,
    "media_prob_atraso": 0.2,
    "obras_concluidas": 3,
    "obras_em_andamento": 2,
}


def _mock_ranking(db, data, total=None):
    mock_result = MagicMock()
    mock_result.data = data
    mock_result.count = total if total is not None else len(data)
    chain = db.table.return_value.select.return_value
    # sem filtros: select().order().range().execute()
    chain.order.return_value.range.return_value.execute.return_value = mock_result
    # com lte: select().lte().order().range().execute()
    chain.lte.return_value.order.return_value.range.return_value.execute.return_value = mock_result
    # com dois lte: select().lte().lte().order().range().execute()
    chain.lte.return_value.lte.return_value.order.return_value.range.return_value.execute.return_value = mock_result


def test_listar_fornecedores(client_with_auth):
    client, db = client_with_auth
    _mock_ranking(db, [FORNECEDOR_FIXTURE], total=1)

    resp = client.get("/api/v1/fornecedores/")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["items"][0]["cnpj"] == "12345678000195"


def test_listar_fornecedores_filtro_taxa_aditivo(client_with_auth):
    client, db = client_with_auth
    _mock_ranking(db, [FORNECEDOR_FIXTURE], total=1)

    resp = client.get("/api/v1/fornecedores/?taxa_aditivo_max=0.2")

    assert resp.status_code == 200


def test_listar_fornecedores_filtro_prob_atraso(client_with_auth):
    client, db = client_with_auth
    _mock_ranking(db, [FORNECEDOR_FIXTURE], total=1)

    resp = client.get("/api/v1/fornecedores/?media_prob_atraso_max=0.3")

    assert resp.status_code == 200


def test_listar_fornecedores_filtros_combinados(client_with_auth):
    client, db = client_with_auth
    _mock_ranking(db, [FORNECEDOR_FIXTURE], total=1)

    resp = client.get("/api/v1/fornecedores/?taxa_aditivo_max=0.2&media_prob_atraso_max=0.3")

    assert resp.status_code == 200


def test_listar_fornecedores_paginacao(client_with_auth):
    client, db = client_with_auth
    _mock_ranking(db, [FORNECEDOR_FIXTURE], total=40)

    resp = client.get("/api/v1/fornecedores/?page=2&size=10")

    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 2
    assert body["size"] == 10
    assert body["total"] == 40
    assert body["pages"] == 4


def test_obter_fornecedor_found(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [FORNECEDOR_FIXTURE]

    resp = client.get("/api/v1/fornecedores/12345678000195")

    assert resp.status_code == 200
    assert resp.json()["cnpj"] == "12345678000195"
    assert resp.json()["nome"] == "Fornecedor A"
    assert resp.json()["total_contratos"] == 5


def test_obter_fornecedor_not_found(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    resp = client.get("/api/v1/fornecedores/99999999000199")

    assert resp.status_code == 404


def test_obras_do_fornecedor(client_with_auth):
    client, db = client_with_auth
    obra_ref = {"obra_id": "obra-1", "obras": {"id": "obra-1", "nome": "Obra A", "status": "em_andamento"}}
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [obra_ref]

    resp = client.get("/api/v1/fornecedores/12345678000195/obras")

    assert resp.status_code == 200
    assert resp.json()[0]["obra_id"] == "obra-1"


def test_obras_do_fornecedor_vazio(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    resp = client.get("/api/v1/fornecedores/99999999000199/obras")

    assert resp.status_code == 200
    assert resp.json() == []


# ── Mapa ──────────────────────────────────────────────────────────────────────

def test_obras_geolocalizadas(client_with_auth):
    client, db = client_with_auth
    geo_data = [{**OBRA_FIXTURE, "latitude": -22.37, "longitude": -41.78}]
    (db.table.return_value.select.return_value
     .not_.is_.return_value.not_.is_.return_value.execute.return_value.data) = geo_data

    resp = client.get("/api/v1/mapa/obras")

    assert resp.status_code == 200


# ── ML ────────────────────────────────────────────────────────────────────────

def test_disparar_analise(client_with_auth):
    client, _ = client_with_auth
    with patch("app.routers.ml.run_ml_analysis") as mock_task:
        mock_task.delay.return_value.id = "task-abc"

        resp = client.post("/api/v1/ml/analisar", json={"obra_id": "obra-1"})

    assert resp.status_code == 200
    assert resp.json()["task_id"] == "task-abc"
    assert resp.json()["status"] == "queued"


PREDICAO_FIXTURE = {
    "id": "pred-1",
    "id_obra": "obra-1",
    "prob_atraso": 0.72,
    "prob_estouro": 0.31,
    "nivel_risco": "alto",
    "modelo_versao": "v1.2.0",
    "atualizado_em": "2026-05-01T12:00:00",
}


def test_listar_predicoes(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.execute.return_value.data = [PREDICAO_FIXTURE]

    resp = client.get("/api/v1/ml/predicoes")

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["id_obra"] == "obra-1"
    assert body[0]["nivel_risco"] == "alto"


def test_listar_predicoes_filtro_nivel_risco(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        PREDICAO_FIXTURE
    ]

    resp = client.get("/api/v1/ml/predicoes?nivel_risco=alto")

    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_obter_predicao_found(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        PREDICAO_FIXTURE
    ]

    resp = client.get("/api/v1/ml/predicoes/obra-1")

    assert resp.status_code == 200
    assert resp.json()["prob_atraso"] == 0.72


def test_obter_predicao_not_found(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    resp = client.get("/api/v1/ml/predicoes/inexistente")

    assert resp.status_code == 404


def test_reprocessar_modelo(client_with_auth):
    client, _ = client_with_auth
    with patch("app.routers.ml.run_ml_retraining") as mock_task:
        mock_task.delay.return_value.id = "retrain-1"

        resp = client.post("/api/v1/ml/reprocessar")

    assert resp.status_code == 200
    assert resp.json()["task_id"] == "retrain-1"
    assert resp.json()["status"] == "queued"


def test_status_task(client_with_auth):
    client, _ = client_with_auth
    with patch("app.routers.ml.celery_app.AsyncResult") as mock_ar:
        inst = mock_ar.return_value
        inst.status = "SUCCESS"
        inst.successful.return_value = True
        inst.result = {"status": "completed"}

        resp = client.get("/api/v1/ml/status/retrain-1")

    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCESS"
    assert resp.json()["resultado"] == {"status": "completed"}


def _override_perfil(perfil: str):
    """Sobrescreve get_current_user para simular um usuário com dado perfil."""
    from app.main import app
    from app.routers.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "u", "email": "u@test.com", "perfil": perfil
    }


def test_reprocessar_readonly_403(client_with_auth):
    client, _ = client_with_auth
    _override_perfil("readonly")

    resp = client.post("/api/v1/ml/reprocessar")

    assert resp.status_code == 403


def test_reprocessar_gestor_403(client_with_auth):
    client, _ = client_with_auth
    _override_perfil("gestor")

    resp = client.post("/api/v1/ml/reprocessar")

    assert resp.status_code == 403


# ── IA ────────────────────────────────────────────────────────────────────────

def test_consultar_ia(client_with_auth):
    from unittest.mock import AsyncMock
    from app.schemas.ml import RAGResponse

    client, _ = client_with_auth
    with patch("app.routers.ia.RAGService") as mock_service_cls:
        mock_service_cls.return_value.query = AsyncMock(
            return_value=RAGResponse(
                resposta="A obra está dentro do prazo.",
                fontes=[{"conteudo": "trecho", "metadata": {"id_contrato": "c1"}}],
            )
        )
        resp = client.post("/api/v1/ia/consulta", json={"pergunta": "Qual a eficiência da obra?"})

    assert resp.status_code == 200
    assert resp.json()["resposta"] == "A obra está dentro do prazo."
    assert resp.json()["fontes"][0]["metadata"]["id_contrato"] == "c1"


def test_consultar_ia_readonly_403(client_with_auth):
    client, _ = client_with_auth
    _override_perfil("readonly")

    resp = client.post("/api/v1/ia/consulta", json={"pergunta": "Qualquer pergunta?"})

    assert resp.status_code == 403


def test_consultar_ia_gestor_ok(client_with_auth):
    from unittest.mock import AsyncMock
    from app.schemas.ml import RAGResponse

    client, _ = client_with_auth
    _override_perfil("gestor")
    with patch("app.routers.ia.RAGService") as mock_service_cls:
        mock_service_cls.return_value.query = AsyncMock(
            return_value=RAGResponse(resposta="ok", fontes=[])
        )
        resp = client.post("/api/v1/ia/consulta", json={"pergunta": "Pergunta do gestor?"})

    assert resp.status_code == 200


def test_consultar_ia_stream(client_with_auth):
    client, _ = client_with_auth

    async def fake_stream(pergunta, obra_id=None, top_k=5):
        for token in ["Olá", " mundo"]:
            yield token

    with patch("app.routers.ia.RAGService") as mock_service_cls:
        mock_service_cls.return_value.stream = fake_stream
        resp = client.get("/api/v1/ia/consulta/stream?pergunta=teste")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert '"token": "Olá"' in resp.text
    assert "[DONE]" in resp.text


def test_gerar_embeddings(client_with_auth):
    client, _ = client_with_auth
    with patch("app.routers.ia.generate_embeddings") as mock_task:
        mock_task.delay.return_value.id = "emb-task-1"

        resp = client.post("/api/v1/ia/embeddings/gerar", json={
            "documento_id": "doc-1", "texto": "Texto do documento"
        })

    assert resp.status_code == 200
    assert resp.json()["task_id"] == "emb-task-1"
