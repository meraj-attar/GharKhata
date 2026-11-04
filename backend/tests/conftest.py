import os

# Configure a local SQLite test database before importing the API. Production uses PostgreSQL.
os.environ['DATABASE_URL'] = 'sqlite+pysqlite://'
os.environ['JWT_SECRET'] = 'test-secret-with-at-least-thirty-two-characters-long'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['CORS_ORIGINS'] = 'http://testserver'
os.environ['ALLOWED_HOSTS'] = 'testserver,localhost'
os.environ['ENVIRONMENT'] = 'development'

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.security import _login_failures, hash_password


@pytest.fixture
def client():
    engine = create_engine('sqlite+pysqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(email='owner@example.com', password_hash=hash_password('strong-test-pass-123')))
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    _login_failures.clear()
    with TestClient(app) as test_client:
        yield test_client, engine
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def auth_client(client):
    http, engine = client
    response = http.post('/api/auth/login', json={'email': 'owner@example.com', 'password': 'strong-test-pass-123'})
    assert response.status_code == 200, response.text
    return http, {'X-CSRF-Token': response.json()['csrf_token']}, engine
