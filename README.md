# Kupi — a shared shopping list

**English** · [Русский](README.ru.md)

*Kupi* (Russian «Купи», "buy!") is a small self-hosted shopping list for a family or a flat:
a phone-friendly page with per-person logins, an admin panel for users and API tokens, and a
token API so an assistant (e.g. Claude) can add items for you. FastAPI + SQLite, runs in Docker
behind Caddy, which obtains the HTTPS certificate automatically.

```
phone  ──HTTPS──▶ Caddy :443 ──▶ app :8000 (FastAPI) ──▶ /data/shopping.db
Claude ──HTTPS + Bearer token──┘
```

The UI is in Russian.

## Features

- One shared list for everyone; items show who added them; bought items move to the bottom.
- Duplicate protection: adding an item that is already on the list (case-insensitive, Cyrillic too) does nothing.
- Per-person accounts; everyone can change their own password.
- Admin panel (`/admin`): create and delete users, reset passwords, grant or revoke admin rights,
  issue and revoke API tokens.
- API tokens for integrations; a token can only work with the list, never with the admin panel.
- `cli.py` — a tiny console client, used by Claude to add items.

## Files

| File | Contents |
|---|---|
| `app.py` | API and pages, including the admin panel |
| `auth.py` | passwords (scrypt), tokens, login rate limiting |
| `db.py` | SQLite schema and migrations; DB path is set via `SHOPPING_DB` |
| `manage.py` | users, tokens and backups from the server console |
| `cli.py` | console client |
| `static/` | UI: list, login, admin panel |
| `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `.env.example` | deployment |
| `sites/` | sites of other services behind the same Caddy (see `sites/README.md`) |
| `tests/smoke_test.py` | end-to-end API test |

---

## Deploying to a VPS

### 1. Domain

You need a domain pointing to the **VPS IP**. A free subdomain from [duckdns.org](https://www.duckdns.org) works.
Check: `nslookup <domain>` must return the VPS address. Until it does, Caddy cannot get a certificate.

### 2. Docker and ports

```bash
curl -fsSL https://get.docker.com | sh
# if ufw is enabled:
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443 && ufw enable
```

Port 80 is required by Let's Encrypt and for the HTTP→HTTPS redirect; keep it open.

### 3. Code

```bash
git clone https://github.com/Deenyaaa/kupi-shopping-list.git shopping-list
cd shopping-list
```

### 4. Start

```bash
cp .env.example .env              # put your domain into DOMAIN
docker compose up -d --build
docker compose logs -f caddy      # wait for "certificate obtained successfully", then Ctrl+C
```

Open `https://<domain>`; the login page should appear.

### 5. First administrator

```bash
docker compose exec app python manage.py add-user alice      # asks for a password, at least 8 characters
docker compose exec app python manage.py make-admin alice
```

Everything else is done in the browser: log in and open **Админка** (admin panel, `/admin`) in the header.

### 6. Access for Claude (optional)

In the admin panel, section **API-токены**: pick the user on whose behalf items will be added, name the
token (`claude`) and create it. The token is shown once.

On the machine running Claude Code, in the project folder:

```powershell
Set-Content .claude-token "<token>" -NoNewline
Set-Content .claude-url "https://<domain>" -NoNewline
py cli.py list        # check
```

Both files are git-ignored.

---

## Operations

Users and tokens are managed in the admin panel. Other commands run on the VPS in the project folder.

| Task | Command |
|---|---|
| Update after code changes | `git pull && docker compose up -d --build` |
| Logs | `docker compose logs -f app` (or `caddy`) |
| Restart | `docker compose restart` |
| Stop | `docker compose down` (data in volumes is kept) |
| Users without a browser | `docker compose exec app python manage.py users` (`passwd`, `del-user`, `make-admin`) |
| Tokens without a browser | `docker compose exec app python manage.py tokens`, then `revoke-token <id>` |

**Never run `docker compose down -v`**: `-v` deletes the volumes, i.e. the database and certificates.

If the only admin lost their password: `docker compose exec app python manage.py passwd <login>`.

### Backup

```bash
docker compose exec app python manage.py backup /data/backup.db
docker compose cp app:/data/backup.db ./shopping-$(date +%F).db
```

`backup` makes a consistent copy even while the server is running; copying the DB file directly during writes is unsafe.

### Restore

```bash
docker compose stop app
docker compose run --rm --user root -v "$PWD:/restore" app \
  sh -c "cp /restore/shopping-2026-09-27.db /data/shopping.db && chown app /data/shopping.db"
docker compose start app
```

---

## Local development (Windows)

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py add-user alice
.\.venv\Scripts\python.exe manage.py make-admin alice
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000
```

Open http://localhost:8000. The local `shopping.db` lives in the project folder and is git-ignored.

Test after changes (starts the server on a temporary DB, 73 checks):

```powershell
.\.venv\Scripts\python.exe tests\smoke_test.py
```

---

## Security

- **HTTPS.** The session cookie is `Secure`, so browsers won't send it over plain HTTP to a remote host. For testing on a LAN via `http://192.168.x.x`, run with `SHOPPING_SECURE_COOKIE=0`.
- **Passwords.** Salted scrypt, minimum 8 characters. Sessions and API tokens are stored only as SHA-256 hashes.
- **Cookie.** `HttpOnly`, `Secure`, `SameSite=Strict`, 30 days. An admin password reset signs the user out everywhere; changing your own password keeps only the current device.
- **Admin panel.** Permissions are enforced on the server, not just hidden in the UI. The admin panel and password change require a browser session: an API token, even one issued to an admin, can only work with the list. You cannot delete yourself or revoke your own admin rights, so the instance can't be left without an admin by accident.
- **Brute force.** After 5 failed attempts (login, or a wrong current password when changing it) the IP is blocked for 15 minutes. The real IP comes from Caddy's `X-Forwarded-For`. The counter is in memory and resets on restart.
- **Attack surface.** No open registration. `/docs` and `/openapi.json` are disabled. The app port is not exposed; everything goes through Caddy.
- **XSS.** User-provided strings (item names, logins) are rendered via `textContent`, plus a `default-src 'self'` CSP header.

## License

[MIT](LICENSE)
