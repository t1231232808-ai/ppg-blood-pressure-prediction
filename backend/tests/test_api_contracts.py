from fastapi.testclient import TestClient

from app.main import app
from app.models.database import get_db
from app.models.entities import User
from app.routers import prediction as prediction_router
from app.utils.auth import get_current_user


class DummyDb:
    def scalar(self, *_args, **_kwargs):
        return None


def override_db():
    yield DummyDb()


def override_user():
    return User(id=1, username="tester", email="tester@example.com", role="user", status=1, password_hash="")


def setup_module():
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user


def teardown_module():
    app.dependency_overrides.clear()


def test_auth_login_invalid_credentials_returns_401():
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"username": "missing", "password": "bad"})
    assert response.status_code == 401


def test_mock_options_returns_predefined_samples():
    client = TestClient(app)
    response = client.get("/api/v1/prediction/mock/options")
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 20
    assert items[0]["mock_id"] == "mock_001"


def test_mock_prediction_persists_and_returns_record_id(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(prediction_router, "encode_vector", lambda signal: [0.0] * 128)
    monkeypatch.setattr(
        prediction_router,
        "run_prediction",
        lambda vector, source_filter=None: {
            "sbp": 120,
            "dbp": 78,
            "confidence": 0.88,
            "explanation": "ok",
            "similar_samples": [{"id": 1, "distance": 0.1, "sbp": 120, "dbp": 78, "source": "mock"}],
            "weights": [1.0],
            "workflow_trace": [],
        },
    )
    monkeypatch.setattr(prediction_router, "_persist_prediction", lambda *args, **kwargs: 101)

    response = client.post("/api/v1/prediction/mock", json={"mock_id": "mock_001"})

    assert response.status_code == 200
    assert response.json()["data"]["record_id"] == 101


def test_milvus_not_initialized_error_message(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(prediction_router, "encode_vector", lambda signal: [0.0] * 128)
    monkeypatch.setattr(
        prediction_router,
        "run_prediction",
        lambda vector, source_filter=None: {"error": "特征库为空，未找到相似样本，请联系管理员初始化数据"},
    )

    response = client.post("/api/v1/prediction/mock", json={"mock_id": "mock_001"})

    assert response.status_code == 422
    assert "特征库为空" in response.json()["detail"]
