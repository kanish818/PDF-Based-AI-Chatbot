"""
Auth Router
Handles user registration, login, Google OAuth 2.0, and /me endpoint.
"""

import logging
import os
from datetime import timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Pydantic schemas ───────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    created_at: str

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_token(user: User) -> str:
    return create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    )


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


def _google_redirect_uri() -> str:
    if settings.GOOGLE_REDIRECT_URI:
        return settings.GOOGLE_REDIRECT_URI

    render_external_url = os.getenv("RENDER_EXTERNAL_URL", "").strip()
    if render_external_url:
        return f"{render_external_url.rstrip('/')}/api/auth/google/callback"

    return "http://localhost:8000/api/auth/google/callback"


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user with email + password."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered.",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        name=payload.name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Registered new user id=%d email=%s", user.id, user.email)

    return AuthResponse(access_token=_make_token(user), user=_user_out(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email + password, return JWT."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    logger.info("User id=%d logged in.", user.id)
    return AuthResponse(access_token=_make_token(user), user=_user_out(user))


@router.get("/google")
def google_login():
    """Redirect the browser to Google's OAuth2 consent page."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": _google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{query_string}"
    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback")
def google_callback(code: str, db: Session = Depends(get_db)):
    """
    Exchange the authorization code for tokens, fetch user info,
    create or retrieve the local user, and redirect to the frontend with a JWT.
    """
    # Exchange code → tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": _google_redirect_uri(),
        "grant_type": "authorization_code",
    }

    try:
        with httpx.Client() as client:
            token_response = client.post(token_url, data=token_data, timeout=15)
            token_response.raise_for_status()
            token_json = token_response.json()
            access_token_google = token_json.get("access_token")

            # Fetch user info
            userinfo_response = client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token_google}"},
                timeout=15,
            )
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()
    except httpx.HTTPError as exc:
        logger.error("Google OAuth HTTP error: %s", exc)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error=oauth_failed"
        )

    google_id = userinfo.get("id")
    email = userinfo.get("email")
    name = userinfo.get("name") or email

    if not google_id or not email:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error=missing_user_info"
        )

    # Find or create the local user
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_id = google_id  # link existing account
        else:
            user = User(email=email, name=name, google_id=google_id)
            db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Google OAuth: user id=%d email=%s", user.id, user.email)

    jwt_token = _make_token(user)
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/callback?token={jwt_token}"
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return _user_out(current_user)
