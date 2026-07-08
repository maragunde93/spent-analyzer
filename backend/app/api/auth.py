import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.local_auth import verify_password
from app.models import User
from app.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_SCOPES = "openid email profile"


class LoginRequest(BaseModel):
    username: str
    password: str


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/login", response_model=UserRead)
def login_local(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> User:
    username = payload.username.strip().lower()
    configured_user = next((item for item in get_settings().local_users if item.username.lower() == username), None)
    if configured_user is None or not verify_password(payload.password, configured_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    email = configured_user.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, display_name=configured_user.display_name.strip()[:120])
        db.add(user)
    else:
        user.display_name = configured_user.display_name.strip()[:120] or user.display_name
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return user


@router.get("/login/google")
def login_google(request: Request) -> RedirectResponse:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google OAuth is not configured")
    state = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": google_callback_url(),
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "state": state,
        "prompt": "select_account",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    expected_state = request.session.pop("google_oauth_state", None)
    if not code or not state or not expected_state or state != expected_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")
    token_payload = await exchange_google_code(code)
    id_token = token_payload.get("id_token")
    if not isinstance(id_token, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google did not return an ID token")
    claims = await fetch_google_claims(id_token)
    user = authenticate_google_user(db, claims)
    request.session["user_id"] = user.id
    return RedirectResponse(f"{get_settings().public_base_url.rstrip('/')}/")


@router.post("/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


def google_callback_url() -> str:
    settings = get_settings()
    api_base = settings.public_api_base_url or f"{settings.public_base_url.rstrip('/')}/api"
    return f"{api_base.rstrip('/')}/auth/google/callback"


async def exchange_google_code(code: str) -> dict:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": google_callback_url(),
                "grant_type": "authorization_code",
            },
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google OAuth token exchange failed")
    return response.json()


async def fetch_google_claims(id_token: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(GOOGLE_TOKENINFO_URL, params={"id_token": id_token})
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google ID token validation failed")
    claims = response.json()
    audience = claims.get("aud")
    if audience != get_settings().google_client_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google ID token audience mismatch")
    return claims


def authenticate_google_user(db: Session, claims: dict) -> User:
    sub = str(claims.get("sub") or "")
    email = str(claims.get("email") or "").strip().lower()
    email_verified = claims.get("email_verified")
    verified = email_verified is True or str(email_verified).lower() == "true"
    if not sub or not email or not verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google account email is not verified")

    allowed = {item.lower() for item in get_settings().allowed_google_emails}
    if email not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Google account is not allowed")

    display_name = str(claims.get("name") or email.split("@")[0]).strip()[:120]
    user = db.scalar(select(User).where(User.google_sub == sub))
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, display_name=display_name, google_sub=sub)
        db.add(user)
    else:
        user.email = email
        user.display_name = display_name or user.display_name
        user.google_sub = sub
    db.commit()
    db.refresh(user)
    return user
