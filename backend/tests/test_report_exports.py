"""Content and security regression tests using isolated dummy household records."""
import io
from datetime import date, timedelta
from decimal import Decimal

from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transaction, TransactionIdempotency, User
from app.security import hash_password

BASE = dict(type='expense', amount='25.50', category='Grocery', date='2026-01-05',
            description='Milk & supplies')
PERIOD = dict(start_date='2026-01-01', end_date='2026-12-31')


def add(http, headers, **updates):
    response = http.post('/api/transactions', json={**BASE, **updates}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def export(http, fmt, report_type='yearly', **params):
    return http.get('/api/reports/export', params={
        **PERIOD, 'report_type': report_type, 'format': fmt,
        **({'year': 2026} if report_type == 'yearly' else {}), **params})


def pdf_text(payload):
    return '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(payload)).pages)


def docx_text(payload):
    doc = Document(io.BytesIO(payload))
    return '\n'.join(p.text for p in doc.paragraphs) + '\n' + '\n'.join(
        ' '.join(c.text for c in row.cells) for t in doc.tables for row in t.rows)


def seed(http, headers):
    add(http, headers, type='income', category='Income', amount='800.10', date='2026-01-01', description='Salary')
    add(http, headers, amount='0.20', date='2026-01-05', description='=1+1')
    add(http, headers, amount='25.50', category='Bills', date='2026-02-28', description='Internet')
    add(http, headers, amount='999.99', date='2025-12-31', description='Out of range')


def test_all_formats_contents_totals_and_filters(auth_client):
    http, headers, _ = auth_client
    seed(http, headers)
    dashboard = http.get('/api/reports', params=PERIOD).json()
    assert (dashboard['total_income'], dashboard['total_expenses'], dashboard['remaining_balance']) == (
        '800.10', '25.70', '774.40')
    results = {fmt: export(http, fmt) for fmt in ('xlsx', 'docx', 'pdf')}
    for fmt, res in results.items():
        assert res.status_code == 200, (fmt, res.text[:200] if fmt != 'pdf' else '')
        assert res.headers['content-disposition'].endswith(f'.{fmt}"')
        assert res.headers['cache-control'] == 'no-store'
        assert res.headers['x-content-type-options'] == 'nosniff'
        assert len(res.content) > 1000

    x = load_workbook(io.BytesIO(results['xlsx'].content), data_only=False)
    assert x.sheetnames == ['Financial Summary', 'Transactions', 'Monthly Breakdown']
    summary = x['Financial Summary']
    assert [Decimal(str(summary[f'B{i}'].value)) for i in (6, 7, 8)] == [
        Decimal('800.10'), Decimal('25.70'), Decimal('774.40')]
    transactions = x['Transactions']
    assert transactions.max_row == 4
    assert [transactions.cell(i, 2).value.date() if hasattr(transactions.cell(i,2).value,'date')
            else transactions.cell(i,2).value for i in range(2,5)] == [
        date(2026,2,28), date(2026,1,5), date(2026,1,1)]
    formula_cell = next(transactions.cell(i, 5) for i in range(2, 5)
                        if transactions.cell(i, 5).value == '=1+1')
    assert formula_cell.data_type == 's'  # never exported as an executable formula
    assert transactions.freeze_panes == 'A2'
    assert transactions.auto_filter.ref == 'A1:F4'
    monthly = x['Monthly Breakdown']
    assert monthly.max_row == 13
    assert Decimal(str(monthly['B2'].value)) == Decimal('800.10')
    assert Decimal(str(monthly['C3'].value)) == Decimal('25.50')

    word = docx_text(results['docx'].content)
    pdf = pdf_text(results['pdf'].content)
    for text in (word, pdf):
        for needle in ('800.10', '25.70', '774.40', 'Internet',
                       '=1+1', '2026-02', '2026-12'):
            assert needle in text, (needle, text[:900])
        assert '999.99' not in text

    # DOCX preserves the rupee symbol.
    assert '₹' in word

    # PDF uses 'INR' when the Unicode rupee glyph is unavailable in the
    # configured font (for example, the fallback font on Windows).
    assert '₹' in pdf or 'INR 800.10' in pdf, pdf[:900]

    assert 'Financial summary' in word and 'Financial summary' in pdf
    assert 'Monthly breakdown' in word and 'Monthly breakdown' in pdf
    assert results['xlsx'].headers['content-type'].startswith('application/vnd.openxmlformats')
    assert results['docx'].headers['content-type'].startswith('application/vnd.openxmlformats')
    assert results['pdf'].headers['content-type'].startswith('application/pdf')


def test_monthly_custom_transaction_and_empty_reports(auth_client):
    http, headers, _ = auth_client
    seed(http, headers)
    for fmt in ('xlsx', 'docx', 'pdf'):
        monthly = export(http, fmt, report_type='monthly', month='2026-01')
        assert monthly.status_code == 200
        if fmt == 'xlsx':
            x = load_workbook(io.BytesIO(monthly.content))
            assert x.sheetnames == ['Financial Summary', 'Transactions']
            assert x['Transactions'].max_row == 3
            assert Decimal(str(x['Financial Summary']['B7'].value)) == Decimal('0.20')
        elif fmt == 'docx':
            assert '800.10' in docx_text(monthly.content)
            assert '25.50' not in docx_text(monthly.content)
        else:
            assert '800.10' in pdf_text(monthly.content)
            assert '25.50' not in pdf_text(monthly.content)
        custom = export(http, fmt, report_type='custom', start_date='2026-02-28', end_date='2026-02-28')
        assert custom.status_code == 200
        tx = export(http, fmt, report_type='transactions', start_date='2026-02-28', end_date='2026-02-28')
        assert tx.status_code == 200
        empty = export(http, fmt, report_type='custom', start_date='2024-01-01', end_date='2024-01-02')
        assert empty.status_code == 200
        if fmt == 'xlsx':
            assert load_workbook(io.BytesIO(empty.content))['Transactions'].max_row == 1
        elif fmt == 'docx':
            assert 'No transactions in this period' in docx_text(empty.content)
        else:
            assert 'No transactions in this period' in pdf_text(empty.content)


def test_reject_unauthenticated_and_invalid_filters(auth_client):
    http, headers, _ = auth_client
    for fmt in ('xlsx', 'docx', 'pdf'):
        for request_args in [
            dict(format=fmt, report_type='monthly', month='2026-13'),
            dict(format=fmt, report_type='yearly', year='invalid'),
            dict(format=fmt, report_type='custom', start_date='2026-02-01', end_date='2026-01-01'),
            dict(format=fmt, report_type='custom', start_date='2026-01-01', end_date='2037-01-01'),
            dict(format=fmt, report_type='custom', start_date='2026-02-30', end_date='2026-03-01'),
        ]:
            assert http.get('/api/reports/export', params=request_args).status_code == 422
    assert export(http, 'xml').status_code == 422
    assert http.get('/api/reports/export?start_date=2026-01-01&end_date=2026-01-30&format=pdf&format=xlsx').status_code == 422
    assert export(http, 'pdf', report_type='oops').status_code == 422
    http.cookies.clear()
    for fmt in ('xlsx', 'docx', 'pdf'):
        assert export(http, fmt).status_code == 401


def test_only_owner_data_exported(auth_client):
    http, headers, engine = auth_client
    seed(http, headers)
    with Session(engine) as db:
        stranger = User(email='stranger@example.com', password_hash=hash_password('my-strong-password-234'))
        db.add(stranger)
        db.flush()
        db.add(Transaction(user_id=stranger.id, type='income', category='Income', amount=Decimal('999999.99'),
                           date=date(2026, 4, 1), description='STRANGER FINANCES'))
        db.commit()
        stranger_id = str(stranger.id)
    for fmt in ('xlsx', 'docx', 'pdf'):
        assert export(http, fmt, user_id=stranger_id).status_code == 422
        res = export(http, fmt)
        assert res.status_code == 200
        if fmt == 'xlsx':
            x = load_workbook(io.BytesIO(res.content))
            assert all('STRANGER' not in str(c.value) for row in x['Transactions'] for c in row)
        else:
            text = docx_text(res.content) if fmt == 'docx' else pdf_text(res.content)
            assert 'STRANGER' not in text
            assert '999,999.99' not in text


def test_large_pdf_repeats_headers_and_readable_pages(auth_client):
    http, headers, _ = auth_client
    with Session(_[0] if isinstance(_, tuple) else _) as db:
        user = db.scalar(select(User).where(User.email == 'owner@example.com'))
        for i in range(165):
            db.add(Transaction(user_id=user.id, type='expense', category='Bills',
                               amount=Decimal('1.01'), date=date(2026,1,1) + timedelta(days=i),
                               description='Receipt ' + str(i) + ' ' + ('A' * 200)))
        db.commit()
    res = export(http, 'pdf')
    assert res.status_code == 200
    reader = PdfReader(io.BytesIO(res.content))
    assert len(reader.pages) >= 3
    combined = pdf_text(res.content)
    assert 'Receipt 0' in combined and 'Receipt 164' in combined
    assert combined.count('Description') >= 2


def test_persistent_idempotency_and_csrf(auth_client):
    http, headers, engine = auth_client
    key = 'submission-key-a1'
    first = http.post('/api/transactions', json=BASE, headers={**headers, 'Idempotency-Key': key})
    assert first.status_code == 201
    second = http.post('/api/transactions', json=BASE, headers={**headers, 'Idempotency-Key': key})
    assert second.status_code == 201 and first.json()['id'] == second.json()['id']
    assert len(http.get('/api/transactions').json()) == 1
    assert http.post('/api/transactions', json={**BASE, 'amount': '44.00'},
                     headers={**headers, 'Idempotency-Key': key}).status_code == 409
    assert http.post('/api/transactions', json=BASE,
                     headers={**headers, 'Idempotency-Key': 'invalid key!'}).status_code in (400, 422)
    assert http.post('/api/transactions', json=BASE, headers={'Idempotency-Key': 'another'}).status_code == 403
    with Session(engine) as db:
        record = db.scalar(select(TransactionIdempotency).where(TransactionIdempotency.key == key))
        assert record is not None and str(record.transaction_id) == first.json()['id']


def test_expired_or_tampered_session_cannot_export(auth_client):
    from datetime import datetime, timedelta, timezone
    import jwt
    from app.config import get_settings
    http, _, engine = auth_client
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == 'owner@example.com'))
        now = datetime.now(timezone.utc)
        token = jwt.encode({
            'sub': str(user.id), 'iat': now - timedelta(days=2),
            'exp': now - timedelta(days=1), 'csrf': 'z' * 40, 'ver': user.session_version,
        }, get_settings().jwt_secret, algorithm='HS256')
    http.cookies.set('gharkhata_session', token)
    assert export(http, 'pdf').status_code == 401
    http.cookies.set('gharkhata_session', token + 'broken')
    assert export(http, 'xlsx').status_code == 401


