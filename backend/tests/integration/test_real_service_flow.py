import os
import time
import uuid

import pytest
import requests


pytestmark = pytest.mark.integration


API_BASE_URL = os.getenv("BP_API_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")
REQUEST_TIMEOUT = float(os.getenv("BP_API_TIMEOUT", "20"))


def api_url(path: str) -> str:
    return f"{API_BASE_URL}{path}"


def wait_for_backend() -> None:
    deadline = time.time() + float(os.getenv("BP_API_WAIT_SECONDS", "60"))
    last_error = None
    while time.time() < deadline:
        try:
            response = requests.get(api_url("/health"), timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                return
            last_error = f"status={response.status_code}, body={response.text[:200]}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(2)
    pytest.fail(f"后端服务未就绪: {last_error}")


def assert_success(response: requests.Response) -> dict:
    assert response.status_code < 400, response.text
    payload = response.json()
    assert payload.get("success") is True, payload
    return payload.get("data") or {}


def test_real_docker_flow_register_login_mock_predict_history_query():
    wait_for_backend()

    suffix = uuid.uuid4().hex[:8]
    username = f"itest_{suffix}"
    email = f"{username}@example.com"
    password = "password123"

    register_response = requests.post(
        api_url("/auth/register"),
        json={"username": username, "email": email, "password": password},
        timeout=REQUEST_TIMEOUT,
    )
    assert_success(register_response)

    login_response = requests.post(
        api_url("/auth/login"),
        json={"username": username, "password": password},
        timeout=REQUEST_TIMEOUT,
    )
    login_data = assert_success(login_response)
    token = login_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    options_response = requests.get(api_url("/prediction/mock/options"), headers=headers, timeout=REQUEST_TIMEOUT)
    options_data = assert_success(options_response)
    assert len(options_data["items"]) == 20

    predict_response = requests.post(
        api_url("/prediction/mock"),
        json={"mock_id": "mock_001"},
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    prediction = assert_success(predict_response)
    record_id = prediction["record_id"]
    assert isinstance(record_id, int)
    assert prediction["sbp"] is not None
    assert prediction["dbp"] is not None

    detail_response = requests.get(api_url(f"/prediction/{record_id}"), headers=headers, timeout=REQUEST_TIMEOUT)
    detail = assert_success(detail_response)
    assert detail["record_id"] == record_id
    assert len(detail["raw_signal"]) == 1250

    similar_response = requests.get(api_url(f"/prediction/{record_id}/similar"), headers=headers, timeout=REQUEST_TIMEOUT)
    similar = assert_success(similar_response)
    assert similar["record_id"] == record_id
    assert "similar_samples" in similar

    records_response = requests.get(api_url("/records"), headers=headers, timeout=REQUEST_TIMEOUT)
    records = assert_success(records_response)
    assert records["total"] >= 1
    assert any(item["id"] == record_id for item in records["items"])
