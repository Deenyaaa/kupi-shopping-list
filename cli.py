"""Клиент списка покупок для Claude (и для консоли). Только стандартная библиотека.

    py cli.py add молоко "хлеб бородинский"
    py cli.py list

Адрес сервера: переменная SHOPPING_URL, файл .claude-url рядом со скриптом или http://127.0.0.1:8000.
API-токен: переменная SHOPPING_TOKEN или файл .claude-token рядом со скриптом.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
TOKEN_FILE = HERE / ".claude-token"
URL_FILE = HERE / ".claude-url"
URL = (
    os.environ.get("SHOPPING_URL")
    or (URL_FILE.read_text(encoding="utf-8").strip() if URL_FILE.exists() else "")
    or "http://127.0.0.1:8000"
).rstrip("/")


def token() -> str:
    if t := os.environ.get("SHOPPING_TOKEN"):
        return t.strip()
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    sys.exit(f"Нет токена: создай его на сервере (manage.py create-token <логин> claude) и сохрани в {TOKEN_FILE}")


def call(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL + path, data=data, method=method, headers={
        "Authorization": f"Bearer {token()}",
        **({"Content-Type": "application/json"} if data else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = json.loads(e.read() or b"{}").get("detail", e.reason)
        sys.exit(f"Ошибка {e.code}: {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"Сервер {URL} недоступен: {e.reason}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2 or sys.argv[1] not in ("add", "list"):
        sys.exit(__doc__)
    if sys.argv[1] == "add":
        for name in sys.argv[2:]:
            item = call("POST", "/api/items", {"name": name})
            print(("уже в списке: " if item["duplicate"] else "добавлено: ") + item["name"])
    else:
        items = call("GET", "/api/items")
        todo = [i["name"] for i in items if not i["bought"]]
        print("\n".join(todo) if todo else "список пуст")


if __name__ == "__main__":
    main()
