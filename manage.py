"""Управление пользователями и API-токенами. Запускать на сервере:

    py manage.py add-user alice
    py manage.py make-admin alice      # дальше пользователями можно управлять на странице /admin
    py manage.py passwd alice
    py manage.py del-user alice
    py manage.py users
    py manage.py create-token alice claude [--out файл]
    py manage.py tokens
    py manage.py revoke-token 3
    py manage.py backup /data/backup.db
"""
import argparse
import getpass
import sqlite3
import sys
import time
from pathlib import Path

import auth
import db


def ask_password() -> str:
    pw = getpass.getpass("Пароль: ")
    if len(pw) < auth.MIN_PASSWORD:
        sys.exit(f"Пароль должен быть не короче {auth.MIN_PASSWORD} символов")
    if getpass.getpass("Ещё раз: ") != pw:
        sys.exit("Пароли не совпадают")
    return pw


def user_id(c, username: str) -> int:
    row = c.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        sys.exit(f"Нет пользователя {username}")
    return row["id"]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("add-user").add_argument("username")
    sub.add_parser("make-admin", help="дать права администратора (страница /admin)").add_argument("username")
    sub.add_parser("passwd").add_argument("username")
    sub.add_parser("del-user").add_argument("username")
    sub.add_parser("users")
    t = sub.add_parser("create-token")
    t.add_argument("username")
    t.add_argument("name", help="для чего токен, например claude")
    t.add_argument("--out", help="записать токен в файл, а не выводить на экран")
    sub.add_parser("tokens")
    sub.add_parser("revoke-token").add_argument("id", type=int)
    sub.add_parser("backup", help="целостная копия базы, можно делать на работающем сервере").add_argument("path")
    a = p.parse_args()

    db.init()
    if a.cmd == "backup":
        with db.db() as src, sqlite3.connect(a.path) as dst:
            src.backup(dst)
        print(f"Копия базы: {a.path}")
        return
    with db.db() as c:
        if a.cmd == "add-user":
            if c.execute("SELECT 1 FROM users WHERE username = ?", (a.username,)).fetchone():
                sys.exit(f"Пользователь {a.username} уже есть")
            c.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (a.username, auth.hash_password(ask_password())),
            )
            print(f"Пользователь {a.username} создан")
        elif a.cmd == "make-admin":
            c.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user_id(c, a.username),))
            print(f"{a.username} теперь администратор")
        elif a.cmd == "passwd":
            uid = user_id(c, a.username)
            c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (auth.hash_password(ask_password()), uid))
            c.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
            print("Пароль изменён, все входы этого пользователя сброшены")
        elif a.cmd == "del-user":
            c.execute("DELETE FROM users WHERE id = ?", (user_id(c, a.username),))
            print(f"Пользователь {a.username} удалён")
        elif a.cmd == "users":
            for r in c.execute("SELECT username, is_admin FROM users ORDER BY username"):
                print(r["username"] + ("  [admin]" if r["is_admin"] else ""))
        elif a.cmd == "create-token":
            token = auth.new_token()
            c.execute(
                "INSERT INTO api_tokens (token_hash, user_id, name, created_at) VALUES (?, ?, ?, ?)",
                (auth.token_hash(token), user_id(c, a.username), a.name, int(time.time())),
            )
            if a.out:
                Path(a.out).write_text(token, encoding="utf-8")
                print(f"Токен записан в {a.out}")
            else:
                print(token)
                print("Сохрани его: второй раз показать не получится.", file=sys.stderr)
        elif a.cmd == "tokens":
            for r in c.execute(
                "SELECT t.id, t.name, u.username FROM api_tokens t JOIN users u ON u.id = t.user_id ORDER BY t.id"
            ):
                print(f"{r['id']}\t{r['username']}\t{r['name']}")
        elif a.cmd == "revoke-token":
            n = c.execute("DELETE FROM api_tokens WHERE id = ?", (a.id,)).rowcount
            print("Токен отозван" if n else "Нет такого токена")


if __name__ == "__main__":
    main()