def test_large_export_rejected(auth_client):
    import uuid
    http, _, engine = auth_client
    with Session(engine) as db:
        owner = db.scalar(select(User).where(User.email == 'owner@example.com'))
        db.execute(Transaction.__table__.insert(), [dict(
            id=uuid.uuid4(), user_id=owner.id, type='expense', amount=Decimal('0.01'),
            category='Grocery', date=date(2026, 1, 2),
            description='Bulk check', created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            updated_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
        ) for i in range(10001)])
        db.commit()
    assert export(http, 'pdf').status_code == 413


def test_production_config_rejects_unsafe_settings():
    from pydantic import ValidationError
    from app.config import Settings
    base = dict(database_url='postgresql+psycopg://finance:password@db.example/finance?sslmode=require',
                jwt_secret='RBWn8_Xi47_sEQ1M5N93fUa2bcvDkJZ8c2gXxRC8',
                environment='production', cookie_secure=True,
                cors_origins='https://finance.example.com', allowed_hosts='finance.example.com')
    assert Settings(**base).environment == 'production'
    for change in [dict(jwt_secret='a'*40), dict(cookie_secure=False),
                   dict(cors_origins='http://finance.example.com'), dict(allowed_hosts='*'),
                   dict(database_url='postgresql+psycopg://finance:password@db.example/finance')]:
        try:
            Settings(**{**base, **change})
        except ValidationError:
            continue
        raise AssertionError(f'Unsafe production settings accepted: {list(change)}')
