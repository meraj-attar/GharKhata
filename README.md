# GharKhata — Household Finance Manager

A simple, single-owner household income and expense tracker. Built with React, TypeScript, Vite, Tailwind CSS, Recharts, FastAPI, SQLAlchemy, Pydantic, Alembic, and PostgreSQL.

**Currency:** Indian Rupees (₹) · **Language:** English · **Theme:** Royal Navy / Soft Lavender / White

## What it does

- **Dashboard:** Month picker, monthly income, monthly expenses, monthly net balance (income − expenses), daily expense bar chart, category breakdown, and the five most recent entries in the selected month.
- **Transactions:** Add, search, filter by month/type/category, edit, and permanently delete with confirmation. Only positive amounts with up to two decimal places are accepted.
- **Reports:** 1, 5, 10, 20 days (inclusive of selected end date), a selected calendar month, or a custom inclusive start/end date. Shows period totals and every matching transaction, with an export to CSV containing its period and generation time.
- **Authentication:** One owner account, created explicitly by a one-time terminal command. No public sign-up and no additional roles.

There is **no demo data**. Figures and exports are calculated from the signed-in owner's saved database transactions.

## Quick start — Docker Compose (recommended)

Requires Docker Engine + Docker Compose. Docker runs the PostgreSQL database, FastAPI application, and built React site.

1. From this folder, make a local environment file:

   ```bash
   cp .env.example .env
   ```

2. Change `DB_PASSWORD` and `JWT_SECRET` in `.env`. Use different random secrets. For example, run this command **twice**, saving one value for each:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Keep `DB_PASSWORD` URL-safe (letters, digits, underscores, and hyphens) because it is embedded in the database connection URL. Do not commit `.env`.

3. Start all services:

   ```bash
   docker compose up -d --build
   ```

   The backend automatically applies Alembic migrations at startup. PostgreSQL data persists in the `postgres_data` Docker volume.

4. Create the **single owner** (run once):

   ```bash
   docker compose exec backend python -m app.create_owner
   ```

   Enter your email and a password of **12–128 characters**. The password is entered invisibly, hashed using Argon2id, and never stored in plain text. A second owner cannot be created through this command once one exists.

5. Visit **http://localhost:8080**, sign in, and start adding transactions.

   To change the local port, set `HTTP_PORT` in `.env`. The web app and PostgreSQL host ports bind to `127.0.0.1` rather than the public network by default.

Useful commands:

```bash
docker compose logs -f backend      # inspect API/migration startup
docker compose ps                   # check service status
docker compose down                 # stop; keeps database data
docker compose up -d --build        # rebuild after source changes
```

**Do not run `docker compose down -v` unless you intentionally want to delete the database volume.**

## Local development (without Docker for frontend/backend)

You need Python 3.11+, Node.js 20+, npm, and PostgreSQL 16+.

1. Set up PostgreSQL. You can reuse the Docker database: after creating the root `.env`, run `docker compose up -d db`.
2. Create a PostgreSQL database named `gharkhata` and an appropriately limited database user if using an existing PostgreSQL installation.
3. In `backend/`, create and activate a virtual environment, then install requirements:

   ```bash
   cd backend
   python -m venv .venv
   # Linux/macOS:
   source .venv/bin/activate
   # Windows PowerShell: .venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt
   cp .env.example .env
   ```

   Adjust `backend/.env`: `DATABASE_URL=postgresql+psycopg://gharkhata:YOUR_DB_PASSWORD@localhost:5432/gharkhata`, set a fresh `JWT_SECRET`, leave `COOKIE_SECURE=false`, and keep `CORS_ORIGINS=http://localhost:5173`. The frontend dev server proxies `/api` to `localhost:8000` so browser requests use the same origin.

