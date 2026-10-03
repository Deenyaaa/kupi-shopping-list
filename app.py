import os
import re
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import auth
import db

STATIC = Path(__file__).with_name("static")
COOKIE = "session"
SESSION_TTL = 30 * 24 * 3600
# Secure-cookie уходит только по HTTPS (и на http://localhost). Выключать только для теста в локальной сети.
SECURE_COOKIE = os.environ.get("SHOPPING_SECURE_COOKIE", "1") != "0"

class ApiError(HTTPException):
    """Ошибка с кодом: интерфейс переводит её по коду, а detail (по-русски) читают cli.py и логи."""

    def __init__(self, status: int, code: str, message: str, **params):
        super().__init__(status, message)
        self.code = code
        self.params = params


# /docs и /openapi.json наружу не светим.
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(ApiError)
async def api_error(request: Request, exc: ApiError):
    return JSONResponse({"detail": exc.detail, "code": exc.code, "params": exc.params}, exc.status_code)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
limiter = auth.LoginLimiter()
db.init()


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def get_user(request: Request) -> dict | None:
    """Пользователь запроса и способ входа: via = "session" (браузер) или "token" (API)."""
    header = request.headers.get("authorization", "")
    with db.db() as c:
        if header.lower().startswith("bearer "):
            via = "token"
            row = c.execute(
                "SELECT u.id, u.username, u.is_admin FROM api_tokens t JOIN users u ON u.id = t.user_id"
                " WHERE t.token_hash = ?",
                (auth.token_hash(header[7:].strip()),),
            ).fetchone()
        elif token := request.cookies.get(COOKIE):
            via = "session"
            row = c.execute(
                "SELECT u.id, u.username, u.is_admin FROM sessions s JOIN users u ON u.id = s.user_id"
                " WHERE s.token_hash = ? AND s.expires_at > ?",
                (auth.token_hash(token), int(time.time())),
            ).fetchone()
        else:
            row = None
    if not row:
        return None
    return {"id": row["id"], "username": row["username"], "is_admin": bool(row["is_admin"]), "via": via}


def current_user(request: Request) -> dict:
    user = get_user(request)
    if not user:
        raise ApiError(401, "not_authenticated", "Нужно войти")
    return user


def session_user(user: dict = Depends(current_user)) -> dict:
    # Пароль и админка — только из браузера: API-токен (например, у Claude) даёт доступ лишь к списку.
    if user["via"] != "session":
        raise ApiError(403, "session_only", "Только через вход в браузере")
    return user


def current_admin(user: dict = Depends(session_user)) -> dict:
    if not user["is_admin"]:
        raise ApiError(403, "admin_only", "Нужны права администратора")
    return user


# --- страницы ---

@app.get("/", include_in_schema=False)
def index(request: Request):
    if not get_user(request):
        return RedirectResponse("/login")
    return FileResponse(STATIC / "index.html")


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(STATIC / "login.html")


@app.get("/admin", include_in_schema=False)
def admin_page(request: Request):
    user = get_user(request)
    if not user:
        return RedirectResponse("/login")
    if not (user["is_admin"] and user["via"] == "session"):
        return RedirectResponse("/")
    return FileResponse(STATIC / "admin.html")


# --- вход ---

class Credentials(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


@app.post("/api/login")
def login(creds: Credentials, request: Request, response: Response):
    ip = request.client.host if request.client else "?"
    if limiter.blocked(ip):
        raise ApiError(429, "too_many_attempts", "Слишком много попыток, подождите 15 минут")
    with db.db() as c:
        user = c.execute("SELECT * FROM users WHERE username = ?", (creds.username.strip(),)).fetchone()
        ok = auth.verify_password(creds.password, user["password_hash"] if user else auth.DUMMY_HASH)
        if not (user and ok):
            limiter.fail(ip)
            raise ApiError(401, "bad_credentials", "Неверный логин или пароль")
        limiter.reset(ip)
        token = auth.new_token()
        now = int(time.time())
        c.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        c.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (auth.token_hash(token), user["id"], now + SESSION_TTL),
        )
    response.set_cookie(
        COOKIE, token, max_age=SESSION_TTL, httponly=True, secure=SECURE_COOKIE, samesite="strict"
    )
    return {"username": user["username"]}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    if token := request.cookies.get(COOKIE):
        with db.db() as c:
            c.execute("DELETE FROM sessions WHERE token_hash = ?", (auth.token_hash(token),))
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return {"id": user["id"], "username": user["username"], "is_admin": user["is_admin"] and user["via"] == "session"}


