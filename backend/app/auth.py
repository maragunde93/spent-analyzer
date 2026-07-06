from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Membership, User


def get_current_user(
    db: Session = Depends(get_db),
    x_test_user_email: str | None = Header(default=None),
) -> User:
    settings = get_settings()
    if settings.test_auth_enabled and x_test_user_email:
        user = db.scalar(select(User).where(User.email == x_test_user_email))
        if user:
            return user
        user = User(email=x_test_user_email, display_name=x_test_user_email.split("@")[0].title())
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

