# GharKhata — Report Export Implementation Guide

## What's new

The existing Reports screen now supports **Excel, Word, PDF** exports in addition to the retained CSV button. This is not a second application; it reuses the current JWT-cookie session, CSRF-on-write conventions, database access, report filters and Decimal financial calculations.

### Files created

- `backend/app/report_exports.py`: XLSX, DOCX and PDF renderers, common currency and monthly breakdown helpers, and shared MIME type definitions.
- `backend/alembic/versions/0002_transaction_idempotency.py`: persistent `transaction_idempotency` table, keyed by the authenticated user and request idempotency key.
- `backend/tests/test_report_exports.py`: content inspection of each format, cross-user security, filters, empty/large exports, expired sessions, idempotency and production config checks.
- `render-build.sh`, `render.yaml`, `DEPLOYMENT_RENDER_NEON.md`: native Render + Neon preparation.
- This guide and the refreshed QA report.

### Files modified

- `backend/app/main.py`: existing reports export endpoint extended; owner-scoped query and centralized `period_data` preserved; bounded export size, strict filters and safe response headers; transaction creation now supports persistent idempotency; optional React static build serving.
- `backend/app/models.py`: idempotency mapping table, with original tables unchanged.
- `backend/app/config.py`: validate HTTPS origins, explicit hosts, non-placeholder secret, secure cookies and PostgreSQL SSL mode in production.
- `backend/requirements.txt`: adds `openpyxl`, `python-docx`, `reportlab`.
- `backend/requirements-dev.txt`: adds `pypdf` for PDF content tests.
- `frontend/src/components/Reports.tsx`: format selector, report type selector, yearly filter, loading and notifications; existing date filters and CSV action retained.
- `frontend/src/lib/api.ts`: shared cookie-authenticated JSON/binary request helper; safe response errors and filename handling; idempotency key support.
- `frontend/src/components/TransactionModal.tsx`: stable idempotency UUID per unchanged create submission/retry.
- `frontend/src/App.tsx`: return to login screen after expired authenticated API session.
- README and safe environment samples updated for native development and deployment.

### Original features retained

Login/logout/session restore, transaction CRUD, Decimal totals, existing dashboards and charts, categories, monthly and custom reports, CSV export, security headers, Argon2, JWT, SameSite cookie and CSRF validation, user isolation and original database migration remain in source.

## New export endpoint

Authenticated `GET /api/reports/export`; supported query parameters:

| Parameter | Values | Notes |
|---|---|---|
| `format` | `csv` (default), `xlsx`, `docx`, `pdf` | CSV default preserves the original URL behavior |
| `report_type` | `monthly`, `yearly`, `custom` (default), `transactions` | Determines title/period behavior |
| `month` | `YYYY-MM` | Required for monthly; inclusive month bounds calculated by backend |
| `year` | integer 1–9999 | Required for yearly; inclusive calendar year |
| `start_date`, `end_date` | ISO date | Required for custom and transaction reports; inclusive |

Example request URLs (after signing in):

```text
/api/reports/export?format=xlsx&report_type=monthly&month=2026-11
/api/reports/export?format=docx&report_type=yearly&year=2026
/api/reports/export?format=pdf&report_type=custom&start_date=2026-01-01&end_date=2026-04-30
/api/reports/export?format=pdf&report_type=transactions&start_date=2026-11-01&end_date=2026-11-30
/api/reports/export?start_date=2026-11-01&end_date=2026-11-30
```

Missing/invalid filters return `422`; over 10,000 matching transactions return `413`; unauthenticated/expired/tampered sessions return `401`. Unexpected or duplicated query parameters are rejected. Export does not take a user ID; the backend always filters by `auth.user.id`.

### Formats and rendering

**Excel** (`openpyxl`): creates `Financial Summary` and `Transactions` sheets, adding `Monthly Breakdown` for annual/multi-month ranges. All amounts are numeric Excel cells formatted for INR, dates are Excel date values, table headers styled, columns sized, rows frozen and transaction filters enabled. Untrusted text is forced to literal string cells to prevent spreadsheet formula execution.

**Word** (`python-docx`): editable title, period, financial summary, categories, transaction table and optional monthly summary. Repeated table headers, fixed table widths, page numbers and rupee-formatted amounts. User descriptions remain editable text.

**PDF** (`reportlab`): printable landscape A4, alternating table rows, section headings, embedded DejaVu fonts for `₹` where available, page numbers, repeated transaction headers and long-text wrapping. If DejaVu fonts are unavailable, the safe `INR` currency label is used instead; no external fonts or private financial data are bundled in the ZIP.

**CSV**: original BOM/CSV output and formula escaping retained with the original endpoint default.

### Financial consistency

The existing `totals(transactions)` function remains the sole source of period income, expenses, balance and expense categories. Each export calls `period_data()` once. A month-by-month breakdown groups the same selected transactions by their existing income/expense types with `Decimal`; it does not invent new financial rules. No export operation writes to the database.

### Frontend download behavior

The browser sends an authenticated same-origin `fetch()` with session cookies. It receives a validated binary `Blob`, extracts the safe server filename from `Content-Disposition`, creates a temporary object URL, and automatically clicks an invisible download anchor. It then releases the object URL. `401` invalidates the visible app session. The UI provides a generation spinner, an error, a success notice and an empty-period explanation. GET downloads do not mutate server state and therefore do not require a CSRF header; original POST/PUT/DELETE CSRF requirements remain active.

### Retesting locally

With local backend packages installed and a dedicated test database:

```bash
cd backend
python -m pytest -q
python -m alembic upgrade head
```

For manual testing, sign in at `http://localhost:5173`, create a few **test** transactions, compare the Reports dashboard summary with the downloaded Excel, Word and PDF values, then try each report type, empty range and invalid range. For production readiness, repeat through the actual HTTPS hostname with a Neon-backed staging database. The automated suite parses workbook cells, DOCX tables and PDF page text — it does not merely check that a file exists.
