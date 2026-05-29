import geojson
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

FAKE_USER = {"sub": "test-uid", "email": "test@example.com"}

OBRA_GEO = {
    "id": "obra-1",
    "nome": "Obra Teste",
    "situacao": "Em andamento",
    "nivel_risco": "alto",
    "bairro": "Centro",
    "valor_contrato": 100_000.0,
    "latitude": -22.37,
    "longitude": -41.78,
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


def _mock_geo(db, data):
    chain = (
        db.table.return_value.select.return_value
        .not_.is_.return_value.not_.is_.return_value
    )
    chain.execute.return_value.data = data
    chain.eq.return_value.execute.return_value.data = data
    chain.eq.return_value.eq.return_value.execute.return_value.data = data


# ── estrutura GeoJSON ─────────────────────────────────────────────────────────

def test_retorna_feature_collection(client_with_auth):
    client, db = client_with_auth
    _mock_geo(db, [OBRA_GEO])

    resp = client.get("/api/v1/mapa/")

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert "features" in body


def test_geojson_valido(client_with_auth):
    client, db = client_with_auth
    _mock_geo(db, [OBRA_GEO])

    resp = client.get("/api/v1/mapa/")

    fc = geojson.loads(resp.text)
    assert isinstance(fc, geojson.FeatureCollection)
    assert all(isinstance(f, geojson.Feature) for f in fc["features"])
    assert all(isinstance(f["geometry"], geojson.Point) for f in fc["features"])


def test_feature_tem_geometry_e_properties(client_with_auth):
    client, db = client_with_auth
    _mock_geo(db, [OBRA_GEO])

    resp = client.get("/api/v1/mapa/")
    feature = resp.json()["features"][0]

    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    assert len(feature["geometry"]["coordinates"]) == 2
    assert feature["properties"]["id"] == "obra-1"
    assert feature["properties"]["nome"] == "Obra Teste"


def test_coordinates_ordem_lon_lat(client_with_auth):
    """GeoJSON/Leaflet exige [longitude, latitude]."""
    client, db = client_with_auth
    _mock_geo(db, [OBRA_GEO])

    resp = client.get("/api/v1/mapa/")
    coords = resp.json()["features"][0]["geometry"]["coordinates"]

    assert coords[0] == OBRA_GEO["longitude"]
    assert coords[1] == OBRA_GEO["latitude"]


def test_properties_campos_necessarios(client_with_auth):
    client, db = client_with_auth
    _mock_geo(db, [OBRA_GEO])

    resp = client.get("/api/v1/mapa/")
    props = resp.json()["features"][0]["properties"]

    assert "id" in props
    assert "nome" in props
    assert "status" in props
    assert "nivel_risco" in props
    assert "secretaria" in props
    assert "bairro" in props
    assert "valor_contrato" in props


def test_resultado_vazio_feature_collection_valida(client_with_auth):
    client, db = client_with_auth
    _mock_geo(db, [])

    resp = client.get("/api/v1/mapa/")

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"] == []

    fc = geojson.loads(resp.text)
    assert isinstance(fc, geojson.FeatureCollection)
    assert fc["features"] == []


def test_multiplas_features(client_with_auth):
    client, db = client_with_auth
    segunda = {**OBRA_GEO, "id": "obra-2", "latitude": -22.40, "longitude": -41.80}
    _mock_geo(db, [OBRA_GEO, segunda])

    resp = client.get("/api/v1/mapa/")

    features = resp.json()["features"]
    assert len(features) == 2

    fc = geojson.loads(resp.text)
    assert isinstance(fc, geojson.FeatureCollection)
    assert len(fc["features"]) == 2


# ── filtros ───────────────────────────────────────────────────────────────────

def test_filtro_status(client_with_auth):
    client, db = client_with_auth
    _mock_geo(db, [OBRA_GEO])

    resp = client.get("/api/v1/mapa/?status=em_andamento")

    assert resp.status_code == 200
    assert resp.json()["type"] == "FeatureCollection"


def test_filtro_nivel_risco(client_with_auth):
    client, db = client_with_auth
    _mock_geo(db, [OBRA_GEO])

    resp = client.get("/api/v1/mapa/?nivel_risco=alto")

    assert resp.status_code == 200
    assert resp.json()["type"] == "FeatureCollection"


def _mock_geo_por_ids(db, ids, data):
    """Mocka o two-step: lookup de IDs na tabela obras + mv_mapa_obras via in_()."""
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": i} for i in ids
    ]
    db.table.return_value.select.return_value.gte.return_value.lte.return_value.execute.return_value.data = [
        {"id": i} for i in ids
    ]
    (
        db.table.return_value.select.return_value.not_.is_.return_value.not_.is_.return_value
        .in_.return_value.execute.return_value.data
    ) = data


def test_filtro_secretaria(client_with_auth):
    client, db = client_with_auth
    _mock_geo_por_ids(db, ["obra-1"], [OBRA_GEO])

    resp = client.get("/api/v1/mapa/?secretaria=Infraestrutura")

    assert resp.status_code == 200
    assert len(resp.json()["features"]) == 1
    db.table.return_value.select.return_value.eq.assert_called_with("secretaria", "Infraestrutura")


def test_filtro_periodo(client_with_auth):
    client, db = client_with_auth
    _mock_geo_por_ids(db, ["obra-1"], [OBRA_GEO])

    resp = client.get("/api/v1/mapa/?data_inicio=2026-04-01&data_fim=2026-05-29")

    assert resp.status_code == 200
    assert len(resp.json()["features"]) == 1


def test_filtro_periodo_sem_resultados(client_with_auth):
    client, db = client_with_auth
    db.table.return_value.select.return_value.gte.return_value.lte.return_value.execute.return_value.data = []

    resp = client.get("/api/v1/mapa/?data_inicio=2026-04-01&data_fim=2026-05-29")

    assert resp.status_code == 200
    assert resp.json()["features"] == []


def test_filtros_combinados(client_with_auth):
    client, db = client_with_auth
    _mock_geo(db, [OBRA_GEO])

    resp = client.get("/api/v1/mapa/?status=em_andamento&nivel_risco=alto")

    assert resp.status_code == 200

    fc = geojson.loads(resp.text)
    assert isinstance(fc, geojson.FeatureCollection)
