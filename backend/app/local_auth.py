import base64
import hashlib
import hmac
import os


HASH_SCHEME = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 260_000


def hash_password(password: str, iterations: int = DEFAULT_ITERATIONS) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "$".join(
        [
            HASH_SCHEME,
            str(iterations),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, iterations_text, salt_text, digest_text = stored_hash.split("$", 3)
        iterations = int(iterations_text)
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
    except (ValueError, TypeError):
        return False
    if scheme != HASH_SCHEME or iterations <= 0:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)
