from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_health_ok():
    with patch("app.main.init_db_engine"), \
         patch("app.main.dispose_db_engine", new=AsyncMock()), \
         patch(
             "app.main.check_connection",
             new=AsyncMock(return_value={"supabase": True, "database": True}),
         ):
        from app.main import app
        with TestClient(app) as client:
            response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"] == "connected"


def test_health_degraded():
    with patch("app.main.init_db_engine"), \
         patch("app.main.dispose_db_engine", new=AsyncMock()), \
         patch(
             "app.main.check_connection",
             new=AsyncMock(return_value={"supabase": True, "database": False}),
         ):
        from app.main import app
        with TestClient(app) as client:
            response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["database"] == "error"