class PasswordChange(BaseModel):
    current: str = Field(max_length=256)
    new: str = Field(min_length=auth.MIN_PASSWORD, max_length=256)


@app.post("/api/password")
def change_password(pw: PasswordChange, request: Request, user: dict = Depends(session_user)):
    ip = request.client.host if request.client else "?"
    if limiter.blocked(ip):
        raise ApiError(429, "too_many_attempts", "Слишком много попыток, подождите 15 минут")
    with db.db() as c:
        stored = c.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not auth.verify_password(pw.current, stored["password_hash"]):
            limiter.fail(ip)  # подбор текущего пароля через эту форму тоже ограничиваем
            raise ApiError(400, "wrong_current_password", "Текущий пароль неверный")
        c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (auth.hash_password(pw.new), user["id"]))
        # Выкидываем все остальные устройства, текущую сессию оставляем.
        c.execute(
            "DELETE FROM sessions WHERE user_id = ? AND token_hash != ?",
            (user["id"], auth.token_hash(request.cookies[COOKIE])),
        )
    return {"ok": True}


# --- список ---

ITEM_SELECT = (
    "SELECT i.id, i.name, u.username AS added_by, i.created_at, i.bought_at IS NOT NULL AS bought"
    " FROM items i LEFT JOIN users u ON u.id = i.added_by"
)


