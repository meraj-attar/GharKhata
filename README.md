# GharKhata — Household Finance Management

GharKhata is a **private, single-owner household income and expense manager** built with React, TypeScript, Vite, Tailwind CSS, FastAPI, SQLAlchemy, Alembic and PostgreSQL. Money is stored as `NUMERIC(11,2)` and calculated in Python using `Decimal`.

## Features

- JWT authentication in **HttpOnly, SameSite=Strict** cookies; Argon2 password hashes; session revocation; request-bound CSRF on writes; login throttling.
- Dashboard with monthly totals, expense chart, recent transactions and category summaries.
- Income and expense transactions: add, edit, delete, search and filter. Idempotency keys protect against duplicate creation when the frontend retries an interrupted submission.
- Existing reports for the last 1, 5, 10 or 20 days, monthly or custom dates, plus yearly reports.
- **Excel (.xlsx), editable Word (.docx), PDF (.pdf)** and retained **CSV (.csv)** downloads from the existing Reports page. Select monthly, yearly, custom date range or transaction report. Actual authenticated data only; no mock financial data is used by the app.
- Neon PostgreSQL / Render deployment support without Docker.

## Local setup

Requirements: **Python 3.11+**, Node.js 20+, npm and a running PostgreSQL instance.

1. Create a PostgreSQL database named `gharkhata` and a least-privilege database user.
2. From `backend/` create and activate a virtual environment and install:

   ```bash
   python -m venv .venv
   # Linux/macOS:
   source .venv/bin/activate
   # Windows PowerShell: .venv\Scripts\Activate.ps1
   python -m pip install -r requirements-dev.txt
   ```

3. Copy `backend/.env.example` to `backend/.env`, configure PostgreSQL and a new random JWT secret:

   ```dotenv
   DATABASE_URL=postgresql+psycopg://gharkhata:your_password@localhost:5432/gharkhata
   JWT_SECRET=paste_a_secure_random_token_of_at_least_32_characters_here
   ENVIRONMENT=development
   COOKIE_SECURE=false
   CORS_ORIGINS=http://localhost:5173
   ALLOWED_HOSTS=localhost,127.0.0.1,testserver
   TRUST_PROXY_HEADERS=false
   ```

   Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Keep actual credentials out of Git. In production, use `COOKIE_SECURE=true`, an HTTPS origin, an explicit allowed host, and a PostgreSQL URL with `?sslmode=require` or stronger.
4. Apply all migrations, create the original single-owner account, then run the API:

   ```bash
   cd backend
   alembic upgrade head
   python -m app.create_owner
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

5. In another terminal:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

6. Open `http://localhost:5173`. The dev server proxies `/api` to the backend, so cookies and API downloads stay on the same browser origin.

### How to download

Sign in, open **Reports & downloads**, choose a period or the export's **Report type** menu (Monthly, Yearly, Custom or Transactions), select **Excel**, **Word**, or **PDF**, and press **Download Report**. The original **Download CSV** button remains available above the summary cards. Empty periods produce zero-value summary reports, not invented records.

### Tests

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q
cd ../frontend
npm install
npm run typecheck
npm run build
```

The backend suite uses in-memory SQLite test records and checks authentication, CSRF, financial values, file contents and user isolation. Use a disposable PostgreSQL staging database to validate its dialect, migrations and deployed query performance before launching publicly. `npm install` requires registry access.

## Architecture and report limitations

`frontend/src/components/Reports.tsx` → `frontend/src/lib/api.ts` → authenticated `GET /api/reports/export` → `app.main.period_data()` / `totals()` → `app.report_exports` → browser `Blob` download.

All three formats use exactly one report-data snapshot. Expenses are grouped by the existing categories, and yearly/multi-month exports include monthly breakdowns. Reports are read-only. For memory safety, an export is limited to **10,000 transactions** and a **10-year** reporting period. Split larger exports into shorter periods. Full browser testing and a real Neon/Render deployment still require staging verification.

## Deployment and audit documentation

- [Render + Neon deployment guide](DEPLOYMENT_RENDER_NEON.md)
- [Export implementation guide](REPORT_EXPORT_IMPLEMENTATION_GUIDE.md)
- [Security audit and QA report](QA_SECURITY_AND_TEST_REPORT.md)

The application is prepared for single-domain hosting. `render-build.sh` builds the Vite frontend and installs the Python backend; after the frontend is built, FastAPI serves the resulting `frontend/dist` at `/` and its API at `/api`. Render must provide both Python and Node/npm during build; alternatively arrange an equivalent build pipeline and keep the same-origin architecture. Database schema upgrades are performed in a pre-deploy step.

**Do not use Docker:** the previous Dockerfiles, Compose file, Docker ignore files and container-only Nginx configuration have been removed.
