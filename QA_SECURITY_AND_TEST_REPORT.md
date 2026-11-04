# GharKhata — Security Audit, Functional QA, and Retest Report

**Audit date:** 2026-11-04 UTC  
**Original artifact:** `GharKhata_FullStack_Source.zip` (42 files, SHA-256 `aaa0c05c7029b78087635f31102ef5d9ad27276e8d0b1ddcd1076b458190bf18`)  
**Scope:** Existing uploaded React/TypeScript + FastAPI + PostgreSQL-ready project.  
**Method:** Original ZIP extracted into a preserved, untouched audit directory. Baseline and additional tests executed against original source first; confirmed defects fixed in a separate working copy and retested. No transactions or real personal data were provided or used.

## Executive result

**Status: CONDITIONAL — corrected API passes available automated and live-HTTP checks, but full production readiness has NOT been established.** Live PostgreSQL, Docker Compose, the React production bundle, browser-level workflows, responsive device rendering, and deployed HTTPS could not be exercised in this environment. Do not treat those items as passing tests.

| Execution set | Original project | Corrected project | Method |
|---|---|---|---|
| Existing backend API tests | **8 PASS / 0 FAIL** | **8 PASS / 0 FAIL** | Pytest + FastAPI TestClient + isolated SQLite |
| Independent extended security/functional cases | **10 PASS / 3 FAIL** | **13 PASS / 0 FAIL** | Pytest + FastAPI TestClient + isolated SQLite |
| Live loopback HTTP checks | Not executed before repairs | **15 PASS / 0 FAIL** | Running Uvicorn, actual HTTP, persisted SQLite test DB, server restart |
| Owner setup and migration | **PASS** | Same original migration | Alembic on SQLite + interactive input simulated with mocks |
| DB CHECK constraints | Not executed before repairs | **4 PASS** | Raw invalid-row inserts against migrated SQLite |
| Frontend TS/TSX syntax parses | **10 PASS** | **10 PASS** | TypeScript transpile syntax diagnostics (NOT full build/type-check) |
| Frontend date/currency helper checks | **5 PASS** | **5 PASS** | Executed transpiled TypeScript in Node.js |
| Actual browser/responsive UI | **NOT RUN** | **NOT RUN** | npm packages unavailable; no bundled frontend to load |
| PostgreSQL/Docker/production TLS | **NOT RUN** | **NOT RUN** | PostgreSQL server, Docker, and live TLS endpoint unavailable |

The baseline results are repeatable with `cd backend && python -m pytest -q` from the appropriate project copy. The independent regression tests are included under `backend/tests/test_qa_regressions.py` in the corrected ZIP.

## Confirmed findings and fixes

### GH-01 — Medium — Numeric transaction dates silently converted

- **Affected original code:** `backend/app/schemas.py:14–19`, particularly `date: date` at original line **18**.
- **How to reproduce against ORIGINAL:** Sign in and use the session cookie and CSRF header. `POST /api/transactions` with JSON `{"type":"expense","amount":"20.50","category":"Grocery","date":0,"description":"audit"}`.
- **Observed before:** `201 Created`; response returned `"date":"1970-01-01"`. `date:86400` similarly became `1970-01-02`. An incorrect date was silently saved.
- **Expected:** Only an explicit valid `YYYY-MM-DD` date string accepted; malformed/numeric dates rejected with HTTP 422.
- **Fix:** `backend/app/schemas.py:24–30` now validates ISO date *input type and format before Pydantic coercion*; calendar validity remains validated by Pydantic.
- **Retest:** **PASS.** Tests `test_v02_transaction_numeric_date_must_be_rejected` and live HTTP numeric-date check return 422; valid transaction dates and reports still work.

### GH-02 — Low — Unexpected transaction fields silently ignored

