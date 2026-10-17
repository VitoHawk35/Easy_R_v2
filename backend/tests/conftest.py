import atexit
import os
import shutil
import sys
import tempfile
import uuid

import pytest
from fastapi.testclient import TestClient

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="easyr-test-data-")
os.environ["EASYR_DATA_DIR"] = _TEST_DATA_DIR
os.environ["EASYR_AUTH_SECRET"] = "test-secret"
os.environ["MPLBACKEND"] = "Agg"
atexit.register(lambda: shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True))

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    username = f"test_{uuid.uuid4().hex}"
    password = "test-password-123"

    register_response = client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    assert register_response.status_code == 200, register_response.text

    login_response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def ml_request():
    def _payload(**overrides):
        payload = {
            "dataset_id": "demo",
            "y_variable": "结局Y1",
            "x_variables": ["年龄", "性别", "白细胞", "血红蛋白", "BMI", "吸烟"],
            "seed": 123,
        }
        payload.update(overrides)
        return payload

    return _payload
