# GharKhata — Render + Neon Deployment Guide

**Deployment status:** Configured, not deployed or verified against a live Neon database or public Render service. The included `render.yaml` is a starting blueprint; confirm settings in your Render account and test on staging.

## Architecture

Serve **React and FastAPI from one HTTPS hostname** to preserve same-origin cookie authentication. In the included design, `render-build.sh` builds `frontend/dist`; FastAPI mounts this static directory at `/` after `/api` handlers. This makes `/api` requests and browser cookies same-origin, as in Vite development. Do not split frontend and backend onto separate public domains without carefully redesigning cookie/CORS/auth rules.

## Neon database

1. Create a Neon PostgreSQL database and a dedicated limited-permission application user. Obtain the **SQLAlchemy-compatible** connection URI.
2. Use a URL such as `postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require`; percent-encode special characters in credentials. For more stringent certificate validation, configure `verify-full` and the required CA trust as appropriate.
3. Set `DATABASE_URL` as a **secret environment variable in Render**, never in Git or Vite frontend settings.
4. Verify reachability, SSL, connection pooling and backups from a staging service. Serverless connection behavior and Neon pooler configuration are not verified by this package.

## Render native web service

Import the repository/blueprint from GitHub or configure one Render Web Service rooted at the `GharKhata` project directory, using the Python native runtime. Ensure **Python 3.11+ and Node.js 20+ / npm** are available during the build. Some native build images may not provide Node; if so, arrange Node installation or build the static assets in CI and make the resulting `frontend/dist` available in deployment. Do not replace this with Docker unless changing the architecture intentionally.

- **Build:** `bash render-build.sh` (pip install backend dependencies, npm install, Vite build).
- **Pre-deploy:** `cd backend && alembic upgrade head` (run for each release; migrate schema before startup).
- **Start:** `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- **Health check:** `/api/health`.
- For the native web service, use the host assigned by Render (e.g. `your-service.onrender.com`) in both `CORS_ORIGINS` (with `https://`) and `ALLOWED_HOSTS` (host only).

Environment variables:

```dotenv
ENVIRONMENT=production
COOKIE_SECURE=true
TRUST_PROXY_HEADERS=false
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
JWT_SECRET=<generated-with-secrets.token_urlsafe(48)>
CORS_ORIGINS=https://your-service.onrender.com
ALLOWED_HOSTS=your-service.onrender.com
```

Store actual secret values only in the Render secrets dashboard. These examples are placeholders. Production config rejects insecure cookies, HTTP origins, wildcard hosts, obvious placeholder/low-diversity secrets and PostgreSQL connections without `sslmode=require` (or stronger). Generated reports are held only in memory and set `Cache-Control: no-store`.

## Verification checklist in staging

1. Confirm the deployed app loads at the correct HTTPS origin and `/api/health` returns `200`.
2. Confirm `alembic current` reports `0002_transaction_idempotency` on the **actual Neon database**.
3. Create the owner once using a trusted Render shell/admin process (`cd backend && python -m app.create_owner`); do not enable a public signup endpoint.
4. Sign in from a browser, inspect cookie flags (`HttpOnly`, `Secure`, `SameSite=Strict`), create a sample transaction and retry the same idempotency key.
5. Compare dashboard totals and exported XLSX/DOCX/PDF/CSV totals. Verify an empty report, multi-page report, invalid date, logged-out download, download filename and mobile layout.
6. Review staging logs for unexpected errors without exposing private financial records. Confirm the app can reload and still access persistent Neon data.
7. Configure least-privilege database credentials, backup/restore exercises, edge rate limiting, uptime alerts, dependency scans and private access controls before production traffic.

PDF export embeds DejaVu Sans from standard Linux font paths when installed. If unavailable, it safely uses `INR` in place of the rupee glyph. For embedded `₹`, provision `fonts-dejavu-core` (or equivalent) on the host without packaging font binaries with the application.

**Not verified here:** Render native Node availability, a production frontend build, actual Render pre-deploy execution, Neon connectivity, PostgreSQL-specific idempotency concurrency, HTTPS browser behavior and live deployments. Complete those steps before relying on a public release.
