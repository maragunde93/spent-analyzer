from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Membership, User


def _display_name_from_email(email: str) -> str:
    return email.split("@")[0].replace(".", " ").replace("_", " ").title()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    x_test_user_email: str | None = Header(default=None),
) -> User:
    settings = get_settings()
    session_user_id = request.session.get("user_id")
    if session_user_id:
        user = db.get(User, int(session_user_id))
        if user:
            return user
        request.session.clear()

    if settings.test_auth_enabled and x_test_user_email:
        user = db.scalar(select(User).where(User.email == x_test_user_email))
        if user:
            return user
        user = User(email=x_test_user_email, display_name=_display_name_from_email(x_test_user_email))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def require_home_member(home_group_id: int, user: User, db: Session) -> None:
    exists = db.scalar(
        select(Membership.id).where(
            Membership.home_group_id == home_group_id,
            Membership.user_id == user.id,
        )
    )
    if not exists:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a household member")