- **Affected original code:** `backend/app/schemas.py:14–19` (default Pydantic model behavior).
- **How to reproduce against ORIGINAL:** Sign in and submit the normal transaction JSON with an additional `"user_id":"00000000-0000-0000-0000-000000000001"` key.
- **Observed before:** `201 Created`, unexpected key silently ignored. **This is not an ownership bypass**: the backend still forcibly set the authenticated user ID.
- **Expected:** Undeclared request keys must be rejected instead of ambiguously accepted.
- **Fix:** `backend/app/schemas.py:15–16` sets `ConfigDict(extra='forbid')` for `TransactionInput`.
- **Retest:** **PASS.** Test `test_v03_unknown_transaction_fields_must_be_rejected` and live HTTP check return 422; ordinary create/edit continue passing.

### GH-03 — Medium — Unicode-prefix bypass of CSV formula sanitizer

- **Affected original code:** `backend/app/main.py:219–223`, original `csv_safe` function.
- **How to reproduce against ORIGINAL:** Run in the backend environment: `from app.main import csv_safe; print(repr(csv_safe('\ufeff=2+3')))`; analogous test strings with U+200B, U+200E, and U+2060 also bypassed the intended prefixing check.
- **Observed before:** The value was emitted **without** an escape apostrophe, e.g. `'\ufeff=2+3'` in Python `repr` (no actual leading apostrophe in the cell).
- **Expected:** A cell that could be treated as an executable spreadsheet formula after ignoring leading invisible characters must be escaped.
- **Fix:** `backend/app/main.py:220–229` treats leading whitespace, Unicode format marks, and control characters as ignorable when checking formula prefixes; the CSV cell receives a literal apostrophe if the first significant character is `=`, `+`, `-`, or `@`.
- **Retest:** **PASS.** Test `test_s05_unicode_hidden_prefix_formula_must_be_escaped` checks four Unicode prefixes. A live-HTTP CSV download containing U+FEFF plus `=2+3` also verified the escaped output.
- **Qualification:** A sanitizer bypass was reproduced; execution of a spreadsheet formula in desktop Excel or another spreadsheet program **was not tested**. Severity reflects a potential CSV injection exposure, not a demonstrated remote-code execution vulnerability.

### Confirmed high or critical vulnerabilities

**None observed by the tests executed.** This is not a guarantee none exist, especially without browser, dependency, PostgreSQL, external penetration, and production TLS testing.

## Security cases: execution matrix

| ID | Check | Initial | After fixes | Evidence / limitations |
|---|---|---|---|---|
| SEC-01 | Password hashed with Argon2id; no plaintext in DB | PASS | PASS | DB inspection after owner CLI + API test |
| SEC-02 | Owner setup and second owner-creation attempt | PASS | PASS | Alembic SQLite migration + owner `main()` with mocked interactive entry; second attempt blocked |
| SEC-03 | Invalid credentials and brute-force threshold | PASS | PASS | Original test: 5 failures, next attempt 429; per-process/IP implementation |
| SEC-04 | Expired/invalid/tampered session denied | PASS | PASS | JWT tamper returns 401; session revocation test passes; expiry enforced by code (expiry-time advance not run) |
| SEC-05 | Unauthorized transaction/dashboard/report/export reads and writes | PASS | PASS | TestClient 401 for protected routes |
| SEC-06 | Other user cannot read, edit, delete, or report owner's records | PASS | PASS | Original isolation test inserts separate second user in test DB |
| SEC-07 | CSRF rejection and forbidden request Origin | PASS | PASS | Missing/wrong header 403; foreign Origin 403 |
| SEC-08 | CORS disallows unapproved origin; trusted Host rejected | PASS | PASS | Preflight has no allow-origin; bad Host returns 400 |
| SEC-09 | SQL injection attempts in search input | PASS | PASS | Search text treated as literal; SQLAlchemy ORM bound parameters |
| SEC-10 | Search wildcard input `%` and `_` treated literally | PASS | PASS | Endpoint request tests |
| SEC-11 | CSV formula protection (ordinary ASCII prefixes) | PASS | PASS | CSV parser assertions on actual response |
| SEC-12 | CSV formula protection (invisible Unicode prefixes) | **FAIL** | **PASS** | GH-03, test function and live HTTP CSV |
| SEC-13 | Malformed, missing, oversized, invalid category/type/amount | PASS | PASS | API 422 for invalid payloads |
| SEC-14 | Strict transaction date format | **FAIL** | **PASS** | GH-01, original API 201 for numeric date; fixed 422 |
| SEC-15 | Unknown transaction field rejection | **FAIL** | **PASS** | GH-02, original API 201; fixed 422 |
| SEC-16 | No API response caching / closed API docs | PASS | PASS | `Cache-Control: no-store`; `/openapi.json` returns 404 |
| SEC-17 | DB check constraints on type, amount and category | NOT RUN | PASS | Four invalid raw DB writes rejected on migrated SQLite |
| SEC-18 | Production config rejects HTTP cookies/origins and placeholder secret | NOT RUN | PASS | Three `Settings` model validation checks |
| SEC-19 | XSS in React-rendered descriptions | CODE REVIEW | CODE REVIEW | JSX text interpolation; no `dangerouslySetInnerHTML` found; **not browser-verified** |
| SEC-20 | Sensitive credentials not embedded in frontend | CODE REVIEW | CODE REVIEW | Source scan: API secrets via backend settings/env; actual deployed bundle **not built** |
| SEC-21 | HTTPS and secure cookie flag in real production deployment | NOT RUN | NOT RUN | HTTPS proxy, real browsers and TLS unavailable; configuration reviewed |
| SEC-22 | Package vulnerability/CVE scan | NOT RUN | NOT RUN | Offline npm, no authoritative dependency vulnerability scan |

