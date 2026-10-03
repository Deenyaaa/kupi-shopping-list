import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque

SCRYPT = dict(n=2**14, r=8, p=1)
MIN_PASSWORD = 8  # общее правило для manage.py, смены пароля и админки


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    _, salt, digest = stored.split("$")
    calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **SCRYPT)
    return hmac.compare_digest(calc.hex(), digest)


# Проверяем пароль и для несуществующего логина, чтобы по времени ответа нельзя было угадать логины.
DUMMY_HASH = hash_password(secrets.token_hex())


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    # В базе лежат только хэши: утечка shopping.db не даёт готовых сессий и токенов.
    return hashlib.sha256(token.encode()).hexdigest()


class LoginLimiter:
    """Не больше MAX_FAILS неудачных входов с одного IP за WINDOW секунд."""

    MAX_FAILS = 5
    WINDOW = 15 * 60

    def __init__(self):
        self.fails: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, ip: str) -> deque[float]:
        q = self.fails[ip]
        while q and q[0] < time.time() - self.WINDOW:
            q.popleft()
        return q

    def blocked(self, ip: str) -> bool:
        return len(self._prune(ip)) >= self.MAX_FAILS

    def fail(self, ip: str):
        self._prune(ip).append(time.time())

    def reset(self, ip: str):
        self.fails.pop(ip, None)
