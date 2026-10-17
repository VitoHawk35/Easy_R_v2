# -*- coding: utf-8 -*-
"""task-E1：报告下载安全回归测试。"""
import os
import re
import uuid

import pytest
from fastapi import HTTPException

from app.services import auth_service
from app.services.data_service import DATA_DIR
from app.services.report_service import get_user_reports_dir


def _register(client, prefix="user"):
    username = f"{prefix}_{uuid.uuid4().hex}"
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "test-password-123"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    headers = {"Authorization": f"Bearer {body['token']}"}
    return headers, body["token"], body["user"]["id"]


@pytest.mark.parametrize("path", [
    "/api/report/download/auth_secret.txt",
    "/api/report/download/../auth_secret.txt",
    "/api/report/download/%2e%2e%2fauth_secret.txt",
])
def test_secret_file_cannot_be_downloaded(client, path):
    """任何登录用户都不能通过下载接口拿到签名密钥。"""
    headers, _, _ = _register(client, "secret")
    response = client.get(path, headers=headers)
    assert response.status_code == 404, response.text


def test_secret_file_not_in_data_dir():
    """密钥文件不再位于 DATA_DIR（原漏洞位置）。"""
    assert not os.path.exists(os.path.join(DATA_DIR, "auth_secret.txt"))


def test_default_secret_file_outside_data_dir(monkeypatch):
    """默认密钥路径必须在 DATA_DIR 之外。"""
    monkeypatch.delenv("EASYR_SECRET_FILE", raising=False)
    secret_path = auth_service._secret_file_path()
    assert not secret_path.startswith(os.path.realpath(DATA_DIR) + os.sep)


def test_token_is_signed_with_env_secret(client, monkeypatch):
    """设置 EASYR_AUTH_SECRET 后 token 用它签名；换密钥后旧 token 验签失败。"""
    headers, token, user_id = _register(client, "signed")

    assert auth_service.verify_token(token).id == user_id
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    monkeypatch.setenv("EASYR_AUTH_SECRET", "rotated-secret-for-test")
    with pytest.raises(HTTPException) as exc_info:
        auth_service.verify_token(token)
    assert exc_info.value.status_code == 401
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_secret_file_fallback_creates_private_file(monkeypatch, tmp_path):
    """未设置 EASYR_AUTH_SECRET 时，按 EASYR_SECRET_FILE 生成并复用密钥文件。"""
    monkeypatch.delenv("EASYR_AUTH_SECRET", raising=False)
    target = tmp_path / "secrets" / "auth_secret.txt"
    monkeypatch.setenv("EASYR_SECRET_FILE", str(target))

    first = auth_service._get_secret()
    assert target.exists()
    assert first
    assert auth_service._get_secret() == first
    assert not os.path.exists(os.path.join(DATA_DIR, "auth_secret.txt"))
    if os.name != "nt":
        assert (target.stat().st_mode & 0o777) == 0o600


def test_report_download_is_owner_only(client):
    """A 的报告：B 下载 404；A 下载 200 且 Content-Type 正确。"""
    headers_a, _, user_a_id = _register(client, "owner")
    headers_b, _, _ = _register(client, "other")

    generated = client.post(
        "/api/report/generate",
        json={"format": "word", "sections": []},
        headers=headers_a,
    )
    assert generated.status_code == 200, generated.text
    filename = generated.json()["filename"]
    assert re.fullmatch(r"report_[0-9]{14}_[A-Za-z0-9_-]{16}\.docx", filename)

    # 报告只落在 A 自己的 reports 目录
    expected_path = os.path.join(get_user_reports_dir(user_a_id), filename)
    assert os.path.isfile(expected_path)

    forbidden = client.get(f"/api/report/download/{filename}", headers=headers_b)
    assert forbidden.status_code == 404

    allowed = client.get(f"/api/report/download/{filename}", headers=headers_a)
    assert allowed.status_code == 200
    assert allowed.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert allowed.content[:2] == b"PK"  # docx (zip) 文件头


def test_legacy_report_in_data_root_not_downloadable(client):
    """DATA_DIR 根目录下的旧式报告（时间戳可猜）不再可下载。"""
    headers, _, _ = _register(client, "legacy")
    legacy_name = "report_1700000000.docx"
    with open(os.path.join(DATA_DIR, legacy_name), "wb") as f:
        f.write(b"legacy")

    response = client.get(f"/api/report/download/{legacy_name}", headers=headers)
    assert response.status_code == 404
