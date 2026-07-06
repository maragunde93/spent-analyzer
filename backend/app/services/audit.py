from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain import Currency
from app.models import AuditLog


def log_action(
    db: Session,
    home_group_id: int,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    description: str,
    entity_id: int | None = None,
    amount: Decimal | None = None,
    currency: Currency | None = None,
) -> None:
    db.add(
        AuditLog(
            home_group_id=home_group_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description[:240],
            amount=amount,
            currency=currency,
        )
    )
