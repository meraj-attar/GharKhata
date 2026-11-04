"""Independent GharKhata audit regression cases, authored against uploaded ZIP."""
import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from app.main import csv_safe
from app.security import verify_password
from app.models import User
from sqlalchemy import select
from sqlalchemy.orm import Session

BASE = {'type':'expense','amount':'20.50','category':'Grocery','date':'2026-11-03','description':'audit'}

def add(client,headers,**overrides):
    r=client.post('/api/transactions',headers=headers,json={**BASE,**overrides})
    assert r.status_code==201, r.text
    return r.json()

def test_s01_unauthenticated_all_private_routes(client):
    http,_ = client
    for path in ['/api/auth/me','/api/transactions','/api/dashboard?month=2026-11',
                 '/api/reports?start_date=2026-11-01&end_date=2026-11-03',
                 '/api/reports/export?start_date=2026-11-01&end_date=2026-11-03']:
        assert http.get(path).status_code==401, path
    assert http.post('/api/transactions',json=BASE).status_code==401
    assert http.put('/api/transactions/00000000-0000-0000-0000-000000000001',json=BASE).status_code==401
    assert http.delete('/api/transactions/00000000-0000-0000-0000-000000000001').status_code==401

def test_s02_host_origin_cors_and_csrf(auth_client):
    http,headers,_=auth_client
    assert http.get('/api/health',headers={'Host':'bad.example'}).status_code==400
    preflight=http.options('/api/transactions',headers={'Origin':'https://bad.example','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'X-CSRF-Token'})
    assert preflight.headers.get('access-control-allow-origin') is None
    assert http.post('/api/transactions',json=BASE,headers={**headers,'Origin':'https://bad.example'}).status_code==403
    assert http.post('/api/transactions',json=BASE,headers={'X-CSRF-Token':'wrong'}).status_code==403
    assert http.post('/api/transactions',json=BASE).status_code==403
    assert http.get('/api/auth/me').headers['cache-control']=='no-store'
    assert http.get('/openapi.json').status_code==404

def test_s03_signed_token_tampering_rejected(auth_client):
    http,headers,_=auth_client
    good=http.cookies.get('gharkhata_session')
    http.cookies.set('gharkhata_session',good[:-8]+'AAAAAAAA')
    assert http.get('/api/auth/me').status_code==401

def test_s04_sql_injection_and_search_wildcards(auth_client):
    http,headers,_=auth_client
    add(http,headers,description="test ' OR 1=1 --")
    add(http,headers,description='100% milk')
    add(http,headers,description='A_B')
    assert len(http.get('/api/transactions?search=%27%20OR%201%3D1%20--').json()) == 1
    assert len(http.get('/api/transactions?search=%25').json()) == 1
    assert len(http.get('/api/transactions?search=_').json()) == 1
    assert len(http.get('/api/transactions').json()) == 3

def test_f01_persist_exact_decimals_and_edit_delete(auth_client):
    http,headers,_=auth_client
    a=add(http,headers,type='income',category='Income',amount='1000.10')
    b=add(http,headers,amount='0.20')
    c=add(http,headers,amount='0.30')
    result=http.get('/api/dashboard?month=2026-11').json()
    assert (result['total_income'],result['total_expenses'],result['remaining_balance'])==('1000.10','0.50','999.60')
    e=http.put('/api/transactions/'+b['id'],headers=headers,json={**BASE,'amount':'55.35','category':'Bills'}).json()
    assert e['updated_at'] and e['amount']=='55.35'
    assert http.delete('/api/transactions/'+c['id'],headers=headers).status_code==204
    result=http.get('/api/dashboard?month=2026-11').json()
    assert (result['total_income'],result['total_expenses'],result['remaining_balance'])==('1000.10','55.35','944.75')
    assert {c['category'] for c in result['categories']}=={'Bills'}

def test_f02_day_windows_1_5_10_20_inclusive(auth_client):
    http,headers,_=auth_client
    end=date(2026,11,20)
    for i in range(25):
        d=(end-timedelta(days=i)).isoformat()
        add(http,headers,date=d,amount='1.01')
    for days in [1,5,10,20]:
        start=(end-timedelta(days=days-1)).isoformat()
        res=http.get('/api/reports',params={'start_date':start,'end_date':end.isoformat()})
        assert res.status_code==200
        data=res.json()
        assert len(data['transactions']) == days
        assert data['total_expenses'] == str(Decimal('1.01')*days)
        assert data['remaining_balance'] == str(Decimal('-1.01')*days)
        assert len(data['categories'])==1

def test_f03_month_leap_year_custom_cross_year(auth_client):
    http,headers,_=auth_client
    for d in ['2024-02-28','2024-02-29','2024-03-01','2025-12-31','2026-01-01']:
        add(http,headers,date=d,amount='10.00')
    assert http.get('/api/dashboard?month=2024-02').json()['total_expenses']=='20.00'
    assert http.get('/api/dashboard?month=2024-03').json()['total_expenses']=='10.00'
    assert len(http.get('/api/reports?start_date=2025-12-31&end_date=2026-01-01').json()['transactions'])==2
    assert http.get('/api/reports?start_date=2026-01-02&end_date=2026-01-01').status_code==422

def test_f04_csv_entries_metadata_and_formula_ascii(auth_client):
    http,headers,_=auth_client
    add(http,headers,description='=1+1',date='2026-11-01')
    add(http,headers,description='Should be omitted',date='2026-11-02')
    res=http.get('/api/reports/export?start_date=2026-11-01&end_date=2026-11-01')
    assert res.status_code==200
    rows=list(csv.reader(io.StringIO(res.content.decode('utf-8-sig'))))
    assert rows[1]==['Period','2026-11-01 to 2026-11-01']
    assert rows[2][0]=='Generated (UTC)'
    assert ['Total Expenses (INR)','20.50'] in rows
    assert ['2026-11-01','Expense','Grocery','20.50',"'=1+1"] in rows
    assert not any('2026-11-02' in cell for row in rows for cell in row)

def test_v01_missing_and_malformed_inputs(auth_client):
    http,headers,_=auth_client
    for d in [dict(amount=''),dict(amount='0'),dict(amount='-1'),dict(amount='1.001'),
              dict(amount='1000000000.00'),dict(category='Income'),dict(type='transfer'),
              dict(date='2026-02-30'),dict(description='x'*241)]:
        assert http.post('/api/transactions',headers=headers,json={**BASE,**d}).status_code==422,d
    assert http.post('/api/transactions',headers=headers,json={k:v for k,v in BASE.items() if k!='amount'}).status_code==422
    assert http.post('/api/transactions',headers=headers,json={**BASE,'description':None}).status_code==201

def test_v02_transaction_numeric_date_must_be_rejected(auth_client):
    http,headers,_=auth_client
    for x in [0,86400]:
        r=http.post('/api/transactions',headers=headers,json={**BASE,'date':x})
        assert r.status_code==422, f'{x} unexpectedly accepted as {r.json().get("date")}'

def test_v03_unknown_transaction_fields_must_be_rejected(auth_client):
    http,headers,_=auth_client
    r=http.post('/api/transactions',headers=headers,json={**BASE,'user_id':'00000000-0000-0000-0000-000000000001'})
    assert r.status_code==422, f'Extraneous user_id silently accepted: {r.status_code}'

def test_s05_unicode_hidden_prefix_formula_must_be_escaped():
    for prefix in ['\ufeff','\u200b','\u200e','\u2060']:
        out=csv_safe(prefix+'=2+3')
        assert out.startswith("'"),f'Unsafe prefix {prefix.encode("unicode_escape")} -> {out!r}'

def test_s06_hashing_and_session_cookie_flags(auth_client):
    http,headers,engine=auth_client
    with Session(engine) as s:
        user=s.scalar(select(User).where(User.email=='owner@example.com'))
        assert user.password_hash.startswith('$argon2id$')
        assert 'strong-test-pass-123' not in user.password_hash
        assert verify_password('strong-test-pass-123',user.password_hash)
    assert http.get('/api/transactions').status_code==200
    assert 'HttpOnly' in http.post('/api/auth/login',json={'email':'owner@example.com','password':'strong-test-pass-123'}).headers['set-cookie']
