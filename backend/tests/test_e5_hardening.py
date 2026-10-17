# -*- coding: utf-8 -*-
"""task-E5 安全与健壮性验收测试。"""
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from app.main import _cors_origins
from app.services import data_service
from app.services.auth_service import USERS_FILE, register_user


def _upload_file(client, headers, name, content, content_type="text/csv"):
    return client.post(
        "/api/datasets/upload",
        files={"file": (name, content, content_type)},
        headers=headers,
    )


def _restart_csv(rows=80):
    lines = ["x1,x2,y"]
    for i in range(rows):
        lines.append(f"{i},{i % 13},{i % 2}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _user_count():
    if not os.path.exists(USERS_FILE):
        return 0
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return len(json.load(f))


def test_upload_60mb_returns_413(client, auth_headers):
    """验收 1：上传 60MB 文件返回 413（默认 EASYR_MAX_UPLOAD_MB=50）。"""
    payload = b"a,b\n" + b"1,2\n" * (60 * 1024 * 1024 // 4)
    assert len(payload) >= 60 * 1024 * 1024

    response = _upload_file(client, auth_headers, "too_big.csv", payload)

    assert response.status_code == 413, response.text
    assert "大小限制" in response.json()["detail"]


def test_concurrent_registration_keeps_all_20_users():
    """验收 2：20 个线程并发注册不同用户，users.json 里 20 个都在。"""
    before = _user_count()
    tag = uuid.uuid4().hex[:8]
    usernames = [f"conc_{tag}_{i}" for i in range(20)]

    with ThreadPoolExecutor(max_workers=20) as pool:
        list(pool.map(lambda name: register_user(name, "password123"), usernames))

    with open(USERS_FILE, "r", encoding="utf-8") as f:
        users = json.load(f)

    stored = {user["username"] for user in users}
    assert set(usernames).issubset(stored)
    assert len(users) == before + 20


def test_ml_succeeds_after_cache_clear(client, auth_headers):
    """验收 3：上传数据集 → 清空进程内缓存（模拟重启）→ ML 接口仍成功。"""
    upload = _upload_file(client, auth_headers, "restart.csv", _restart_csv())
    assert upload.status_code == 200, upload.text
    dataset_id = upload.json()["id"]

    # 模拟服务重启：数据集与元信息缓存都被清空
    data_service._datasets.clear()
    data_service._dataset_meta.clear()

    # 前端重启后通常先拉数据集列表：它只恢复 meta，不恢复数据本身
    listed = client.get("/api/datasets", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == dataset_id for item in listed.json())
    assert dataset_id not in data_service._datasets

    response = client.post(
        "/api/ml/logistic",
        json={
            "dataset_id": dataset_id,
            "y_variable": "y",
            "x_variables": ["x1", "x2"],
            "variable_types": {"y": "logical"},
            "seed": 123,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


def test_cors_origins_default_is_empty(monkeypatch):
    """D2：CORS 白名单默认留空（生产经 nginx 同源访问）。"""
    monkeypatch.delenv("EASYR_CORS_ORIGINS", raising=False)
    assert _cors_origins() == []


def test_cors_origins_read_from_env(monkeypatch):
    """D2：CORS 白名单由环境变量配置，逗号分隔并去空白。"""
    monkeypatch.setenv(
        "EASYR_CORS_ORIGINS",
        "https://app.example.org, http://localhost:5173",
    )
    assert _cors_origins() == [
        "https://app.example.org",
        "http://localhost:5173",
    ]
