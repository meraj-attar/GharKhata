# GharKhata — Security Audit and QA Verification

**Review date:** 2026-11-04. **Input:** `GharKhata_QA_Fixed_Project.zip`, inspected and copied to a separate work directory. **Final output:** `GharKhata_Security_QA_Report_Export_Updated.zip`. No external systems or real financial accounts were tested. The uploaded archive was not overwritten.

## Executive result

**Conditional: backend tested, production rollout not yet verified.** The uploaded ZIP's original 21 backend tests passed before changes. After this update, **30 backend tests passed, 0 failed**; DOCX/PDF visual spot-checks completed; a SQLite Alembic upgrade to the new migration head succeeded. Frontend TS/TSX source passed syntax transpilation (10 files), but a *production frontend build could not be completed* because npm registry DNS/network access was unavailable, and there was no local `node_modules` directory. Do not mistake source parsing for a full typecheck, build, UI or browser download test.

## Verified findings and response

| Severity | Finding | Affected files | Fix and evidence |
|---|---|---|---|
| **Medium** | Transaction creation was not persistently idempotent in the supplied archive | `backend/app/main.py`, `backend/app/models.py`, new migration, `frontend/src/components/TransactionModal.tsx`, `frontend/src/lib/api.ts` | Unique per-user key/request hash/transaction association persisted; exact replay returns the existing record, different payload with the same key returns `409`; tests pass. |
| **Medium** | Production settings did not enforce encrypted PostgreSQL connection settings | `backend/app/config.py` | New production validation requires `sslmode=require`/`verify-ca`/`verify-full` for PostgreSQL; production configuration tests pass. Live Neon TLS connection is still untested. |
| **Low** | Existing response to authenticated API `401` did not always return the user to sign-in UI | `frontend/src/lib/api.ts`, `frontend/src/App.tsx` | Unified fetch error handling and session-expired event; reviewed and syntax parsed, not browser-tested. |
| **Low / deployment** | Uploaded archive still contained Dockerfiles, Compose, container Nginx and Docker-oriented README despite requested Docker removal | Docker files removed, `README.md`, new `render.yaml`, `render-build.sh` and deployment guide | Docker-specific files removed; native Render/Neon configuration and single-origin serving added. Deploy/build not yet verified. |
| **New feature risk addressed** | Export file text could become spreadsheet formulas or untrusted markup | `backend/app/report_exports.py` | Excel transaction strings forced to plain-text cells; PDF descriptions HTML-escaped; Word text uses document cell text. Test with `=1+1` confirmed no Excel formula. |
| **New feature risk addressed** | Owner records could leak across export requests, or large requests exhaust memory | `backend/app/main.py`, `backend/app/report_exports.py` | Report data always filtered by session `user.id`; unexpected query parameters rejected; 10,000-record and 10-year limits. Automated owner-isolation and `413` tests pass. |

Previously verified corrections preserved: strict ISO transaction-date strings (numeric dates rejected), strict request-field validation and Unicode-aware CSV formula escaping. Existing Argon2, HS256 JWT, user isolation, authorization, CSRF on writes, session revocation, rate limiting, trusted-host and CORS controls were not removed. **No critical finding was confirmed in the tests run; absence of a confirmed finding is not proof of no vulnerabilities.**

## QA execution matrix

| Check | Result | Evidence / limitation |
|---|---|---|
| Original backend tests before edits | **Passed (21/21)** | Isolated in-memory SQLite, FastAPI TestClient |
| Final backend tests | **Passed (30/30)** | `python -m pytest -q`, including original regression cases |
| XLSX generation, MIME, sheets, cells, formatting, filtering, empty ranges | **Passed** | `openpyxl.load_workbook` assertions on responses |
| DOCX generation, headings, summary, tables, empty ranges | **Passed** | `python-docx` reopened output and asserted content |
| PDF generation, totals, page text, multi-page repeated headers, empty ranges | **Passed** | `pypdf` parsed actual response bytes and multiple pages |
| Cross-format financial accuracy | **Passed** | 800.10 income − 25.70 expenses = 774.40, equal across XLSX/DOCX/PDF and `/api/reports` |
| Cross-user export isolation | **Passed** | A second user's dummy record never appeared in exports; forged user_id query rejected |
| Unauthenticated, expired/tampered session | **Passed** | All new formats deny with 401 |
| CSRF on transaction writes and idempotent retry | **Passed** | Missing CSRF rejected; duplicate key and conflict behavior tested |
| Input validation and large report cap | **Passed** | Invalid format/date/month/year, duplicate params and 10,001 transactions rejected |
| SQLite migrations through `0002_transaction_idempotency` | **Passed** | Live local Alembic upgrade + table metadata inspection |
| DOCX/PDF visual page quality spot-check | **Passed (spot-check)** | Rendered multi-page dummy reports; improved fixed-width Word table after visual review |
| React/TypeScript syntax/transpile | **Passed (10/10 files)** | Global TypeScript transpiler syntax diagnostics = 0 |
| Full React TypeScript typecheck and production bundle | **Not executed successfully** | `npm install` failed `EAI_AGAIN` (npm registry unavailable) |
| Browser-driven download/UI/mobile checks | **Not executed** | No installed frontend bundle/browser session |
| PostgreSQL/Neon integration, actual Render HTTPS deployment | **Not executed** | No live database or permitted deployment |
| Python dependency vulnerability/CVE scan | **Not executed** | No dependency audit scanner available; `pip check` on shared host reported an unrelated MoviePy/Pillow conflict |
| npm vulnerability scan | **Not executed** | No lockfile and offline registry; `npm audit --offline` returned `ENOLOCK` |

## Remaining risks and limitations

- **Production sign-off pending:** Real PostgreSQL schema/transaction behavior, Neon TLS, Render build/start, HTTPS cookies, browser downloads, mobile accessibility and large live datasets need staging tests.
- **Login rate limit is process-local:** The existing login throttle is not a distributed/shared limiter. Add upstream or shared-store protection if deploying multiple workers/replicas.
- **In-memory export scaling:** Generating Word/PDF/XLSX for 10,000 rows may use significant memory and take time; the endpoint is capped but not benchmarked against Render resource limits. Consider a smaller cap or background job for high-volume deployments.
- **`Idempotency-Key` remains optional for compatibility:** The updated frontend supplies it for new transaction submissions, but external API clients without the header are not retry-safe. Historical idempotency keys persist until related transactions/users are deleted; consider an explicit retention policy as volume grows.
- **Frontend lockfile:** The uploaded project had no `package-lock.json`; dependency reproducibility/security checks require generating and committing one in a network-enabled environment.
- **PDF fallback:** DejaVu Sans is used for the ₹ glyph when available, otherwise `INR` is printed without loss of monetary value; ensure the deployment host has suitable fonts if the ₹ symbol is mandatory.
- **No live deployment done:** `render.yaml` and build script are preparation artifacts only, not proof of a successful deployment.

## Test commands and source changes

```bash
cd GharKhata/backend
python -m pip install -r requirements-dev.txt
python -m pytest -q
alembic upgrade head
cd ../frontend
npm install
npm run typecheck
npm run build
```

The full source includes old and new tests, migrations `0001_initial` and `0002_transaction_idempotency`, React frontend source, requirements, revised README, native Render blueprint and both implementation/deployment guides. The original project archive remains unchanged. Files under `.venv`, `node_modules`, `__pycache__`, `.pytest_cache`, real `.env` and generated report/build artifacts are excluded from the packaged source.
