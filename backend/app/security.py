import secrets
import ipaddress
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User

SESSION_SECONDS = 8 * 60 * 60
COOKIE_NAME = 'gharkhata_session'
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
# Equalize verification time for an unknown email.
_dummy_hash = password_hasher.hash('a-password-that-is-not-in-use')
_login_failures: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = threading.Lock()


def hash_password(raw: str) -> str:
    if not 12 <= len(raw) <= 128:
        raise ValueError('Password must be 12 to 128 characters long')
    return password_hasher.hash(raw)


def verify_password(raw: str, encoded: str) -> bool:
    try:
        return bool(password_hasher.verify(encoded, raw))
    except (VerifyMismatchError, VerificationError, ValueError):
        return False


def check_login_limit(ip: str):
    now = time.monotonic()
    with _rate_lock:
        attempts = _login_failures[ip]
        while attempts and now - attempts[0] > 900:
            attempts.popleft()
        if len(attempts) >= 5:
            raise HTTPException(status_code=429, detail='Too many login attempts. Try again later.')


def record_login_failure(ip: str):
    with _rate_lock:
        _login_failures[ip].append(time.monotonic())


def clear_login_failures(ip: str):
    with _rate_lock:
        _login_failures.pop(ip, None)


def set_session_cookie(response: Response, user: User) -> str:
    now = datetime.now(timezone.utc)
    csrf = secrets.token_urlsafe(32)
    token = jwt.encode(
        {'sub': str(user.id), 'iat': now, 'exp': now + timedelta(seconds=SESSION_SECONDS), 'csrf': csrf, 'ver': user.session_version},
        get_settings().jwt_secret, algorithm='HS256',
    )
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, secure=get_settings().cookie_secure,
        samesite='strict', max_age=SESSION_SECONDS, path='/api',
    )
    return csrf


@dataclass
class AuthContext:
    user: User
    csrf_token: str


def get_auth(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Sign in required')
    try:
        payload = jwt.decode(
            token, get_settings().jwt_secret, algorithms=['HS256'],
            options={'require': ['sub', 'exp', 'iat', 'csrf', 'ver']},
        )
        user_id = uuid.UUID(payload['sub'])
        csrf = payload['csrf']
        if not isinstance(csrf, str) or len(csrf) < 32:
            raise ValueError('Invalid token')
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise HTTPException(status_code=401, detail='Session expired or invalid') from None
    user = db.get(User, user_id)
    if user is None or payload['ver'] != user.session_version:
        raise HTTPException(status_code=401, detail='Session expired or invalid')
    return AuthContext(user=user, csrf_token=csrf)


def require_csrf(
    auth: AuthContext = Depends(get_auth),
    x_csrf_token: str | None = Header(default=None),
) -> AuthContext:
    if not x_csrf_token or not secrets.compare_digest(x_csrf_token, auth.csrf_token):
        raise HTTPException(status_code=403, detail='Invalid CSRF token')
    return auth


def client_ip(request: Request) -> str:
    """Trust X-Real-IP only behind an isolated, overwriting reverse proxy."""
    source = request.client.host if request.client else 'unknown'
    if get_settings().trust_proxy_headers:
        candidate = request.headers.get('x-real-ip', '')
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            pass
    return source
