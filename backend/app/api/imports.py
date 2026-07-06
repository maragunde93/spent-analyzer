from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_home_member
from app.database import get_db
from app.domain import ExpenseSource, ImportLineKind
from app.models import CashWalletEntry, Category, Earning, Expense, ImportBatch, ImportLine, Subcategory, User
from app.schemas import ImportBatchRead, ImportCommitRequest
from app.services.accounting import amount_to_ars
from app.services.audit import log_action
from app.services.bbva_account_parser import parse_bbva_account_xls
from app.services.bbva_parser import parse_bbva_visa_pdf
from app.services.categorizer import suggest_category
from app.services.recurring import should_suggest_recurring, sync_recurring_rule

router = APIRouter(prefix="/households/{home_group_id}/imports", tags=["imports"])


@router.get("", response_model=list[ImportBatchRead])
def list_import_batches(
    home_group_id: int,
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ImportBatchRead]:
    require_home_member(home_group_id, user, db)
    stmt = select(ImportBatch).where(ImportBatch.home_group_id == home_group_id).order_by(ImportBatch.created_at.desc())
    if status:
        stmt = stmt.where(ImportBatch.status == status)
    return [_read_batch(db, batch.id) for batch in db.scalars(stmt)]


@router.post("/bbva-visa", response_model=ImportBatchRead)
async def upload_bbva_visa(
    home_group_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportBatchRead:
    require_home_member(home_group_id, user, db)
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    try:
        parsed = parse_bbva_visa_pdf(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    batch = ImportBatch(
        home_group_id=home_group_id,
        uploaded_by_user_id=user.id,
        filename=file.filename or "statement.pdf",
        statement_account=parsed.account,
        period_label=parsed.period_label,
    )
    db.add(batch)
    db.flush()
    categories = {c.name: c.id for c in db.scalars(select(Category).where(Category.home_group_id == home_group_id))}
    subcategories = _subcategories_by_name(db, home_group_id)
    for line in parsed.lines:
        suggestion = suggest_category(line.description)
        suggested_category_id = categories.get(suggestion.name) if suggestion else None
        suggested_recurring = should_suggest_recurring(db, home_group_id, line.description, suggested_category_id)
        db.add(
            ImportLine(
                import_batch_id=batch.id,
                home_group_id=home_group_id,
                date=line.date,
                description=line.description,
                coupon=line.coupon,
                kind=line.kind,
                currency=line.currency,
                original_amount=line.amount,
                suggested_category_id=suggested_category_id,
                suggested_subcategory_id=_suggest_subcategory_id(line.description, suggested_category_id, subcategories),
                suggested_recurring=suggested_recurring,
                fingerprint=f"{batch.id}:{line.fingerprint}",
                raw_text=line.raw_text,
            )
        )
    db.commit()
    log_action(db, home_group_id, user.id, "import_upload", "import_batch", f"Resumen de tarjeta cargado: {batch.filename}", batch.id)
    db.commit()
    return _read_batch(db, batch.id)


@router.post("/bbva-account", response_model=ImportBatchRead)
async def upload_bbva_account(
    home_group_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportBatchRead:
    require_home_member(home_group_id, user, db)
    with NamedTemporaryFile(delete=False, suffix=".xls") as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    try:
        parsed = parse_bbva_account_xls(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)

    batch = ImportBatch(
        home_group_id=home_group_id,
        uploaded_by_user_id=user.id,
        filename=file.filename or "movimientos-cuenta.xls",
        source_type="bbva_account_xls",
        statement_account=parsed.account,
        period_label=parsed.period_label,
    )
    db.add(batch)
    db.flush()
    categories = {c.name: c.id for c in db.scalars(select(Category).where(Category.home_group_id == home_group_id))}
    subcategories = _subcategories_by_name(db, home_group_id)
    for line in parsed.lines:
        suggestion = suggest_category(line.description)
        suggested_category_id = categories.get(suggestion.name) if suggestion else None
        suggested_recurring = should_suggest_recurring(db, home_group_id, line.description, suggested_category_id)
        db.add(
            ImportLine(
                import_batch_id=batch.id,
                home_group_id=home_group_id,
                date=line.date,
                description=line.description,
                coupon=None,
                kind=line.kind,
                currency=line.currency,
                original_amount=line.amount,
                suggested_category_id=suggested_category_id,
                suggested_subcategory_id=_suggest_subcategory_id(line.description, suggested_category_id, subcategories),
                suggested_recurring=suggested_recurring,
                fingerprint=f"{batch.id}:{line.fingerprint}",
                raw_text=line.raw_text,
            )
        )
    log_action(db, home_group_id, user.id, "import_upload", "import_batch", f"Movimientos de cuenta cargados: {batch.filename}", batch.id)
    db.commit()
    return _read_batch(db, batch.id)


@router.get("/{batch_id}", response_model=ImportBatchRead)
def get_import_batch(
    home_group_id: int,
    batch_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportBatchRead:
    require_home_member(home_group_id, user, db)
    return _read_batch(db, batch_id)


@router.delete("/{batch_id}")
def delete_import_batch(
    home_group_id: int,
    batch_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    batch = db.get(ImportBatch, batch_id)
    if batch is None or batch.home_group_id != home_group_id:
        raise HTTPException(status_code=404, detail="Importacion no encontrada")

    lines = list(db.scalars(select(ImportLine).where(ImportLine.import_batch_id == batch_id)))
    line_ids = [line.id for line in lines]
    converted_line_ids: set[int] = set()
    if line_ids:
        converted_line_ids.update(db.scalars(select(Expense.import_line_id).where(Expense.import_line_id.in_(line_ids))).all())
        converted_line_ids.update(db.scalars(select(Earning.import_line_id).where(Earning.import_line_id.in_(line_ids))).all())
        deletable_line_ids = [line.id for line in lines if line.id not in converted_line_ids]
        if deletable_line_ids:
            db.execute(delete(ImportLine).where(ImportLine.id.in_(deletable_line_ids)))
            db.flush()
    if converted_line_ids:
        batch.status = "committed"
    else:
        log_action(db, home_group_id, user.id, "import_delete", "import_batch", f"Importacion borrada: {batch.filename}", batch.id)
        db.delete(batch)
    db.commit()
    return {"ok": True}


@router.post("/{batch_id}/commit")
def commit_import(
    home_group_id: int,
    batch_id: int,
    payload: ImportCommitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    batch = db.get(ImportBatch, batch_id)
    lines = list(
        db.scalars(
            select(ImportLine).where(
                ImportLine.home_group_id == home_group_id,
                ImportLine.import_batch_id == batch_id,
                ImportLine.id.in_(payload.line_ids),
                ImportLine.status == "pending",
            )
        )
    )
    created = 0
    processed = 0
    for line in lines:
        if _duplicate_status_for_line(db, line) == "already_committed":
            line.status = "duplicate"
            continue
        _fill_missing_suggestion(db, line)
        category_id = payload.category_overrides.get(line.id, line.suggested_category_id)
        subcategory_id = payload.subcategory_overrides.get(line.id, line.suggested_subcategory_id)
        is_recurring = payload.recurring_overrides.get(line.id, line.suggested_recurring)
        conversion_date = batch.created_at.date() if batch else line.date
        amount_ars = amount_to_ars(db, Decimal(line.original_amount), line.currency, conversion_date)
        if line.kind in (ImportLineKind.card_payment, ImportLineKind.previous_payment):
            line.status = "ignored"
            processed += 1
            continue
        if line.kind == ImportLineKind.cash_withdrawal:
            db.add(
                CashWalletEntry(
                    home_group_id=home_group_id,
                    user_id=payload.paid_by_user_id,
                    date=line.date,
                    description=line.description,
                    currency=line.currency,
                    amount=abs(Decimal(line.original_amount)),
                )
            )
            line.status = "committed"
            processed += 1
            continue
        if line.kind == ImportLineKind.income:
            db.add(
                Earning(
                    home_group_id=home_group_id,
                    date=line.date,
                    description=line.description,
                    user_id=payload.paid_by_user_id,
                    uploaded_by_user_id=user.id,
                    currency=line.currency,
                    original_amount=abs(Decimal(line.original_amount)),
                    amount_ars=abs(amount_ars),
                    import_line_id=line.id,
                )
            )
            line.status = "committed"
            processed += 1
            continue

        source = ExpenseSource.bank_import if batch and batch.source_type == "bbva_account_xls" else ExpenseSource.import_pdf
        signed_amount = Decimal(line.original_amount)
        original_amount = signed_amount if signed_amount < 0 or line.kind == ImportLineKind.refund else abs(signed_amount)
        reporting_amount = amount_ars if signed_amount < 0 or line.kind == ImportLineKind.refund else abs(amount_ars)
        expense = Expense(
            home_group_id=home_group_id,
            date=line.date,
            description=line.description,
            category_id=category_id,
            subcategory_id=subcategory_id,
            paid_by_user_id=payload.paid_by_user_id,
            uploaded_by_user_id=user.id,
            source=source,
            currency=line.currency,
            original_amount=original_amount,
            amount_ars=reporting_amount,
            import_line_id=line.id,
            is_recurring=is_recurring,
        )
        db.add(expense)
        db.flush()
        sync_recurring_rule(db, expense)
        line.status = "committed"
        created += 1
        processed += 1
    if batch:
        ignored_kinds = [ImportLineKind.card_payment, ImportLineKind.previous_payment]
        for ignored_line in db.scalars(
            select(ImportLine).where(
                ImportLine.import_batch_id == batch.id,
                ImportLine.status == "pending",
                ImportLine.kind.in_(ignored_kinds),
            )
        ):
            ignored_line.status = "ignored"
        db.flush()
        remaining = db.scalar(
            select(ImportLine.id).where(
                ImportLine.import_batch_id == batch.id,
                ImportLine.status == "pending",
            )
        )
        batch.status = "parsed" if remaining else "committed"
        log_action(
            db,
            home_group_id,
            user.id,
            "import_commit",
            "import_batch",
            f"Importacion procesada: {processed} lineas, {created} gastos creados",
            batch.id,
        )
    db.commit()
    return {"created": created, "processed": processed}


def _read_batch(db: Session, batch_id: int) -> ImportBatchRead:
    batch = db.get(ImportBatch, batch_id)
    lines = list(db.scalars(select(ImportLine).where(ImportLine.import_batch_id == batch_id).order_by(ImportLine.date, ImportLine.id)))
    for line in lines:
        _fill_missing_suggestion(db, line)
        line.duplicate_status = _duplicate_status_for_line(db, line)
    return ImportBatchRead(
        id=batch.id,
        filename=batch.filename,
        source_type=batch.source_type,
        statement_account=batch.statement_account,
        period_label=batch.period_label,
        status=batch.status,
        created_at=batch.created_at.isoformat() if batch.created_at else None,
        lines=lines,
    )


def _fill_missing_suggestion(db: Session, line: ImportLine) -> None:
    if line.suggested_category_id is not None:
        if not line.suggested_recurring:
            line.suggested_recurring = should_suggest_recurring(db, line.home_group_id, line.description, line.suggested_category_id)
        return
    suggestion = suggest_category(line.description)
    if suggestion is None:
        return
    category_id = db.scalar(
        select(Category.id).where(
            Category.home_group_id == line.home_group_id,
            Category.name == suggestion.name,
        )
    )
    if category_id is None:
        return
    line.suggested_category_id = category_id
    line.suggested_subcategory_id = _suggest_subcategory_id(
        line.description,
        category_id,
        _subcategories_by_name(db, line.home_group_id),
    )
    line.suggested_recurring = should_suggest_recurring(db, line.home_group_id, line.description, category_id)
    db.flush()


def _subcategories_by_name(db: Session, home_group_id: int) -> dict[tuple[int, str], int]:
    return {
        (subcategory.category_id, subcategory.name.upper()): subcategory.id
        for subcategory in db.scalars(select(Subcategory).where(Subcategory.home_group_id == home_group_id))
    }


def _suggest_subcategory_id(description: str, category_id: int | None, subcategories: dict[tuple[int, str], int]) -> int | None:
    if category_id is None:
        return None
    normalized = description.upper()
    service_rules = {
        "CAJA SEG": "Seguro",
        "EDESUR": "Electricidad",
        "EDENOR": "Electricidad",
        "AYSA": "Agua",
        "METROGAS": "Gas",
        "MOVISTAR": "Internet",
        "CLARO": "Internet",
        "SEGURO": "Seguro",
        "PATENTE": "Auto",
    }
    for token, subcategory_name in service_rules.items():
        if token in normalized:
            return subcategories.get((category_id, subcategory_name.upper()))
    return None


def _raw_fingerprint(fingerprint: str) -> str:
    return fingerprint.split(":", 1)[1] if ":" in fingerprint else fingerprint


def _duplicate_status_for_line(db: Session, line: ImportLine) -> str:
    raw = _raw_fingerprint(line.fingerprint)
    prior_lines = list(
        db.scalars(
            select(ImportLine).where(
                ImportLine.home_group_id == line.home_group_id,
                ImportLine.import_batch_id != line.import_batch_id,
            )
        )
    )
    matching_prior = [prior for prior in prior_lines if _raw_fingerprint(prior.fingerprint) == raw]
    if not matching_prior:
        return "new"
    prior_ids = [prior.id for prior in matching_prior]
    committed_expense = db.scalar(select(Expense.id).where(Expense.import_line_id.in_(prior_ids)))
    committed_earning = db.scalar(select(Earning.id).where(Earning.import_line_id.in_(prior_ids)))
    if committed_expense or committed_earning or any(prior.status in ("committed", "ignored") for prior in matching_prior):
        return "already_committed"
    return "previously_parsed"
