# Купи — общий список покупок

[English](README.md) · **Русский**

Общий список покупок на несколько человек: страница для телефона, вход по логину и паролю,
админка для управления пользователями и API-токенами (например, для Claude). FastAPI и SQLite.
На сервере работает в Docker за Caddy, который сам выпускает HTTPS-сертификат.

```
телефон ──HTTPS──▶ Caddy :443 ──▶ app :8000 (FastAPI) ──▶ /data/shopping.db
Claude  ──HTTPS + Bearer-токен──┘
```

## Файлы

| Файл | Что внутри |
|---|---|
| `app.py` | API и страницы, включая админку |
| `auth.py` | пароли (scrypt), токены, ограничение попыток входа |
| `db.py` | схема SQLite и миграции, путь к базе задаётся через `SHOPPING_DB` |
| `manage.py` | пользователи, токены, резервные копии из консоли сервера |
| `cli.py` | консольный клиент, через него Claude добавляет покупки |
| `static/` | интерфейс: список, вход, админка |
| `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `.env.example` | развёртывание |
| `sites/` | сайты соседних сервисов за этим же Caddy (см. `sites/README.md`) |
| `tests/smoke_test.py` | сквозная проверка API |

---

## Развёртывание на VPS

### 1. Домен

Нужен домен, который указывает на **IP VPS**. Бесплатно: поддомен на [duckdns.org](https://www.duckdns.org).
Проверка: `nslookup <домен>` должен вернуть адрес VPS.
Пока домен смотрит на другой адрес, Caddy не получит сертификат.

### 2. Docker и порты

```bash
curl -fsSL https://get.docker.com | sh
# если включён ufw:
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443 && ufw enable
```

Порт 80 нужен Let's Encrypt для выпуска сертификата и для переадресации на HTTPS. Закрывать его нельзя.

### 3. Код

```bash
git clone <адрес репозитория> shopping-list
cd shopping-list
```

Без git можно скопировать папку с компьютера: `scp -r shopping-list user@vps:~/`
(`.venv`, базу и токены копировать не нужно).

### 4. Запуск

```bash
cp .env.example .env              # впиши свой домен в DOMAIN
docker compose up -d --build
docker compose logs -f caddy      # ждём строку "certificate obtained successfully", выход Ctrl+C
```

Открой `https://<домен>`, должна появиться страница входа.

### 5. Первый администратор

```bash
docker compose exec app python manage.py add-user alice      # спросит пароль, минимум 8 символов
docker compose exec app python manage.py make-admin alice
```

Дальше всё делается в браузере: войди и открой **Админка** в шапке (`/admin`). Там можно создавать
пользователей, сбрасывать им пароли, назначать админов, удалять пользователей и выпускать API-токены.
Свой пароль любой пользователь меняет сам: кнопка **Пароль** на главной.

### 6. Доступ для Claude

В админке, раздел **API-токены**: выбери пользователя, от имени которого будут добавляться покупки,
впиши назначение (`claude`) и нажми **Создать токен**. Токен показывается один раз.

На компьютере, где работает Claude Code, в папке проекта:

```powershell
Set-Content .claude-token "<токен>" -NoNewline
Set-Content .claude-url "https://<домен>" -NoNewline
py cli.py list        # проверка
```

Оба файла в `.gitignore`. Токен даёт доступ только к списку: ни админкой, ни сменой пароля через него
воспользоваться нельзя.

---

## Эксплуатация

Пользователи и токены — в админке (`/admin`). Остальные команды выполняются на VPS в папке проекта.

| Задача | Команда |
|---|---|
| Обновить после изменений в коде | `git pull && docker compose up -d --build` |
| Логи | `docker compose logs -f app` (или `caddy`) |
| Перезапуск | `docker compose restart` |
| Остановить | `docker compose down` (данные в томах сохраняются) |
| Пользователи без браузера | `docker compose exec app python manage.py users` (`passwd`, `del-user`, `make-admin`) |
| Токены без браузера | `docker compose exec app python manage.py tokens`, затем `revoke-token <id>` |

**Никогда не запускай `docker compose down -v`**: флаг `-v` удаляет тома, а вместе с ними базу и сертификаты.

Если единственный админ потерял пароль: `docker compose exec app python manage.py passwd <логин>`.

### Резервная копия

```bash
docker compose exec app python manage.py backup /data/backup.db
docker compose cp app:/data/backup.db ./shopping-$(date +%F).db
```

`backup` делает целостную копию даже на работающем сервере. Просто копировать файл базы во время записи нельзя.

### Восстановление

```bash
docker compose stop app
docker compose run --rm --user root -v "$PWD:/restore" app \
  sh -c "cp /restore/shopping-2026-09-27.db /data/shopping.db && chown app /data/shopping.db"
docker compose start app
```

---

## Локальная разработка (Windows)

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py add-user alice
.\.venv\Scripts\python.exe manage.py make-admin alice
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000
```

Открой http://localhost:8000. Локальная база `shopping.db` лежит в папке проекта и в git не попадает.

Проверка после изменений (поднимает сервер на временной базе, 73 проверки):

```powershell
.\.venv\Scripts\python.exe tests\smoke_test.py
```

---

## Как устроена защита

- **HTTPS.** Без него пароль и cookie входа передаются открытым текстом. Cookie помечена `Secure`, поэтому по HTTP на внешний адрес браузер её не отправит. Для теста в домашней сети по `http://192.168.x.x` запускай с `SHOPPING_SECURE_COOKIE=0`.
- **Пароли.** scrypt с солью, минимум 8 символов. Сессии и API-токены хранятся в базе только в виде SHA-256-хэшей.
- **Cookie.** `HttpOnly`, `Secure`, `SameSite=Strict`, живёт 30 дней. Сброс пароля админом выкидывает пользователя со всех устройств; при смене своего пароля остаётся только текущее устройство.
- **Админка.** Права проверяются на сервере, а не только скрываются в интерфейсе. Админка и смена пароля доступны только при входе через браузер: API-токен, даже выпущенный для админа, работает лишь со списком. Нельзя удалить себя и снять права администратора с себя — так нельзя случайно остаться без админа.
- **Перебор паролей.** После 5 неудачных попыток (вход или неверный текущий пароль при смене) IP блокируется на 15 минут. Настоящий IP берётся из `X-Forwarded-For` от Caddy. Счётчик хранится в памяти и сбрасывается при перезапуске.
- **Лишнее закрыто.** Открытой регистрации нет. `/docs` и `/openapi.json` выключены. Порт приложения наружу не открыт, всё идёт через Caddy.
- **XSS.** Пользовательские строки (названия покупок, логины) выводятся через `textContent`, плюс заголовок CSP `default-src 'self'`.

## Лицензия

[MIT](LICENSE)
