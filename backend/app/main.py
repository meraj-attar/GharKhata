import csv
import hashlib
import json
import re
import io
import calendar
import unicodedata
import uuid
from pathlib import Path
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.report_exports import MIME_TYPES, build_export
from app.database import get_db
from app.models import Transaction, TransactionIdempotency, User
from app.schemas import (Category, ExpenseCategory, EXPENSE_CATEGORIES, LoginInput,
                         MeOut, TransactionInput, TransactionKind, TransactionOut)
from app.security import (AuthContext, COOKIE_NAME, check_login_limit, clear_login_failures,
                          get_auth, record_login_failure, require_csrf, set_session_cookie, client_ip,
                          verify_password, _dummy_hash)

settings = get_settings()
app = FastAPI(title='GharKhata API', docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True,
                   allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Content-Type', 'X-CSRF-Token'])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.hosts)


@app.middleware('http')
async def no_store(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/api'):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
    return response


def require_origin(request: Request):
    origin = request.headers.get('origin')
    if origin and origin.rstrip('/') not in settings.origins:
        raise HTTPException(status_code=403, detail='Invalid request origin')


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.post('/api/auth/login', response_model=MeOut)
def login(body: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    require_origin(request)
    ip = client_ip(request)
    check_login_limit(ip)
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    encoded_hash = user.password_hash if user else _dummy_hash
    password_ok = verify_password(body.password, encoded_hash)
    if user is None or not password_ok:
        record_login_failure(ip)
        raise HTTPException(status_code=401, detail='Invalid email or password')
    clear_login_failures(ip)
    user.session_version += 1  # revoke any previously issued session (single-owner app)
    db.commit()
    csrf = set_session_cookie(response, user)
    return {'email': user.email, 'csrf_token': csrf}


@app.get('/api/auth/me', response_model=MeOut)
def me(auth: AuthContext = Depends(get_auth)):
    return {'email': auth.user.email, 'csrf_token': auth.csrf_token}


@app.post('/api/auth/logout', status_code=204)
def logout(request: Request, auth: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    require_origin(request)
    auth.user.session_version += 1  # server-side session revocation
    db.commit()
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME, path='/api', secure=settings.cookie_secure, httponly=True, samesite='strict')
    return response


def month_bounds(month: str) -> tuple[date, date]:
    try:
        if len(month) != 7 or month[4] != '-':
            raise ValueError
        year, month_number = int(month[:4]), int(month[5:])
        if not 1 <= month_number <= 12:
            raise ValueError
        start = date(year, month_number, 1)
        end = date(year, month_number, calendar.monthrange(year, month_number)[1])
    except (ValueError, OverflowError):
        raise HTTPException(status_code=422, detail='Month must be YYYY-MM') from None
    return start, end


def owned_transaction(db: Session, user_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction:
    transaction = db.scalar(select(Transaction).where(Transaction.id == transaction_id,
                                                       Transaction.user_id == user_id))
    if transaction is None:
        raise HTTPException(status_code=404, detail='Transaction not found')
    return transaction


@app.get('/api/transactions', response_model=list[TransactionOut])
def list_transactions(
    month: str | None = None,
    type: TransactionKind | None = None,
    category: Category | None = None,
    search: str | None = Query(default=None, max_length=100),
    auth: AuthContext = Depends(get_auth), db: Session = Depends(get_db),
):
    query = select(Transaction).where(Transaction.user_id == auth.user.id)
    if month:
        start, end = month_bounds(month)
        query = query.where(Transaction.date >= start, Transaction.date <= end)
    if type:
        query = query.where(Transaction.type == type)
    if category:
        query = query.where(Transaction.category == category)
    if search and search.strip():
        escaped = search.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        term = f'%{escaped}%'
        query = query.where(or_(Transaction.description.ilike(term, escape='\\'),
                                Transaction.category.ilike(term, escape='\\')))
    return db.scalars(query.order_by(Transaction.date.desc(), Transaction.created_at.desc())).all()


@app.post('/api/transactions', response_model=TransactionOut, status_code=201)
def create_transaction(body: TransactionInput, request: Request,
                       idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
                       auth: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    require_origin(request)
    if idempotency_key is not None:
        if not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', idempotency_key):
            raise HTTPException(status_code=422, detail='Invalid Idempotency-Key')
        fingerprint = hashlib.sha256(json.dumps(body.model_dump(mode='json'),
                                               sort_keys=True).encode('utf-8')).hexdigest()
        existing = db.get(TransactionIdempotency, (auth.user.id, idempotency_key))
        if existing:
            if existing.request_hash != fingerprint:
                raise HTTPException(status_code=409, detail='Idempotency key reused with different content')
            transaction = owned_transaction(db, auth.user.id, existing.transaction_id)
            return transaction
    transaction = Transaction(user_id=auth.user.id, **body.model_dump())
    db.add(transaction)
    if idempotency_key is not None:
        db.flush()  # transaction UUID must exist before mapping the replay key
        db.add(TransactionIdempotency(user_id=auth.user.id, key=idempotency_key,
                                      request_hash=fingerprint, transaction_id=transaction.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key is None:
            raise
        existing = db.get(TransactionIdempotency, (auth.user.id, idempotency_key))
        if existing is None:
            raise  # unrelated integrity error; do not disguise it
        if existing.request_hash != fingerprint:
            raise HTTPException(status_code=409, detail='Idempotency key reused with different content') from None
        return owned_transaction(db, auth.user.id, existing.transaction_id)
    db.refresh(transaction)
    return transaction


@app.put('/api/transactions/{transaction_id}', response_model=TransactionOut)
def update_transaction(transaction_id: uuid.UUID, body: TransactionInput, request: Request,
                       auth: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    require_origin(request)
    transaction = owned_transaction(db, auth.user.id, transaction_id)
    for field, value in body.model_dump().items():
        setattr(transaction, field, value)
    db.commit()
    db.refresh(transaction)
    return transaction


@app.delete('/api/transactions/{transaction_id}', status_code=204)
def delete_transaction(transaction_id: uuid.UUID, request: Request,
                       auth: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    require_origin(request)
    transaction = owned_transaction(db, auth.user.id, transaction_id)
    db.delete(transaction)
    db.commit()
    return Response(status_code=204)


def totals(transactions: list[Transaction]):
    income = sum((t.amount for t in transactions if t.type == 'income'), Decimal('0.00'))
    expense = sum((t.amount for t in transactions if t.type == 'expense'), Decimal('0.00'))
    categories = {category: Decimal('0.00') for category in EXPENSE_CATEGORIES}
    for transaction in transactions:
        if transaction.type == 'expense':
            categories[transaction.category] += transaction.amount
    return {
        'total_income': str(income.quantize(Decimal('0.01'))),
        'total_expenses': str(expense.quantize(Decimal('0.01'))),
        'remaining_balance': str((income - expense).quantize(Decimal('0.01'))),
        'categories': [{'category': c, 'amount': str(amount.quantize(Decimal('0.01')))}
                       for c, amount in categories.items() if amount > 0],
    }


@app.get('/api/dashboard')
def dashboard(month: str, auth: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    start, end = month_bounds(month)
    transactions = db.scalars(select(Transaction).where(
        Transaction.user_id == auth.user.id, Transaction.date >= start,
        Transaction.date <= end).order_by(Transaction.date.desc(), Transaction.created_at.desc())).all()
    summary = totals(transactions)
    daily: dict[int, Decimal] = defaultdict(lambda: Decimal('0.00'))
    for transaction in transactions:
        if transaction.type == 'expense':
            daily[transaction.date.day] += transaction.amount
    return {
        **summary,
        'daily_expenses': [{'day': day, 'amount': str(daily[day].quantize(Decimal('0.01')))}
                           for day in range(1, end.day + 1)],
        'recent_transactions': [TransactionOut.model_validate(t) for t in transactions[:5]],
    }


def period_data(db: Session, user_id: uuid.UUID, start: date, end: date, limit: int | None = None):
    if start > end:
        raise HTTPException(status_code=422, detail='Start date cannot be after end date')
    query = (select(Transaction).where(
        Transaction.user_id == user_id, Transaction.date >= start, Transaction.date <= end)
        .order_by(Transaction.date.desc(), Transaction.created_at.desc()))
    if limit is not None:
        query = query.limit(limit)
    transactions = db.scalars(query).all()
    return {
        'start_date': start.isoformat(), 'end_date': end.isoformat(),
        **totals(transactions),
        'transactions': [TransactionOut.model_validate(t) for t in transactions],
    }


@app.get('/api/reports')
def report(start_date: date, end_date: date, auth: AuthContext = Depends(get_auth),
           db: Session = Depends(get_db)):
    return period_data(db, auth.user.id, start_date, end_date)


def csv_safe(value: str | None) -> str:
    """Protect spreadsheet users against formula injection in free-text cells."""
    if not value:
        return ''
    # Some spreadsheet engines ignore invisible leading Unicode format/control marks.
    # Treat a formula starter after any such prefix as unsafe, preserving the original text.
    prefix = 0
    while prefix < len(value) and (value[prefix].isspace() or unicodedata.category(value[prefix]) in ('Cf', 'Cc')):
        prefix += 1
    return "'" + value if value[prefix:].startswith(('=', '+', '-', '@')) else value


@app.get('/api/reports/export')
def export_report(
    request: Request, start_date: date | None = None, end_date: date | None = None,
    format: str = Query(default='csv', pattern=r'^(csv|xlsx|docx|pdf)$'),
    report_type: str = Query(default='custom', pattern=r'^(monthly|yearly|custom|transactions)$'),
    month: str | None = Query(default=None, max_length=7),
    year: int | None = Query(default=None, ge=1, le=9999),
    auth: AuthContext = Depends(get_auth), db: Session = Depends(get_db),
):
    allowed = {'start_date', 'end_date', 'format', 'report_type', 'month', 'year'}
    supplied = [key for key, _ in request.query_params.multi_items()]
    if any(key not in allowed for key in supplied) or len(supplied) != len(set(supplied)):
        raise HTTPException(status_code=422, detail='Unexpected or duplicated report filter')
    if report_type == 'monthly':
        if month is None:
            raise HTTPException(status_code=422, detail='Month is required for monthly reports')
        start_date, end_date = month_bounds(month)
    elif report_type == 'yearly':
        if year is None:
            raise HTTPException(status_code=422, detail='Year is required for yearly reports')
        start_date, end_date = date(year, 1, 1), date(year, 12, 31)
    elif start_date is None or end_date is None:
        raise HTTPException(status_code=422, detail='Start and end dates are required')
    if (end_date - start_date).days > 3660:
        raise HTTPException(status_code=422, detail='Maximum report period is 10 years')
    data = period_data(db, auth.user.id, start_date, end_date, limit=10001)
    if len(data['transactions']) > 10000:
        raise HTTPException(status_code=413, detail='Report exceeds 10,000 transactions. Select a shorter period.')
    if format != 'csv':
        body = build_export(data, format, report_type)
        filename = f'GharKhata_{report_type}_{start_date.isoformat()}_to_{end_date.isoformat()}.{format}'
        return Response(content=body, media_type=MIME_TYPES[format], headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'X-Content-Type-Options': 'nosniff',
        })
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['GharKhata - Household Finance Manager'])
    writer.writerow(['Period', f'{start_date.isoformat()} to {end_date.isoformat()}'])
    writer.writerow(['Generated (UTC)', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')])
    writer.writerow([])
    writer.writerow(['Total Income (INR)', data['total_income']])
    writer.writerow(['Total Expenses (INR)', data['total_expenses']])
    writer.writerow(['Remaining Balance (INR)', data['remaining_balance']])
    writer.writerow([])
    writer.writerow(['Expense Category', 'Amount (INR)'])
    for row in data['categories']:
        writer.writerow([row['category'], row['amount']])
    writer.writerow([])
    writer.writerow(['Date', 'Type', 'Category', 'Amount (INR)', 'Description'])
    for t in data['transactions']:
        writer.writerow([t.date.isoformat(), t.type.title(), t.category,
                         str(t.amount), csv_safe(t.description)])
    filename = f'GharKhata_{start_date.isoformat()}_to_{end_date.isoformat()}.csv'
    return Response(content='\ufeff' + output.getvalue(), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})


# Render single-service hosting keeps the browser and API on the same origin,
# preserving HttpOnly SameSite=Strict cookie and relative /api request security.
_frontend_dist = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
if _frontend_dist.is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount('/', StaticFiles(directory=str(_frontend_dist), html=True), name='frontend')