4. Run migrations, create your owner, and start the backend:

   ```bash
   alembic upgrade head
   python -m app.create_owner
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

5. Open a **second terminal**:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

6. Visit **http://localhost:5173**.

To verify a frontend production build, run `cd frontend && npm run build`.

## Tests

From `backend/`, after `pip install -r requirements-dev.txt`:

```bash
python -m pytest -q
```

The API test suite uses an **isolated in-memory SQLite database** for fast, deterministic request tests. It covers sign-in, protected endpoints, CSRF, login throttling, session revocation, create/edit/delete, category and amount validation, month filtering, reporting, CSV metadata/formula injection protection, and per-user record isolation. **Production uses PostgreSQL via `DATABASE_URL`, not SQLite.**

Alembic migration can be verified by applying `alembic upgrade head` against the configured database. For a full deployment check, test CRUD and CSV export through the running PostgreSQL-backed site.

## Production deployment (HTTPS)

The Compose application serves HTTP on **127.0.0.1:8080**, intended to sit behind a trusted HTTPS reverse proxy (e.g., Caddy or Nginx with TLS). Do not expose the local HTTP port directly on the public internet.

1. Point your domain, e.g., `finance.example.com`, to the server.
2. Set these values in the root `.env` before starting:

   ```dotenv
   ENVIRONMENT=production
   COOKIE_SECURE=true
   CORS_ORIGINS=https://finance.example.com
   ALLOWED_HOSTS=finance.example.com,localhost,127.0.0.1,frontend
   ```

   Keep strong, unique `DB_PASSWORD` and `JWT_SECRET`. The backend refuses to start with insecure cookies or an HTTP allowed origin in production mode.

3. Install and configure HTTPS at your reverse proxy. Example **Caddyfile**:

   ```caddy
   finance.example.com {
       reverse_proxy 127.0.0.1:8080
       header Strict-Transport-Security "max-age=31536000"
   }
   ```

   Caddy can obtain/renew a certificate automatically when DNS and ports 80/443 are set up correctly. If you use another reverse proxy, enable TLS and HSTS there. Forward the original Host header.

4. Start using `docker compose up -d --build`, create the owner if it does not already exist, and sign in at `https://finance.example.com`.
5. Protect the host with firewall rules, restrict server administration, back up the PostgreSQL volume/data regularly, and apply OS/dependency security updates. Consider upstream request throttling as a second defense against brute-force traffic.

To back up the database:

```bash
docker compose exec -T db pg_dump -U gharkhata -d gharkhata > gharkhata-backup.sql
```

Keep backups private and test your recovery process before relying on them.

## Backend security design

- **Passwords:** Argon2id hash (`argon2-cffi`), never plain text. Login uses the same error for unknown users and wrong passwords.
- **Sessions:** Signed HS256 JWT stored in an **HttpOnly, SameSite=Strict** cookie, with `Secure` in HTTPS production. Tokens expire after eight hours. Signing in again or signing out increments the owner's `session_version`, invalidating earlier sessions server-side.
- **CSRF:** Mutating API routes require a session-bound `X-CSRF-Token`, returned only via authenticated same-origin API responses; writes also check the Origin header where present. CORS allows only the origins explicitly configured in environment settings.
- **Authorization:** Every transaction query, update, deletion, dashboard calculation, and report is scoped to the authenticated user's ID. No public registration or unsecured transaction endpoint.
- **Validation:** FastAPI/Pydantic and database CHECK constraints enforce valid transaction types/categories and positive decimal amounts. SQLAlchemy parameterizes database access. React renders user descriptions as text, not raw HTML. CSV descriptions are protected against spreadsheet formula injection.
- **Login throttling:** Five failed attempts per IP in a rolling 15-minute window, stored in process memory. Run one API worker as configured. In Docker, the private backend trusts `X-Real-IP` **only** because Nginx overwrites it; do not enable `TRUST_PROXY_HEADERS=true` when exposing the API directly. When adding another upstream reverse proxy (such as Caddy), configure trusted client-IP forwarding correctly or attempts may be grouped under that proxy's IP. For more than one worker/container, use shared rate limiting at your reverse proxy.
- **Secrets:** Only environment variables contain the database URL and JWT signing key. Vite frontend code has no secret. Production API errors do not include Python tracebacks.

## Project layout

```text
GharKhata/
├── .env.example
├── compose.yaml
├── README.md
├── backend/
│   ├── .env.example
│   ├── Dockerfile
│   ├── requirements.txt / requirements-dev.txt
│   ├── alembic.ini
│   ├── alembic/versions/0001_initial.py
│   ├── app/
│   │   ├── config.py, database.py, models.py, schemas.py
│   │   ├── security.py, main.py, create_owner.py
│   └── tests/
└── frontend/
    ├── Dockerfile, nginx.conf
    ├── package.json, vite.config.ts, tailwind.config.js
    └── src/
        ├── App.tsx
        ├── components/
        └── lib/
```

## Data model and calculation rules

Only two application tables: **users** and **transactions** (plus Alembic's migration metadata table). Each transaction has `id`, `user_id`, `type`, `amount`, `category`, `date`, `description`, `created_at`, and `updated_at`. Amounts use PostgreSQL `NUMERIC(11,2)` and Python `Decimal`.

All summary values follow **Remaining Balance = Total Income − Total Expenses**. Dashboard cards reflect the **selected month**. Reports and CSVs reflect **only the selected inclusive date range**, even if it includes days in other months. Transaction history defaults to all saved entries and can be filtered by month, type, category, and description.

## Security audit and QA retest (2026-11-04 UTC)

See [`QA_SECURITY_AND_TEST_REPORT.md`](QA_SECURITY_AND_TEST_REPORT.md) for initial findings, exact reproduction steps, three narrow fixes and retest evidence. The corrected ZIP includes 13 additional regression tests, so `python -m pytest -q` should now run **21 backend tests**. These tests use SQLite in-memory; PostgreSQL staging, full React production build, browser responsive UI and HTTPS deployment still require verification before production sign-off.