## Functional test cases: execution matrix

| ID | Test | Original | After fixes | Execution evidence |
|---|---|---|---|---|
| FUN-01 | One-time owner creation and login | PASS | PASS | Owner CLI and HTTP login |
| FUN-02 | Add valid income / expense | PASS | PASS | JSON API, persisted SQLite |
| FUN-03 | Edit transaction and update totals | PASS | PASS | TestClient and running Uvicorn |
| FUN-04 | Delete transaction; re-read totals | PASS | PASS | TestClient and running Uvicorn |
| FUN-05 | Precision: income minus expenses exact to paise | PASS | PASS | `1000.10 - 0.20 - 0.30 = 999.60`; live `1234.56 - 234.50 = 1000.06` |
| FUN-06 | Dashboard month selection/expense daily chart data | PASS | PASS | API monthly totals, daily values and month length; chart rendering NOT browser-tested |
| FUN-07 | Transaction list and search, type/category/month filters | PASS | PASS | API GET filters; frontend input UI NOT clicked |
| FUN-08 | 1-day, 5-day, 10-day, 20-day inclusive ranges | PASS | PASS | Four ranges, exactly 1/5/10/20 persisted entries each |
| FUN-09 | Monthly report including leap-day February | PASS | PASS | Feb 2024 includes 29th; March excluded |
| FUN-10 | Custom report spanning year; invalid inverted range | PASS | PASS | Correct 2025-12-31 to 2026-01-01; inverted 422 |
| FUN-11 | CSV totals, generation date, period and included entries | PASS | PASS | Parsed exported CSV; out-of-period transaction excluded |
| FUN-12 | Negative/zero/too-precise/oversized amount; empty/malformed inputs | PASS | PASS | API 422 |
| FUN-13 | Numeric date rejected | FAIL | PASS | GH-01 |
| FUN-14 | Unrecognized request field rejected | FAIL | PASS | GH-02 |
| FUN-15 | Logout, session invalidation and unauthorized-after-logout | PASS | PASS | API tests and live HTTP |
| FUN-16 | Saved entries persist through a server restart | NOT RUN | PASS | Real Uvicorn process stopped/restarted, records retained in SQLite file |
| FUN-17 | Frontend month, date arithmetic and ₹ currency format | PASS | PASS | 5 Node-executed helper assertions |
| FUN-18 | Add/edit/delete modal UI, confirmation buttons, navigation | NOT RUN | NOT RUN | No React production bundle available |
| FUN-19 | Mobile, tablet and desktop visual responsiveness | NOT RUN | NOT RUN | No running frontend in Chromium; media class patterns source-reviewed only |
| FUN-20 | Frontend build/type-check, Recharts runtime rendering | NOT RUN | NOT RUN | npm offline dependency installation fails with `ENOTCACHED` |

