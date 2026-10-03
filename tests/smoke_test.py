"""Сквозная проверка API: поднимает сервер на временной базе и прогоняет сценарии.

    .venv\\Scripts\\python.exe tests\\smoke_test.py
"""
import http.cookiejar
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(), "test.db")
PY = sys.executable
BASE = "http://127.0.0.1:8765"

env = {**os.environ, "SHOPPING_DB": DB}

# тестовые пользователи и токен — через код приложения, минуя getpass
setup = subprocess.run([PY, "-c", """
import auth, db, time
db.init()
with db.db() as c:
    for u, admin in (('alice', 1), ('bob', 0)):
        c.execute('INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)',
                  (u, auth.hash_password('test-pass-' + u), admin))
    t = auth.new_token()
    c.execute('INSERT INTO api_tokens (token_hash, user_id, name, created_at) VALUES (?, 1, ?, ?)', (auth.token_hash(t), 'claude', int(time.time())))
print(t)
"""], cwd=PROJECT, env=env, capture_output=True, text=True, check=True)
TOKEN = setup.stdout.strip()

server = subprocess.Popen([PY, "-m", "uvicorn", "app:app", "--port", "8765"], cwd=PROJECT, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
fails = 0


def check(name, cond, extra=""):
    global fails
    print(("OK  " if cond else "FAIL") + " " + name + (f"  [{extra}]" if extra and not cond else ""))
    fails += not cond


def req(method, path, body=None, headers=None, opener=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"} if data else {}
    h.update(headers or {})
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        resp = (opener or urllib.request.build_opener(NoRedirect)).open(r)
        return resp.status, resp.headers, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read().decode()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def session():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect)


try:
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE + "/login")
            break
        except Exception:
            time.sleep(0.2)

    s, h, _ = req("GET", "/")
    check("без входа / редиректит на /login", s in (302, 307) and h["location"] == "/login", s)
    for m, p in [("GET", "/api/items"), ("POST", "/api/items"), ("GET", "/api/me")]:
        s, _, _ = req(m, p, {"name": "x"} if m == "POST" else None)
        check(f"без входа {m} {p} -> 401", s == 401, s)
    for p in ["/docs", "/openapi.json", "/redoc"]:
        check(f"{p} закрыт", req("GET", p)[0] == 404)
    check("чужой токен -> 401", req("GET", "/api/items", headers={"Authorization": "Bearer nope"})[0] == 401)

    alice = session()
    s, h, b = req("POST", "/api/login", {"username": "alice", "password": "wrong"}, opener=alice)
    check("неверный пароль -> 401", s == 401, s)
    s, h, b = req("POST", "/api/login", {"username": "Alice", "password": "test-pass-alice"}, opener=alice)
    cookie = h.get("set-cookie", "")
    check("вход (логин без учёта регистра)", s == 200, (s, b))
    check("cookie HttpOnly/Secure/SameSite=strict",
          all(x in cookie.lower() for x in ["httponly", "secure", "samesite=strict"]), cookie)
    check("CSP заголовок", "default-src 'self'" in h.get("content-security-policy", ""))

    # Secure-cookie urllib по http не отправляет, поэтому дальше подставляем её руками
    sid = cookie.split(";")[0]
    A = {"Cookie": sid}
    check("/ после входа отдаёт страницу", req("GET", "/", headers=A)[0] == 200)
    s, _, b = req("GET", "/api/me", headers=A)
    check("/api/me", s == 200 and json.loads(b)["username"] == "alice", b)

    s, _, b = req("POST", "/api/items", {"name": "  Молоко   2.5% "}, headers=A)
    milk = json.loads(b)
    check("добавление, пробелы схлопнуты", s == 201 and milk["name"] == "Молоко 2.5%" and milk["added_by"] == "alice", b)
    s, _, b = req("POST", "/api/items", {"name": "молоко 2.5%"}, headers=A)
    check("дубль в другом регистре (кириллица) не добавляется", s == 200 and json.loads(b)["duplicate"] and json.loads(b)["id"] == milk["id"], b)
    check("пустое название -> 422", req("POST", "/api/items", {"name": "   "}, headers=A)[0] == 422)
    check("слишком длинное -> 422", req("POST", "/api/items", {"name": "x" * 201}, headers=A)[0] == 422)

    T = {"Authorization": f"Bearer {TOKEN}"}
    s, _, b = req("POST", "/api/items", {"name": "Хлеб"}, headers=T)
    bread = json.loads(b)
    check("добавление по API-токену", s == 201 and bread["added_by"] == "alice", b)
    s, _, b = req("POST", "/api/items", {"name": "<img src=x onerror=alert(1)>"}, headers=T)
    check("html в названии хранится как текст", s == 201)

    bob = session()
    s, h, _ = req("POST", "/api/login", {"username": "bob", "password": "test-pass-bob"}, opener=bob)
    B = {"Cookie": h["set-cookie"].split(";")[0]}
    s, _, b = req("GET", "/api/items", headers=B)
    check("второй пользователь видит общий список", s == 200 and len(json.loads(b)) == 3, b)
    s, _, b = req("PATCH", f"/api/items/{milk['id']}", {"bought": True}, headers=B)
    check("отметить купленным", s == 200 and json.loads(b)["bought"] is True, b)
    s, _, b = req("GET", "/api/items", headers=A)
    items = json.loads(b)
    check("купленное в конце списка", items[-1]["id"] == milk["id"] and items[-1]["bought"], b)
    s, _, b = req("POST", "/api/items", {"name": "Молоко 2.5%"}, headers=A)
    check("купленное молоко можно добавить заново", s == 201, b)
    s, _, b = req("PATCH", f"/api/items/{milk['id']}", {"bought": False}, headers=B)
    check("снять отметку", s == 200 and json.loads(b)["bought"] is False)
    req("PATCH", f"/api/items/{milk['id']}", {"bought": True}, headers=B)
    s, _, b = req("POST", "/api/items/clear-bought", headers=B)
    check("очистить купленное", s == 200 and json.loads(b)["deleted"] == 1, b)
    s, _, b = req("DELETE", f"/api/items/{bread['id']}", headers=B)
    check("удалить", s == 200)
    check("удалить несуществующее -> 404", req("DELETE", f"/api/items/{bread['id']}", headers=B)[0] == 404)

    # --- админка ---
    def login(user, password):
        s, h, b = req("POST", "/api/login", {"username": user, "password": password})
        return s, ({"Cookie": h["set-cookie"].split(";")[0]} if s == 200 else None)

    s, _, b = req("GET", "/api/me", headers=A)
    check("/api/me: alice админ", s == 200 and json.loads(b)["is_admin"] is True, b)
    s, _, b = req("GET", "/api/me", headers=B)
    check("/api/me: bob не админ", json.loads(b)["is_admin"] is False, b)
    check("/admin для админа", req("GET", "/admin", headers=A)[0] == 200)
    s, h, _ = req("GET", "/admin", headers=B)
    check("/admin для не-админа -> редирект на /", s in (302, 307) and h["location"] == "/", s)
    s, h, _ = req("GET", "/admin")
    check("/admin без входа -> /login", s in (302, 307) and h["location"] == "/login", s)
    check("не-админ: /api/admin/users -> 403", req("GET", "/api/admin/users", headers=B)[0] == 403)
    check("токен админа не даёт админку -> 403", req("GET", "/api/admin/users", headers=T)[0] == 403)
    check("токен не меняет пароль -> 403",
          req("POST", "/api/password", {"current": "x", "new": "y" * 8}, headers=T)[0] == 403)

    s, _, b = req("GET", "/api/admin/users", headers=A)
    users = {u["username"]: u for u in json.loads(b)}
    check("список пользователей", s == 200 and set(users) == {"alice", "bob"} and users["alice"]["is_admin"], b)
    alice_id = users["alice"]["id"]

    s, _, b = req("POST", "/api/admin/users", {"username": "carol", "password": "carol-pass-1"}, headers=A)
    carol = json.loads(b)
    check("создать пользователя", s == 201 and carol["username"] == "carol" and not carol["is_admin"], b)
    check("дубль логина -> 409",
          req("POST", "/api/admin/users", {"username": "CAROL", "password": "x" * 8}, headers=A)[0] == 409)
    check("логин с пробелом -> 422",
          req("POST", "/api/admin/users", {"username": "a b", "password": "x" * 8}, headers=A)[0] == 422)
    check("короткий пароль -> 422",
          req("POST", "/api/admin/users", {"username": "dave", "password": "short"}, headers=A)[0] == 422)
    check("не-админ не создаёт пользователей",
          req("POST", "/api/admin/users", {"username": "eve", "password": "x" * 8}, headers=B)[0] == 403)
    s, C = login("carol", "carol-pass-1")
    check("новый пользователь входит", s == 200)

    s, _, b = req("PATCH", f"/api/admin/users/{carol['id']}", {"password": "carol-pass-2"}, headers=A)
    check("админ меняет пароль пользователю", s == 200, b)
    check("сброс пароля выкидывает его сессии", req("GET", "/api/items", headers=C)[0] == 401)
    check("старый пароль не подходит", login("carol", "carol-pass-1")[0] == 401)
    s, C = login("carol", "carol-pass-2")
    check("новый пароль подходит", s == 200)

    s, _, b = req("PATCH", f"/api/admin/users/{carol['id']}", {"is_admin": True}, headers=A)
    check("сделать админом", s == 200 and json.loads(b)["is_admin"] is True, b)
    check("новый админ видит админку", req("GET", "/api/admin/users", headers=C)[0] == 200)
    req("PATCH", f"/api/admin/users/{carol['id']}", {"is_admin": False}, headers=A)
    check("снятый админ теряет доступ", req("GET", "/api/admin/users", headers=C)[0] == 403)
    check("нельзя снять админа с себя",
          req("PATCH", f"/api/admin/users/{alice_id}", {"is_admin": False}, headers=A)[0] == 400)
    check("нельзя удалить себя", req("DELETE", f"/api/admin/users/{alice_id}", headers=A)[0] == 400)
    check("PATCH несуществующего -> 404",
          req("PATCH", "/api/admin/users/9999", {"is_admin": True}, headers=A)[0] == 404)

    s, _, b = req("POST", "/api/admin/tokens", {"user_id": carol["id"], "name": "test-int"}, headers=A)
    new_tok = json.loads(b)
    check("создать токен", s == 201 and new_tok["token"] and new_tok["username"] == "carol", b)
    CT = {"Authorization": f"Bearer {new_tok['token']}"}
    check("новый токен работает со списком", req("GET", "/api/items", headers=CT)[0] == 200)
    s, _, b = req("GET", "/api/admin/tokens", headers=A)
    listed = json.loads(b)
    check("токен в списке, без самого секрета",
          any(t["id"] == new_tok["id"] for t in listed) and all("token" not in t for t in listed), b)
    check("отозвать токен", req("DELETE", f"/api/admin/tokens/{new_tok['id']}", headers=A)[0] == 200)
    check("отозванный токен -> 401", req("GET", "/api/items", headers=CT)[0] == 401)
    check("отозвать несуществующий -> 404",
          req("DELETE", f"/api/admin/tokens/{new_tok['id']}", headers=A)[0] == 404)

    s, _, _ = req("DELETE", f"/api/admin/users/{carol['id']}", headers=A)
    check("удалить пользователя", s == 200)
    check("удалённый не входит", login("carol", "carol-pass-2")[0] == 401)

    # --- смена своего пароля ---
    s, B2 = login("bob", "test-pass-bob")  # второе устройство bob
    check("неверный текущий пароль -> 400",
          req("POST", "/api/password", {"current": "bad", "new": "bob-new-pass"}, headers=B)[0] == 400)
    s, _, b = req("POST", "/api/password", {"current": "test-pass-bob", "new": "bob-new-pass"}, headers=B)
    check("сменить свой пароль", s == 200, b)
    check("текущая сессия после смены жива", req("GET", "/api/items", headers=B)[0] == 200)
    check("другие устройства разлогинены", req("GET", "/api/items", headers=B2)[0] == 401)
    s, _ = login("bob", "bob-new-pass")  # успешный вход заодно сбрасывает счётчик неудач с этого IP
    check("вход с новым паролем", s == 200)
    req("POST", "/api/password", {"current": "bob-new-pass", "new": "test-pass-bob"}, headers=B)

    s, _, _ = req("POST", "/api/logout", headers=A)
    check("после выхода сессия не работает", req("GET", "/api/items", headers=A)[0] == 401)
    check("у второго пользователя сессия жива", req("GET", "/api/items", headers=B)[0] == 200)

    codes = [req("POST", "/api/login", {"username": "bob", "password": "bad"})[0] for _ in range(6)]
    check("перебор паролей блокируется после 5 попыток", codes[:5] == [401] * 5 and codes[5] == 429, codes)
    s, _, _ = req("POST", "/api/login", {"username": "bob", "password": "test-pass-bob"})
    check("при блокировке и верный пароль не пускает", s == 429, s)

    backup = DB + ".backup"
    subprocess.run([PY, "manage.py", "backup", backup], cwd=PROJECT, env=env, capture_output=True, check=True)
    import sqlite3
    with sqlite3.connect(backup) as b:
        n_users = b.execute("SELECT count(*) FROM users").fetchone()[0]
    check("manage.py backup делает рабочую копию", n_users == 2, n_users)

    cli = subprocess.run([PY, "cli.py", "add", "Кефир"], cwd=PROJECT, capture_output=True,
                         env={**env, "SHOPPING_URL": BASE, "SHOPPING_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"})
    check("cli.py add", cli.returncode == 0 and "добавлено: Кефир" in cli.stdout.decode("utf-8"), cli)
finally:
    server.terminate()
    err = server.communicate(timeout=10)[1].decode(errors="replace")
    tracebacks = [l for l in err.splitlines() if "Traceback" in l or "Error" in l and "INFO" not in l]
    check("в логе сервера нет ошибок", not tracebacks, "\n".join(tracebacks[:5]))

print(f"\n{'ВСЁ ОК' if not fails else f'ПРОВАЛОВ: {fails}'}")
sys.exit(1 if fails else 0)
