from hashlib import pbkdf2_hmac


def hash_password(password: str, salt: str = "population-system") -> str:
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return digest.hex()