class NewItem(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ItemUpdate(BaseModel):
    bought: bool


def fetch_item(c, item_id: int) -> dict:
    row = c.execute(f"{ITEM_SELECT} WHERE i.id = ?", (item_id,)).fetchone()
    if not row:
        raise ApiError(404, "item_not_found", "Нет такой покупки")
    return {**dict(row), "bought": bool(row["bought"])}


@app.get("/api/items")
def list_items(user: dict = Depends(current_user)):
    with db.db() as c:
        rows = c.execute(
            f"{ITEM_SELECT} ORDER BY i.bought_at IS NOT NULL, COALESCE(i.bought_at, 0) DESC, i.created_at"
        ).fetchall()
    return [{**dict(r), "bought": bool(r["bought"])} for r in rows]


@app.post("/api/items", status_code=201)
def add_item(item: NewItem, response: Response, user: dict = Depends(current_user)):
    name = " ".join(item.name.split())
    if not name:
        raise ApiError(422, "empty_name", "Пустое название")
    with db.db() as c:
        # Если такая покупка уже есть в списке и ещё не куплена, второй раз не добавляем.
        # Сравниваем в Python: lower() в SQLite не понимает кириллицу.
        for row in c.execute("SELECT id, name FROM items WHERE bought_at IS NULL"):
            if row["name"].casefold() == name.casefold():
                response.status_code = 200
                return {**fetch_item(c, row["id"]), "duplicate": True}
        cur = c.execute(
            "INSERT INTO items (name, added_by, created_at) VALUES (?, ?, ?)",
            (name, user["id"], int(time.time())),
        )
        return {**fetch_item(c, cur.lastrowid), "duplicate": False}


@app.patch("/api/items/{item_id}")
def update_item(item_id: int, upd: ItemUpdate, user: dict = Depends(current_user)):
    with db.db() as c:
        fetch_item(c, item_id)
        c.execute(
            "UPDATE items SET bought_at = ? WHERE id = ?",
            (int(time.time()) if upd.bought else None, item_id),
        )
        return fetch_item(c, item_id)


@app.delete("/api/items/{item_id}")
def delete_item(item_id: int, user: dict = Depends(current_user)):
    with db.db() as c:
        fetch_item(c, item_id)
        c.execute("DELETE FROM items WHERE id = ?", (item_id,))
    return {"ok": True}


@app.post("/api/items/clear-bought")
def clear_bought(user: dict = Depends(current_user)):
    with db.db() as c:
        n = c.execute("DELETE FROM items WHERE bought_at IS NOT NULL").rowcount
    return {"deleted": n}


# --- админка: пользователи и API-токены (только админ, только из браузера) ---

USERNAME_RE = re.compile(r"[\w.-]{1,64}")  # \w с юникодом: кириллица тоже можно


class NewUser(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(min_length=auth.MIN_PASSWORD, max_length=256)
    is_admin: bool = False


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=auth.MIN_PASSWORD, max_length=256)
    is_admin: bool | None = None


class NewToken(BaseModel):
    user_id: int
    name: str = Field(min_length=1, max_length=64)


def fetch_user(c, user_id: int):
    row = c.execute("SELECT id, username, is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise ApiError(404, "user_not_found", "Нет такого пользователя")
    return {"id": row["id"], "username": row["username"], "is_admin": bool(row["is_admin"])}


@app.get("/api/admin/users")
def admin_users(admin: dict = Depends(current_admin)):
    with db.db() as c:
        rows = c.execute("SELECT id FROM users ORDER BY username").fetchall()
        return [fetch_user(c, r["id"]) for r in rows]


@app.post("/api/admin/users", status_code=201)
def admin_add_user(new: NewUser, admin: dict = Depends(current_admin)):
    username = new.username.strip()
    if not USERNAME_RE.fullmatch(username):
        raise ApiError(422, "bad_username", "Логин: буквы, цифры, точка, дефис или подчёркивание, без пробелов")
    with db.db() as c:
        if c.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            raise ApiError(409, "user_exists", f"Пользователь {username} уже есть", username=username)
        cur = c.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
            (username, auth.hash_password(new.password), int(new.is_admin)),
        )
        return fetch_user(c, cur.lastrowid)


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: int, upd: UserUpdate, admin: dict = Depends(current_admin)):
    with db.db() as c:
        fetch_user(c, user_id)
        if upd.is_admin is False and user_id == admin["id"]:
            # себя не понижаем: так нельзя случайно остаться совсем без админа
            raise ApiError(400, "cannot_demote_self", "Нельзя снять права администратора с самого себя")
        if upd.is_admin is not None:
            c.execute("UPDATE users SET is_admin = ? WHERE id = ?", (int(upd.is_admin), user_id))
        if upd.password is not None:
            c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (auth.hash_password(upd.password), user_id))
            c.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))  # выкинуть со всех устройств
        return fetch_user(c, user_id)


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, admin: dict = Depends(current_admin)):
    if user_id == admin["id"]:
        raise ApiError(400, "cannot_delete_self", "Нельзя удалить самого себя")
    with db.db() as c:
        fetch_user(c, user_id)
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))  # сессии и токены удалятся каскадом
    return {"ok": True}


@app.get("/api/admin/tokens")
def admin_tokens(admin: dict = Depends(current_admin)):
    with db.db() as c:
        rows = c.execute(
            "SELECT t.id, t.name, t.created_at, u.username FROM api_tokens t JOIN users u ON u.id = t.user_id"
            " ORDER BY t.id"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/admin/tokens", status_code=201)
def admin_add_token(new: NewToken, admin: dict = Depends(current_admin)):
    token = auth.new_token()
    with db.db() as c:
        user = fetch_user(c, new.user_id)
        cur = c.execute(
            "INSERT INTO api_tokens (token_hash, user_id, name, created_at) VALUES (?, ?, ?, ?)",
            (auth.token_hash(token), user["id"], new.name.strip(), int(time.time())),
        )
    # Сам токен показываем один раз: в базе остаётся только хэш.
    return {"id": cur.lastrowid, "name": new.name.strip(), "username": user["username"], "token": token}


@app.delete("/api/admin/tokens/{token_id}")
def admin_revoke_token(token_id: int, admin: dict = Depends(current_admin)):
    with db.db() as c:
        if not c.execute("DELETE FROM api_tokens WHERE id = ?", (token_id,)).rowcount:
            raise ApiError(404, "token_not_found", "Нет такого токена")
    return {"ok": True}
