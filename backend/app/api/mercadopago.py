from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_home_member
from app.config import get_settings
from app.database import get_db
from app.models import Membership, MercadoPagoIntegration, User
from app.schemas import MercadoPagoIntegrationRead, MercadoPagoSyncRead, MercadoPagoTokenUpdate
from app.services.audit import log_action
from app.services.mercadopago import MercadoPagoClient, MercadoPagoError, MercadoPagoTemporaryError, sync_integration

router = APIRouter(prefix="/households/{home_group_id}/mercadopago", tags=["mercadopago"])


@router.get("/integrations", response_model=list[MercadoPagoIntegrationRead])
def list_integrations(
    home_group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MercadoPagoIntegrationRead]:
    require_home_member(home_group_id, user, db)
    members = list(db.scalars(select(Membership).where(Membership.home_group_id == home_group_id)))
    integrations = {
        integration.user_id: integration
        for integration in db.scalars(select(MercadoPagoIntegration).where(MercadoPagoIntegration.home_group_id == home_group_id))
    }
    return [_integration_read(member.user_id, integrations.get(member.user_id)) for member in members]


@router.put("/integrations/{member_user_id}", response_model=MercadoPagoIntegrationRead)
async def upsert_integration(
    home_group_id: int,
    member_user_id: int,
    payload: MercadoPagoTokenUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MercadoPagoIntegrationRead:
    require_home_member(home_group_id, user, db)
    _require_member_user(home_group_id, member_user_id, db)
    token = payload.access_token.strip()
    settings = get_settings()
    client = MercadoPagoClient(
        token,
        api_base_url=settings.mercadopago_api_base_url,
        identity_base_url=settings.mercadopago_identity_base_url,
    )
    try:
        account = await client.validate_token()
    except MercadoPagoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    integration = db.scalar(
        select(MercadoPagoIntegration).where(
            MercadoPagoIntegration.home_group_id == home_group_id,
            MercadoPagoIntegration.user_id == member_user_id,
        )
    )
    if integration is None:
        integration = MercadoPagoIntegration(home_group_id=home_group_id, user_id=member_user_id, access_token=token)
        db.add(integration)
    integration.access_token = token
    integration.enabled = payload.enabled
    integration.mp_user_id = account.mp_user_id
    integration.mp_nickname = account.nickname
    integration.mp_site_id = account.site_id
    integration.last_sync_status = "connected"
    integration.last_sync_error = None
    integration.updated_at = datetime.utcnow()
    db.flush()
    log_action(db, home_group_id, user.id, "mercadopago_connect", "mercadopago_integration", f"Mercado Pago conectado para usuario #{member_user_id}", integration.id)
    db.commit()
    db.refresh(integration)
    return _integration_read(member_user_id, integration)


@router.post("/integrations/{member_user_id}/sync", response_model=MercadoPagoSyncRead)
async def sync_now(
    home_group_id: int,
    member_user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MercadoPagoSyncRead:
    require_home_member(home_group_id, user, db)
    integration = db.scalar(
        select(MercadoPagoIntegration).where(
            MercadoPagoIntegration.home_group_id == home_group_id,
            MercadoPagoIntegration.user_id == member_user_id,
        )
    )
    if integration is None or not integration.enabled:
        raise HTTPException(status_code=404, detail="Integracion Mercado Pago no conectada")
    settings = get_settings()
    client = MercadoPagoClient(
        integration.access_token,
        api_base_url=settings.mercadopago_api_base_url,
        identity_base_url=settings.mercadopago_identity_base_url,
    )
    try:
        result = await sync_integration(
            db,
            integration,
            client=client,
            overlap_days=settings.mercadopago_sync_overlap_days,
            poll_interval_seconds=settings.mercadopago_report_poll_interval_seconds,
            poll_timeout_seconds=settings.mercadopago_report_poll_timeout_seconds,
        )
    except MercadoPagoTemporaryError as exc:
        db.rollback()
        integration.last_sync_status = "error"
        integration.last_sync_error = str(exc)
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MercadoPagoError as exc:
        db.rollback()
        integration.last_sync_status = "error"
        integration.last_sync_error = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        integration.last_sync_status = "error"
        integration.last_sync_error = str(exc)[:1000]
        db.commit()
        raise HTTPException(status_code=500, detail="No se pudo sincronizar Mercado Pago") from exc
    return MercadoPagoSyncRead(**result.__dict__)


@router.delete("/integrations/{member_user_id}")
def delete_integration(
    home_group_id: int,
    member_user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    integration = db.scalar(
        select(MercadoPagoIntegration).where(
            MercadoPagoIntegration.home_group_id == home_group_id,
            MercadoPagoIntegration.user_id == member_user_id,
        )
    )
    if integration is not None:
        log_action(db, home_group_id, user.id, "mercadopago_disconnect", "mercadopago_integration", f"Mercado Pago desconectado para usuario #{member_user_id}", integration.id)
        db.delete(integration)
        db.commit()
    return {"ok": True}


def _require_member_user(home_group_id: int, member_user_id: int, db: Session) -> None:
    membership = db.scalar(
        select(Membership).where(
            Membership.home_group_id == home_group_id,
            Membership.user_id == member_user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")


def _integration_read(user_id: int, integration: MercadoPagoIntegration | None) -> MercadoPagoIntegrationRead:
    if integration is None:
        return MercadoPagoIntegrationRead(user_id=user_id, connected=False)
    return MercadoPagoIntegrationRead(
        user_id=user_id,
        connected=True,
        enabled=integration.enabled,
        mp_user_id=integration.mp_user_id,
        mp_nickname=integration.mp_nickname,
        mp_site_id=integration.mp_site_id,
        last_sync_at=integration.last_sync_at.isoformat() if integration.last_sync_at else None,
        last_sync_status=integration.last_sync_status,
        last_sync_error=integration.last_sync_error,
        last_report_file_name=integration.last_report_file_name,
        updated_at=integration.updated_at.isoformat() if integration.updated_at else None,
    )
