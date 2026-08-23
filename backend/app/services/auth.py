from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories import user as user_repo


class InvalidCredentialsError(Exception):
    pass


class DuplicateUserError(Exception):
    pass


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = user_repo.get_by_email(db, email)
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("invalid email or password")
    return user


def login(db: Session, email: str, password: str) -> str:
    """Verifies credentials and returns a signed JWT access token."""
    user = authenticate_user(db, email, password)
    return create_access_token(user_id=user.id, email=user.email, role=user.role)


def register_user(db: Session, *, email: str, password: str, role: str = "student",
                   full_name: str | None = None) -> User:
    """Creates a user with a hashed password.

    Not exposed via an API endpoint in this task (no signup flow was
    requested) — this exists so tests (and any future signup endpoint)
    have a single place that creates users correctly.
    """
    if user_repo.get_by_email(db, email) is not None:
        raise DuplicateUserError(f"user with email '{email}' already exists")
    return user_repo.create(
        db, email=email, hashed_password=hash_password(password), role=role, full_name=full_name
    )
