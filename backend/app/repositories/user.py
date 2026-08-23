import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def create(db: Session, *, email: str, hashed_password: str, role: str = "student",
           full_name: str | None = None) -> User:
    user = User(email=email, hashed_password=hashed_password, role=role, full_name=full_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)
