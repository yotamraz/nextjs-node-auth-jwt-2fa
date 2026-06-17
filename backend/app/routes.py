import base64
import io
from datetime import datetime, timedelta, timezone

import jwt
import pyotp
import qrcode
import qrcode.constants
from fastapi import APIRouter, Cookie, Depends, Header, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    create_temp_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    TwoFactorTokenRequest,
)

router = APIRouter(prefix="/api/auth")


def _error(msg: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status)


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refreshToken",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key="refreshToken", path="/")


# ──────────────────────────── Signup ────────────────────────────


@router.post("/signup")
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        return _error("Email already in use", 409)

    user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.flush()

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    user.refresh_token = refresh_token

    db.commit()

    resp = JSONResponse({"accessToken": access_token})
    _set_refresh_cookie(resp, refresh_token)
    return resp


# ──────────────────────────── Login ─────────────────────────────


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        return _error("Invalid email or password", 401)

    if user.two_factor_enabled:
        temp_token = create_temp_token(user.id)
        return JSONResponse({"requires2FA": True, "tempToken": temp_token})

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    user.refresh_token = refresh_token
    db.commit()

    resp = JSONResponse({"accessToken": access_token})
    _set_refresh_cookie(resp, refresh_token)
    return resp


# ──────────────────────────── Logout ────────────────────────────


@router.post("/logout")
def logout(
    db: Session = Depends(get_db),
    refreshToken: str | None = Cookie(default=None),
):
    if refreshToken:
        try:
            payload = decode_token(refreshToken, "refresh")
            user = db.query(User).filter(User.id == payload["sub"]).first()
            if user:
                user.refresh_token = None
                db.commit()
        except jwt.PyJWTError:
            pass

    resp = JSONResponse({"message": "Logged out"})
    _clear_refresh_cookie(resp)
    return resp


# ──────────────────────────── Me ────────────────────────────────


@router.get("/me")
def me(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        return _error("Unauthorized", 401)

    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token, "access")
    except jwt.PyJWTError:
        return _error("Invalid or expired token", 401)

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        return _error("User not found", 404)

    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "twoFactorEnabled": user.two_factor_enabled,
        }
    }


# ──────────────────────── Refresh Token ─────────────────────────


@router.post("/refresh-token")
def refresh_token_route(
    db: Session = Depends(get_db),
    refreshToken: str | None = Cookie(default=None),
):
    if not refreshToken:
        return _error("No refresh token", 401)

    try:
        payload = decode_token(refreshToken, "refresh")
    except jwt.PyJWTError:
        return _error("Invalid or expired refresh token", 401)

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or user.refresh_token != refreshToken:
        return _error("Invalid refresh token", 401)

    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)
    user.refresh_token = new_refresh
    db.commit()

    resp = JSONResponse({"accessToken": new_access})
    _set_refresh_cookie(resp, new_refresh)
    return resp


# ──────────────────── Forgot Password ───────────────────────────


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        return {"message": "If that email exists, a reset link has been sent."}

    reset_tok = create_reset_token(user.id)
    user.reset_token = reset_tok
    user.reset_token_expiry = datetime.now(timezone.utc) + timedelta(
        minutes=settings.RESET_TOKEN_EXPIRE_MINUTES
    )
    db.commit()

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_tok}"
    print(f"[DEV] Password reset link: {reset_link}")

    return {"message": "If that email exists, a reset link has been sent."}


# ──────────────────── Reset Password ────────────────────────────


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.token, "reset")
    except jwt.PyJWTError:
        return _error("Invalid or expired reset token", 400)

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or user.reset_token != body.token:
        return _error("Invalid reset token", 400)

    if user.reset_token_expiry and user.reset_token_expiry.replace(
        tzinfo=timezone.utc
    ) < datetime.now(timezone.utc):
        return _error("Reset token expired", 400)

    user.password_hash = hash_password(body.newPassword)
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()

    return {"message": "Password updated successfully"}


# ──────────────────── 2FA Setup ─────────────────────────────────


@router.post("/2fa/setup")
def setup_2fa(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        return _error("Unauthorized", 401)

    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token, "access")
    except jwt.PyJWTError:
        return _error("Invalid token", 401)

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        return _error("User not found", 404)

    secret = pyotp.random_base32()
    user.two_factor_secret = secret
    db.commit()

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.email, issuer_name="AuthApp")

    img = qrcode.make(uri, error_correction=qrcode.constants.ERROR_CORRECT_L)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    qr_data_uri = f"data:image/png;base64,{qr_b64}"

    return {"qrCode": qr_data_uri, "secret": secret}


# ──────────────────── 2FA Verify Setup ──────────────────────────


@router.post("/2fa/verify-setup")
def verify_2fa_setup(
    body: TwoFactorTokenRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        return _error("Unauthorized", 401)

    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token, "access")
    except jwt.PyJWTError:
        return _error("Invalid token", 401)

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.two_factor_secret:
        return _error("2FA not initialized", 400)

    totp = pyotp.TOTP(user.two_factor_secret)
    if not totp.verify(body.token):
        return _error("Invalid 2FA token", 400)

    user.two_factor_enabled = True
    db.commit()

    return {"message": "2FA enabled successfully"}


# ──────────────────── 2FA Login ─────────────────────────────────


@router.post("/2fa/login")
def login_2fa(
    body: TwoFactorTokenRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        return _error("Unauthorized", 401)

    temp_token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(temp_token, "temp_2fa")
    except jwt.PyJWTError:
        return _error("Invalid or expired temp token", 401)

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.two_factor_secret:
        return _error("User not found", 404)

    totp = pyotp.TOTP(user.two_factor_secret)
    if not totp.verify(body.token):
        return _error("Invalid 2FA code", 401)

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    user.refresh_token = refresh_token
    db.commit()

    resp = JSONResponse({"accessToken": access_token})
    _set_refresh_cookie(resp, refresh_token)
    return resp


# ──────────────────── 2FA Disable ───────────────────────────────


@router.post("/2fa/disable")
def disable_2fa(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        return _error("Unauthorized", 401)

    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token, "access")
    except jwt.PyJWTError:
        return _error("Invalid token", 401)

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        return _error("User not found", 404)

    user.two_factor_enabled = False
    user.two_factor_secret = None
    db.commit()

    return {"message": "2FA disabled"}
