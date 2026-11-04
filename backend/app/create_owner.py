"""One-time interactive owner creation: python -m app.create_owner"""
import getpass

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def main():
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)) is not None:
            raise SystemExit('An owner already exists. Registration is disabled.')
        try:
            email = validate_email(input('Owner email: ').strip(), check_deliverability=False).normalized.lower()
        except EmailNotValidError as exc:
            raise SystemExit(f'Invalid email address: {exc}') from None
        password = getpass.getpass('Password (12-128 characters): ')
        confirm = getpass.getpass('Confirm password: ')
        if password != confirm:
            raise SystemExit('Passwords do not match.')
        try:
            encoded = hash_password(password)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
        db.add(User(email=email, password_hash=encoded))
        db.commit()
        print('Owner created. You can now sign in.')


if __name__ == '__main__':
    main()
