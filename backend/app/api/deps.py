from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User

bearer = HTTPBearer(auto_error=False)


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak ada.", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_token(cred.credentials)
        user = db.get(User, int(payload["sub"]))
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak valid atau kedaluwarsa.")
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Pengguna tidak aktif.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Hanya admin yang dapat melakukan aksi ini.")
    return user


def request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)
