import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.schemas import UserPublic
from app.services.data_service import DATA_DIR

USERS_DIR = os.path.join(DATA_DIR, "users")
USERS_FILE = os.path.join(USERS_DIR, "users.json")
# 密钥文件默认放在 DATA_DIR 之外，避免通过任何 DATA_DIR 下的下载接口泄露。
_DEFAULT_SECRET_FILE = os.path.abspath(os.path.join(DATA_DIR, os.pardir, "secrets", "auth_secret.txt"))
SECRET_FILE = os.getenv("EASYR_SECRET_FILE", _DEFAULT_SECRET_FILE)
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
security = HTTPBearer()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _secret_file_path() -> str:
    """运行时解析密钥文件路径，便于 EASYR_SECRET_FILE 覆盖。"""
    return os.path.abspath(os.getenv("EASYR_SECRET_FILE") or SECRET_FILE)


def _ensure_storage() -> None:
    os.makedirs(USERS_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        _atomic_write_json(USERS_FILE, [])


def _atomic_write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _load_users() -> list[Dict[str, Any]]:
    _ensure_storage()
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: list[Dict[str, Any]]) -> None:
    _atomic_write_json(USERS_FILE, users)


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return base64.urlsafe_b64encode(digest).decode("utf-8")


def _public_user(user: Dict[str, Any]) -> UserPublic:
    return UserPublic(id=user["id"], username=user["username"], created_at=user["created_at"])


def _get_secret() -> bytes:
    """签名密钥：优先 EASYR_AUTH_SECRET，否则读取/生成 EASYR_SECRET_FILE。"""
    env_secret = os.getenv("EASYR_AUTH_SECRET")
    if env_secret:
        return env_secret.encode("utf-8")

    _ensure_storage()
    secret_file = _secret_file_path()
    if not os.path.exists(secret_file):
        os.makedirs(os.path.dirname(secret_file), exist_ok=True)
        try:
            fd = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass  # 并发启动时另一个进程已创建
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(secrets.token_urlsafe(48))
            try:
                os.chmod(secret_file, 0o600)
            except OSError:
                pass
    with open(secret_file, "r", encoding="utf-8") as f:
        return f.read().strip().encode("utf-8")


def _sign(payload: str) -> str:
    return hmac.new(_get_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _encode_payload(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _decode_payload(encoded: str) -> Dict[str, Any]:
    padded = encoded + "=" * (-len(encoded) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))


def create_token(user: Dict[str, Any]) -> str:
    payload = _encode_payload({
        "user_id": user["id"],
        "username": user["username"],
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    })
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str) -> UserPublic:
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="无效登录凭证")
    if not hmac.compare_digest(_sign(payload), signature):
        raise HTTPException(status_code=401, detail="无效登录凭证")
    data = _decode_payload(payload)
    if int(data.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    users = _load_users()
    user = next((u for u in users if u["id"] == data.get("user_id")), None)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return _public_user(user)


def register_user(username: str, password: str) -> tuple[str, UserPublic]:
    normalized = _normalize_username(username)
    if len(normalized) < 1:
        raise ValueError("用户名不能为空")
    if len(password) < 6:
        raise ValueError("密码至少需要6位")
    users = _load_users()
    if any(_normalize_username(u["username"]) == normalized for u in users):
        raise ValueError("用户名已存在")
    salt = secrets.token_urlsafe(16)
    user = {
        "id": f"u_{secrets.token_urlsafe(12)}",
        "username": normalized,
        "salt": salt,
        "password_hash": _hash_password(password, salt),
        "created_at": _now(),
    }
    users.append(user)
    _save_users(users)
    user_dir = os.path.join(USERS_DIR, user["id"])
    os.makedirs(os.path.join(user_dir, "datasets"), exist_ok=True)
    os.makedirs(os.path.join(user_dir, "history"), exist_ok=True)
    _atomic_write_json(os.path.join(user_dir, "profile.json"), {"id": user["id"], "username": user["username"], "created_at": user["created_at"]})
    _atomic_write_json(os.path.join(user_dir, "datasets.json"), [])
    return create_token(user), _public_user(user)


def authenticate_user(username: str, password: str) -> tuple[str, UserPublic]:
    normalized = _normalize_username(username)
    users = _load_users()
    user = next((u for u in users if _normalize_username(u["username"]) == normalized), None)
    if not user or not hmac.compare_digest(_hash_password(password, user["salt"]), user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return create_token(user), _public_user(user)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserPublic:
    return verify_token(credentials.credentials)
