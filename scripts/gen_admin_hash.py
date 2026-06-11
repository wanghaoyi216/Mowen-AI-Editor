"""生成 admin 的新密码哈希"""
import hashlib
import secrets

PASSWORD = "admin123456"
salt = secrets.token_bytes(16)
digest = hashlib.pbkdf2_hmac('sha256', PASSWORD.encode('utf-8'), salt, 200000, dklen=32)
hashed = f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"
print(hashed)