## Frontend and UI review

- **Source syntax:** 10 TypeScript/TSX files parsed successfully with the TypeScript compiler `transpileModule`, reporting zero syntax diagnostics. This **does not** provide a full type-check or verify imports, API integration in-browser, layout, or accessibility.
- **Date/currency utilities:** five runtime checks passed, including leap-year month end, cross-year report start dates, and rupee formatting.
- **Source-only design inspection:** desktop navy sidebar, mobile bottom navigation, report date buttons, edit/delete confirmation, chart components, responsive Tailwind breakpoints, and empty states are present in JSX. Their actual display and clicking behavior **have not been tested**.
- **Blocker:** `npm install --offline` failed with `ENOTCACHED`, and the public npm registry was not reachable. React/Recharts dependencies were not available; the production frontend build, browser-click QA, screenshots, mobile/tablet viewport checks and download behavior through browser UI remain unverified.

## Deployment / database verification limitations and remaining risks

1. **PostgreSQL and Docker not exercised (unverified):** The test database was SQLite, not PostgreSQL. Alembic's initial migration created `users`, `transactions`, and `alembic_version` on SQLite, with expected CHECK constraints and composite `(user_id, date)` index. Real PostgreSQL migrations, connection pooling, DB permissions, Docker Compose networking, backups, and deployed persistence require a staging run.
2. **TLS not exercised (unverified):** The included Compose setup binds HTTP to localhost and the README recommends HTTPS termination upstream. Verify `ENVIRONMENT=production`, `COOKIE_SECURE=true`, HTTPS origins, correct allowed hosts, a valid certificate and an HTTPS-only public endpoint in staging.
3. **Rate limiting is process-local (Low operational residual risk):** Five failures per IP in 15 minutes are tested, but counters clear on worker restart and are not shared across multiple workers/replicas. The included Compose uses one backend worker. If scaling out, add edge/shared throttling; do not mistake this for distributed brute-force protection.
4. **Dependencies/build reproducibility (Low operational residual risk):** No frontend package lockfile was included in the uploaded project; package versions can drift. Generate/commit a lockfile and complete a production build in a networked staging environment. No dependency CVE scan was possible here.
5. **XSS/browser behavior (unverified):** User text is rendered using standard React interpolation and appears escaped by design. Actual browser DOM/XSS tests remain outstanding.
6. **Test environment only:** All audit test accounts, credentials and transaction examples were disposable. Never use the test JWT secret or SQLite test database in production.

## Changed files in corrected ZIP

- `backend/app/schemas.py` — strict date input and rejection of undeclared transaction fields (GH-01, GH-02)
- `backend/app/main.py` — Unicode-aware CSV formula sanitization (GH-03)
- `backend/tests/test_qa_regressions.py` — 13 audit regression test cases
- `QA_SECURITY_AND_TEST_REPORT.md` — this report
- `README.md` — brief audit/retesting reference

**No unrelated features, database schema changes, or frontend visual redesign were introduced.** The original uploaded ZIP remains unchanged.

## Commands to reproduce local checks

```bash
cd GharKhata/backend
python -m pip install -r requirements-dev.txt
python -m pytest -q          # corrected project: 21 tests expected
```

To run in PostgreSQL-backed staging (not done during this audit): set production-safe environment secrets, run `docker compose up -d --build`, create the owner using `docker compose exec backend python -m app.create_owner`, then repeat real-browser login, add/edit/delete, all report periods, CSV download, logout and mobile viewport tests. Verify permissions, backup/recovery and HTTPS before public deployment.

## Final verdict

**The three confirmed issues have been repaired and re-tested successfully, with all 21 backend tests passing.** The live HTTP smoke check also passed **15/15**. This is a strong result for the backend and code paths exercised, **not** a full production sign-off: PostgreSQL, the complete React bundle, browser/UI responsiveness, dependency security and HTTPS production behavior still require staging verification.
