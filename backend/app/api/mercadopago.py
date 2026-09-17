import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_home_member
from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models import MercadoPagoIntegration, User
from app.schemas import MercadoPagoIntegrationRead, MercadoPagoSyncAccepted, MercadoPagoSyncRequest, MercadoPagoTokenUpdate
from app.services.audit import log_action
from app.services.mercadopago import MercadoPagoClient, MercadoPagoError, claim_mercadopago_sync, execute_mercadopago_sync_job

router = APIRouter(prefix="/households/{home_group_id}/mercadopago", tags=["mercadopago"])
_sync_tasks: set[asyncio.Task[None]] = set()


async def cancel_running_sync_tasks() -> None:
    tasks = list(_sync_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _sync_tasks.clear()


@router.get("/integrations", response_model=list[MercadoPagoIntegrationRead])
def list_integrations(
    home_group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MercadoPagoIntegrationRead]:
    require_home_member(home_group_id, user, db)
    integration = db.scalar(
        select(MercadoPagoIntegration).where(
            MercadoPagoIntegration.home_group_id == home_group_id,
            MercadoPagoIntegration.user_id == user.id,
        )
    )
    return [_integration_read(user.id, integration)]


@router.put("/integrations/{member_user_id}", response_model=MercadoPagoIntegrationRead)
async def upsert_integration(
    home_group_id: int,
    member_user_id: int,
    payload: MercadoPagoTokenUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MercadoPagoIntegrationRead:
    require_home_member(home_group_id, user, db)
    _require_own_integration(member_user_id, user)
    existing = db.scalar(
        select(MercadoPagoIntegration).where(
            MercadoPagoIntegration.home_group_id == home_group_id,
            MercadoPagoIntegration.user_id == member_user_id,
        )
    )
    if existing is not None and existing.last_sync_status == "running":
        raise HTTPException(status_code=409, detail="Hay una sincronizacion de Mercado Pago en curso")
    token = payload.access_token.strip()
    settings = get_settings()
    client = MercadoPagoClient(
        token,
        api_base_url=settings.mercadopago_api_base_url,
        identity_base_url=settings.mercadopago_identity_base_url,
        debug_http=settings.mercadopago_debug_http_enabled,
        debug_http_max_chars=settings.mercadopago_debug_http_max_chars,
    )
    try:
        account = await client.validate_token()
    except MercadoPagoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    integration = existing
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


@router.post("/integrations/{member_user_id}/sync", response_model=MercadoPagoSyncAccepted, status_code=202)
async def sync_now(
    home_group_id: int,
    member_user_id: int,
    payload: MercadoPagoSyncRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MercadoPagoSyncAccepted:
    require_home_member(home_group_id, user, db)
    _require_own_integration(member_user_id, user)
    integration = db.scalar(
        select(MercadoPagoIntegration).where(
            MercadoPagoIntegration.home_group_id == home_group_id,
            MercadoPagoIntegration.user_id == member_user_id,
        )
    )
    if integration is None or not integration.enabled:
        raise HTTPException(status_code=404, detail="Integracion Mercado Pago no conectada")
    if payload and bool(payload.start_date) != bool(payload.end_date):
        raise HTTPException(status_code=400, detail="Para sincronizar un rango, completa las fechas Desde y Hasta")
    settings = get_settings()
    if not claim_mercadopago_sync(db, integration.id):
        raise HTTPException(status_code=409, detail="Hay una sincronizacion de Mercado Pago en curso")
    custom_range = bool(payload and payload.start_date and payload.end_date)
    task = asyncio.create_task(
        execute_mercadopago_sync_job(
            SessionLocal,
            integration.id,
            api_base_url=settings.mercadopago_api_base_url,
            identity_base_url=settings.mercadopago_identity_base_url,
            overlap_days=settings.mercadopago_sync_overlap_days,
            poll_interval_seconds=settings.mercadopago_report_poll_interval_seconds,
            poll_timeout_seconds=settings.mercadopago_report_poll_timeout_seconds,
            start_date=payload.start_date if payload else None,
            end_date=payload.end_date if payload else None,
            advance_cursor=not custom_range,
            debug_http=settings.mercadopago_debug_http_enabled,
            debug_http_max_chars=settings.mercadopago_debug_http_max_chars,
        )
    )
    _sync_tasks.add(task)
    task.add_done_callback(_sync_tasks.discard)
    return MercadoPagoSyncAccepted()


@router.delete("/integrations/{member_user_id}")
def delete_integration(
    home_group_id: int,
    member_user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    _require_own_integration(member_user_id, user)
    integration = db.scalar(
        select(MercadoPagoIntegration).where(
            MercadoPagoIntegration.home_group_id == home_group_id,
            MercadoPagoIntegration.user_id == member_user_id,
        )
    )
    if integration is not None:
        if integration.last_sync_status == "running":
            raise HTTPException(status_code=409, detail="Hay una sincronizacion de Mercado Pago en curso")
        log_action(db, home_group_id, user.id, "mercadopago_disconnect", "mercadopago_integration", f"Mercado Pago desconectado para usuario #{member_user_id}", integration.id)
        db.delete(integration)
        db.commit()
    return {"ok": True}


def _require_own_integration(member_user_id: int, user: User) -> None:
    if member_user_id != user.id:
        raise HTTPException(status_code=403, detail="Solo puedes administrar tu propia integracion de Mercado Pago")


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
        last_sync_started_at=integration.last_sync_started_at.isoformat() if integration.last_sync_started_at else None,
        last_sync_completed_at=integration.last_sync_completed_at.isoformat() if integration.last_sync_completed_at else None,
        last_sync_begin_date=integration.last_sync_begin_date.isoformat() if integration.last_sync_begin_date else None,
        last_sync_end_date=integration.last_sync_end_date.isoformat() if integration.last_sync_end_date else None,
        last_sync_imported=integration.last_sync_imported,
        last_sync_ignored=integration.last_sync_ignored,
        last_sync_duplicates=integration.last_sync_duplicates,
        updated_at=integration.updated_at.isoformat() if integration.updated_at else None,
    )
