"""密码哈希工具

使用 hashlib.pbkdf2_hmac（不引入额外依赖 bcrypt，避免 docker 镜像体积膨胀）。
PBKDF2-HMAC-SHA256 + 16 bytes salt + 100000 轮迭代，符合 OWASP 2023 建议。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Tuple


_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16
_HASH_BYTES = 32
_ALG = "sha256"


def hash_password(plain: str) -> str:
    """生成密码哈希。格式：``pbkdf2_sha256$<iter>$<salt_hex>$<hash_hex>``"""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(_ALG, plain.encode("utf-8"), salt, _PBKDF2_ITERATIONS, dklen=_HASH_BYTES)
    return f"pbkdf2_{_ALG}${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    """验证密码。恒定时间比较防时序攻击。"""
    try:
        scheme, iter_str, salt_hex, hash_hex = hashed.split("$", 3)
    except ValueError:
        return False
    if not scheme.startswith("pbkdf2_"):
        return False
    alg = scheme.split("_", 1)[1]
    try:
        iterations = int(iter_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac(alg, plain.encode("utf-8"), salt, iterations, dklen=len(expected))
    return hmac.compare_digest(digest, expected)


def issue_token(user_id: int, secret: str) -> Tuple[str, int]:
    """签发一个简易 token（HMAC-SHA256 + 用户ID + 过期时间戳）。"""
    import base64
    import json
    import time

    expires_at = int(time.time()) + 60 * 60 * 24 * 7  # 7 天
    payload = {
        "sub": user_id,
        "exp": expires_at,
        "iat": int(time.time()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{payload_b64}.{sig_b64}", expires_at


def verify_token(token: str, secret: str) -> int | None:
    """验证 token，返回 user_id；失败返回 None。"""
    import base64
    import json
    import time

    try:
        payload_b64, sig_b64 = token.split(".", 1)
    except ValueError:
        return None

    # 验签
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64_expected = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    if not hmac.compare_digest(sig_b64, sig_b64_expected):
        return None

    # 解码 payload（补齐 padding）
    padding = "=" * (-len(payload_b64) % 4)
    try:
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        return None

    sub = payload.get("sub")
    if not isinstance(sub, int):
        return None
    return sub
