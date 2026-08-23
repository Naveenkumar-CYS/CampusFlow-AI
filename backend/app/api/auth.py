from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.rate_limit import enforce_login_rate_limit
from app.core.security import TokenError, decode_access_token
from app.db.session import get_db
from app.schemas.auth import CurrentUser, LoginRequest, TokenResponse
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    """Reusable FastAPI dependency: verifies the Bearer token and returns the
    authenticated identity. Import this into other routers to protect them.

    401 on: missing token, malformed token, invalid signature, expired token.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        return CurrentUser(user_id=payload["sub"], email=payload["email"], role=payload["role"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(enforce_login_rate_limit)])
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        token = auth_service.login(db, payload.email, payload.password)
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    return TokenResponse(access_token=token)


@router.get("/me", response_model=CurrentUser)
def read_current_user(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current_user
