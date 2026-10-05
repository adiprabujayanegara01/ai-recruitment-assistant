from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import current_user, request_id, require_admin
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas import LoginIn, UserCreate
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _u(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role}


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    ok = bool(user and user.is_active and verify_password(body.password, user.password_hash))
    audit(db, user.id if user else None, "login_success" if ok else "login_failed", "user", user.id if user else None,
          {"email": body.email.lower()}, request_id(request))
    if not ok:
        raise HTTPException(401, "Email atau password salah.")
    return {"access_token": create_access_token(user.id, user.role), "token_type": "bearer", "user": _u(user)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return _u(user)


@router.post("/users", status_code=201)
def create_user(body: UserCreate, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(409, "Email sudah terdaftar.")
    u = User(name=body.name, email=body.email.lower(), password_hash=hash_password(body.password), role=body.role)
    db.add(u)
    db.commit()
    audit(db, admin.id, "user_created", "user", u.id, {"role": u.role}, request_id(request))
    return _u(u)


@router.get("/users")
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [_u(u) for u in db.query(User).order_by(User.id).all()]
