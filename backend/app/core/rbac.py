"""
RBAC + object-level authorization — the "gateway" access layer.

This module is the single place that turns a verified JWT identity
(``CurrentUser``, produced by ``app.api.auth.get_current_user``) into an
authorization decision. Every protected router depends on functions from
this module instead of re-implementing role checks, so the request flow
is always:

    Client -> FastAPI app -> get_current_user (JWT, 401) -> require_roles (RBAC, 403) -> endpoint

Nothing here talks to the database except the small ownership helper,
and nothing here duplicates JWT verification — it is layered strictly on
top of the existing ``app.api.auth`` dependency.
"""
import enum

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.models.student import Student
from app.schemas.auth import CurrentUser


class Role(str, enum.Enum):
    """Project roles. Values match the lowercase strings already stored
    on ``User.role`` and issued inside the JWT ``role`` claim."""

    STUDENT = "student"
    FACULTY = "faculty"
    ADMIN = "admin"
    ACCOUNTS = "accounts"
    WARDEN = "warden"
    EXAM_OFFICER = "exam_officer"


def require_roles(*allowed_roles: Role):
    """FastAPI dependency factory: 403s unless the authenticated user's
    role is one of ``allowed_roles``. Use as:

        @router.post("", dependencies=[Depends(require_roles(Role.ADMIN))])
    """
    allowed = {role.value for role in allowed_roles}

    def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return _check


# ------------------------------------------------------- Object-level auth

def get_owned_student(db: Session, current_user: CurrentUser) -> Student | None:
    """Resolves the Student row that belongs to the logged-in account.

    There is no explicit user_id FK on Student (out of scope to add for
    this task), so the link is made the only way the existing schema
    allows: matching the login email to the student's academic email.
    Returns None if this account has no linked student record.
    """
    return db.scalar(select(Student).where(Student.email == current_user.email))


def enforce_own_student_record(
    current_user: CurrentUser,
    db: Session,
    *,
    staff_roles: set[Role],
    target_student_code: str | None = None,
    target_student_pk=None,
) -> None:
    """Object-level authorization for a single student's private record.

    - Any role in ``staff_roles`` is allowed through unconditionally.
    - A STUDENT is allowed through only if the record's student identity
      (matched by human-readable ``student_id`` code or by internal UUID
      — pass whichever the endpoint has) belongs to their own account.
    - Everyone else gets 403.

    This is the check that stops "Student A" from reading "Student B"'s
    record by editing a path parameter.
    """
    if current_user.role in {r.value for r in staff_roles}:
        return

    if current_user.role != Role.STUDENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )

    own = get_owned_student(db, current_user)
    if own is not None:
        if target_student_code is not None and own.student_id == target_student_code:
            return
        if target_student_pk is not None and own.id == target_student_pk:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You may only access your own records",
    )


def enforce_own_student_filter(
    current_user: CurrentUser,
    db: Session,
    *,
    staff_roles: set[Role],
    requested_student_code: str | None,
) -> None:
    """Object-level authorization for list endpoints that accept an
    optional ``student_id`` query filter (attendance, hostel allocations,
    exam registrations).

    Staff roles may list freely (including with no filter, i.e. everyone).
    A STUDENT must supply the filter and it must be their own student_id
    — otherwise they could list every record with no filter at all, or
    someone else's by supplying a different code.
    """
    if current_user.role in {r.value for r in staff_roles}:
        return

    if current_user.role != Role.STUDENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )

    own = get_owned_student(db, current_user)
    if (
        requested_student_code is not None
        and own is not None
        and own.student_id == requested_student_code
    ):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You may only list your own records",
    )
