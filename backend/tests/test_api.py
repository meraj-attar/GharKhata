from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.security import hash_password


def transaction(type='expense', amount='250.50', category='Grocery', date='2026-11-03', description='Daily shopping'):
    return dict(type=type, amount=amount, category=category, date=date, description=description)


def create(client, headers, **changes):
    data = transaction()
    data.update(changes)
    response = client.post('/api/transactions', json=data, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_login_and_protected_endpoints(client):
    http, _ = client
    assert http.get('/api/transactions').status_code == 401
    assert http.get('/api/dashboard?month=2026-11').status_code == 401
    assert http.get('/api/reports?start_date=2026-11-01&end_date=2026-11-10').status_code == 401
    assert http.post('/api/auth/login', json={'email': 'owner@example.com', 'password': 'wrong'}).status_code == 401
    login = http.post('/api/auth/login', json={'email': 'owner@example.com', 'password': 'strong-test-pass-123'})
    assert login.status_code == 200
    assert 'HttpOnly' in login.headers['set-cookie']
    assert 'samesite=strict' in login.headers['set-cookie'].lower()
    assert http.get('/api/auth/me').json()['email'] == 'owner@example.com'
    assert http.post('/api/auth/logout').status_code == 403
    assert http.post('/api/auth/logout', headers={'X-CSRF-Token': login.json()['csrf_token']}).status_code == 204
    assert http.get('/api/auth/me').status_code == 401


def test_login_limit_and_origin(client):
    http, _ = client
    for _ in range(5):
        assert http.post('/api/auth/login', json={'email': 'owner@example.com', 'password': 'wrong'}).status_code == 401
    assert http.post('/api/auth/login', json={'email': 'owner@example.com', 'password': 'strong-test-pass-123'}).status_code == 429
    assert http.post('/api/auth/login', headers={'Origin': 'https://evil.example'}, json={'email': 'owner@example.com', 'password': 'strong-test-pass-123'}).status_code == 403


def test_create_read_update_delete_and_csrf(auth_client):
    http, headers, _ = auth_client
    data = transaction()
    assert http.post('/api/transactions', json=data).status_code == 403
    first = create(http, headers)
    assert first['amount'] == '250.50'
    assert http.get('/api/transactions').json()[0]['id'] == first['id']
    update = transaction(type='income', category='Income', amount='2000.00', description='Salary')
    assert http.put('/api/transactions/' + first['id'], json=update, headers=headers).status_code == 200
    summary = http.get('/api/dashboard?month=2026-11').json()
    assert summary['total_income'] == '2000.00'
    assert summary['total_expenses'] == '0.00'
    assert summary['remaining_balance'] == '2000.00'
    assert http.delete('/api/transactions/' + first['id']).status_code == 403
    assert http.delete('/api/transactions/' + first['id'], headers=headers).status_code == 204
    assert http.get('/api/transactions').json() == []
    assert http.get('/api/dashboard?month=2026-11').json()['remaining_balance'] == '0.00'
    assert http.delete('/api/transactions/' + first['id'], headers=headers).status_code == 404


def test_validation_and_category_limits(auth_client):
    http, headers, _ = auth_client
    cases = [
        {'amount': '-2.00'}, {'amount': '0'}, {'amount': '1.234'},
        {'amount': '1000000000.00'}, {'type': 'transfer'},
        {'category': 'Shopping'}, {'type': 'income'},
        {'type': 'income', 'category': 'Grocery'},
        {'type': 'expense', 'category': 'Income'},
        {'description': 'x' * 241}, {'date': 'invalid'},
    ]
    for changes in cases:
        response = http.post('/api/transactions', json={**transaction(), **changes}, headers=headers)
        assert response.status_code == 422, (changes, response.text)
    assert http.post('/api/transactions', headers={**headers, 'Origin': 'https://attacker.example'}, json=transaction()).status_code == 403


def test_dashboard_month_and_report_ranges(auth_client):
    http, headers, _ = auth_client
    create(http, headers, type='income', category='Income', amount='10000.00', date='2026-10-31', description='Old salary')
    create(http, headers, type='income', category='Income', amount='2000.10', date='2026-11-01', description='Salary')
    create(http, headers, amount='125.25', date='2026-11-01')
    create(http, headers, amount='24.75', category='Medical', date='2026-11-03', description='Medicine')
    create(http, headers, amount='50.00', category='Bills', date='2026-11-06')
    create(http, headers, amount='75.00', category='Personal', date='2026-12-01')
    november = http.get('/api/dashboard?month=2026-11').json()
    assert november['total_income'] == '2000.10'
    assert november['total_expenses'] == '200.00'
    assert november['remaining_balance'] == '1800.10'
    assert len(november['daily_expenses']) == 30
    assert november['daily_expenses'][0]['amount'] == '125.25'
    assert len(november['recent_transactions']) == 4
    assert len(http.get('/api/transactions?month=2026-11').json()) == 4
    assert len(http.get('/api/transactions?category=Medical').json()) == 1
    assert len(http.get('/api/transactions?search=Medicine').json()) == 1
    assert len(http.get('/api/transactions?type=income').json()) == 2
    assert http.get('/api/dashboard?month=2026-13').status_code == 422
    report = http.get('/api/reports?start_date=2026-11-01&end_date=2026-11-05').json()
    assert report['total_income'] == '2000.10'
    assert report['total_expenses'] == '150.00'
    assert report['remaining_balance'] == '1850.10'
    assert len(report['transactions']) == 3
    assert {c['category'] for c in report['categories']} == {'Grocery', 'Medical'}
    assert http.get('/api/reports?start_date=2026-11-10&end_date=2026-11-01').status_code == 422
    assert http.get('/api/reports?start_date=2026-01-01&end_date=2026-01-02').json()['transactions'] == []


def test_csv_metadata_boundary_and_formula_injection(auth_client):
    http, headers, _ = auth_client
    create(http, headers, date='2026-11-01', description='=HYPERLINK("evil")')
    create(http, headers, date='2026-11-10')
    res = http.get('/api/reports/export?start_date=2026-11-01&end_date=2026-11-01')
    assert res.status_code == 200
    assert 'text/csv' in res.headers['content-type']
    csv_data = res.content.decode('utf-8-sig')
    assert '2026-11-01 to 2026-11-01' in csv_data
    assert 'Generated (UTC)' in csv_data
    assert '250.50' in csv_data
    assert "'=HYPERLINK" in csv_data
    assert '2026-11-10' not in csv_data


def test_user_isolation(auth_client):
    http, headers, engine = auth_client
    first = create(http, headers)
    with Session(engine) as db:
        db.add(User(email='other@example.com', password_hash=hash_password('other-strong-test-pass')))
        db.commit()
    # Replace session cookie by signing in as the second user.
    login = http.post('/api/auth/login', json={'email': 'other@example.com', 'password': 'other-strong-test-pass'})
    other_headers = {'X-CSRF-Token': login.json()['csrf_token']}
    assert http.get('/api/transactions').json() == []
    assert http.put('/api/transactions/' + first['id'], headers=other_headers, json=transaction()).status_code == 404
    assert http.delete('/api/transactions/' + first['id'], headers=other_headers).status_code == 404
    assert http.get('/api/reports?start_date=2026-11-01&end_date=2026-11-30').json()['transactions'] == []


def test_new_login_invalidates_previous_session(client):
    http, _ = client
    first = http.post('/api/auth/login', json={'email': 'owner@example.com', 'password': 'strong-test-pass-123'})
    old_cookie = first.cookies.get('gharkhata_session')
    second = http.post('/api/auth/login', json={'email': 'owner@example.com', 'password': 'strong-test-pass-123'})
    assert second.status_code == 200
    assert first.json()['csrf_token'] != second.json()['csrf_token']
    assert http.get('/api/auth/me', headers={'Cookie': f'gharkhata_session={old_cookie}'}).status_code == 401
    assert http.get('/api/auth/me').status_code == 200
    assert http.post('/api/auth/logout', headers={'X-CSRF-Token': second.json()['csrf_token']}).status_code == 204
    assert http.get('/api/auth/me', headers={'Cookie': f'gharkhata_session={second.cookies.get("gharkhata_session")}' }).status_code == 401
