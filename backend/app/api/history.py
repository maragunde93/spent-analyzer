from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_home_member
from app.database import get_db
from app.models import AuditLog, User
from app.schemas import AuditLogRead

router = APIRouter(prefix="/households/{home_group_id}/history", tags=["history"])


@router.get("", response_model=list[AuditLogRead])
def list_history(
    home_group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AuditLogRead]:
    require_home_member(home_group_id, user, db)
    rows = list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.home_group_id == home_group_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(200)
        )
    )
    return [
        AuditLogRead(
            id=row.id,
            actor_user_id=row.actor_user_id,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            description=row.description,
            currency=row.currency,
            amount=row.amount,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]
