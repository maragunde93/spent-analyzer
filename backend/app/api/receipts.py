from pathlib import Path
from tempfile import NamedTemporaryFile

from decimal import Decimal
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_home_member
from app.database import get_db
from app.models import Category, Expense, ReceiptImport, ReceiptItem, Subcategory, User
from app.schemas import ReceiptAssociationRequest, ReceiptImportRead, ReceiptItemRead, ReceiptReviewRequest
from app.services.audit import log_action
from app.services.receipt_ai_parser import parse_receipt_files

router = APIRouter(prefix="/households/{home_group_id}/receipts", tags=["receipts"])
logger = logging.getLogger("spent.receipts")


@router.get("", response_model=list[ReceiptImportRead])
def list_receipts(
    home_group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReceiptImportRead]:
    require_home_member(home_group_id, user, db)
    receipts = list(
        db.scalars(
            select(ReceiptImport)
            .where(ReceiptImport.home_group_id == home_group_id)
            .order_by(ReceiptImport.created_at.desc(), ReceiptImport.id.desc())
        )
    )
    return [
        _receipt_read(receipt, db)
        for receipt in receipts
    ]


@router.post("", response_model=ReceiptImportRead)
async def upload_receipt(
    home_group_id: int,
    expense_id: int | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReceiptImportRead:
    require_home_member(home_group_id, user, db)
    if not files:
        raise HTTPException(status_code=400, detail="No se recibieron archivos")
    logger.info("receipt_upload_start home_group_id=%s user_id=%s files=%s expense_id=%s", home_group_id, user.id, len(files), expense_id)
    if expense_id is not None:
        expense = db.get(Expense, expense_id)
        if expense is None or expense.home_group_id != home_group_id:
            logger.warning("receipt_upload_expense_ignored home_group_id=%s user_id=%s expense_id=%s", home_group_id, user.id, expense_id)
            expense_id = None
    upload_paths: list[tuple[Path, str | None]] = []
    filenames: list[str] = []
    try:
        for upload in files:
            filenames.append(upload.filename or "ticket.jpg")
            suffix = Path(upload.filename or "ticket.jpg").suffix
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await upload.read())
                tmp_path = Path(tmp.name)
            upload_paths.append((tmp_path, upload.content_type))
        parsed, raw_text, parser_source = parse_receipt_files(upload_paths)
    finally:
        for tmp_path, _content_type in upload_paths:
            tmp_path.unlink(missing_ok=True)
    display_filename = filenames[0] if len(filenames) == 1 else f"{len(filenames)} archivos: {', '.join(filenames[:3])}{'...' if len(filenames) > 3 else ''}"
    has_raw_text = bool(raw_text.strip())
    default_category = _find_category_by_name(home_group_id, "Compras del hogar", db)
    receipt_status = "parsed_llm" if parser_source == "llm" and parsed and parsed.items else "parsed" if parsed and parsed.items else "ocr_no_items" if has_raw_text else "uploaded_pending_ocr"

    receipt = ReceiptImport(
        home_group_id=home_group_id,
        uploaded_by_user_id=user.id,
        expense_id=expense_id,
        category_id=default_category.id if default_category else None,
        filename=display_filename,
        status=receipt_status,
        raw_text=raw_text or None,
    )
    db.add(receipt)
    db.flush()
    if parsed is not None:
        for item in parsed.items:
            db.add(
                ReceiptItem(
                    receipt_import_id=receipt.id,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_amount=item.total_amount,
                    suggested_subcategory_name=item.suggested_subcategory,
                )
            )
    log_action(
        db,
        home_group_id,
        user.id,
        "receipt_upload",
        "receipt",
        f"Ticket cargado: {receipt.filename}",
        receipt.id,
    )
    db.commit()
    db.refresh(receipt)
    logger.info(
        "receipt_upload_done home_group_id=%s receipt_id=%s source=%s status=%s items=%s",
        home_group_id,
        receipt.id,
        parser_source,
        receipt.status,
        len(parsed.items) if parsed else 0,
    )
    return _receipt_read(receipt, db)


@router.put("/{receipt_id}/items", response_model=ReceiptImportRead)
def update_receipt_items(
    home_group_id: int,
    receipt_id: int,
    payload: ReceiptReviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReceiptImportRead:
    require_home_member(home_group_id, user, db)
    receipt = db.get(ReceiptImport, receipt_id)
    if receipt is None or receipt.home_group_id != home_group_id:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    category_id = _valid_category_id(home_group_id, payload.category_id, db) if payload.category_id else receipt.category_id
    items = {
        item.id: item
        for item in db.scalars(select(ReceiptItem).where(ReceiptItem.receipt_import_id == receipt_id))
    }
    for review_item in payload.items:
        item = items.get(review_item.id)
        if item is None:
            continue
        item.description = review_item.description
        item.quantity = review_item.quantity
        item.unit_price = review_item.unit_price
        item.total_amount = review_item.total_amount
        item.suggested_subcategory_name = review_item.suggested_subcategory_name
        item.status = "accepted" if review_item.accepted else "rejected"
        item.subcategory_id = (
            _resolve_subcategory_id(home_group_id, category_id, review_item.subcategory_id, review_item.suggested_subcategory_name, db)
            if review_item.accepted
            else None
        )
    receipt.status = "reviewed"
    receipt.category_id = category_id
    log_action(
        db,
        home_group_id,
        user.id,
        "receipt_review",
        "receipt",
        f"Ticket revisado: {receipt.filename}",
        receipt.id,
    )
    db.commit()
    db.refresh(receipt)
    logger.info("receipt_review_done home_group_id=%s receipt_id=%s category_id=%s items=%s", home_group_id, receipt.id, receipt.category_id, len(payload.items))
    return _receipt_read(receipt, db)


@router.put("/{receipt_id}/association", response_model=ReceiptImportRead)
def associate_receipt(
    home_group_id: int,
    receipt_id: int,
    payload: ReceiptAssociationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReceiptImportRead:
    require_home_member(home_group_id, user, db)
    receipt = db.get(ReceiptImport, receipt_id)
    if receipt is None or receipt.home_group_id != home_group_id:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    expense = db.get(Expense, payload.expense_id)
    if expense is None or expense.home_group_id != home_group_id:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    category_id = _valid_category_id(home_group_id, payload.category_id, db) if payload.category_id else receipt.category_id
    receipt.expense_id = expense.id
    receipt.category_id = category_id
    receipt.status = "associated"
    if category_id:
        expense.category_id = category_id
    log_action(
        db,
        home_group_id,
        user.id,
        "receipt_associate",
        "receipt",
        f"Ticket asociado a gasto: {receipt.filename}",
        receipt.id,
        expense.original_amount,
        expense.currency,
    )
    db.commit()
    db.refresh(receipt)
    logger.info("receipt_associate_done home_group_id=%s receipt_id=%s expense_id=%s category_id=%s", home_group_id, receipt.id, expense.id, category_id)
    return _receipt_read(receipt, db)


@router.delete("/{receipt_id}")
def delete_receipt(
    home_group_id: int,
    receipt_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_home_member(home_group_id, user, db)
    receipt = db.get(ReceiptImport, receipt_id)
    if receipt is None or receipt.home_group_id != home_group_id:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    db.execute(delete(ReceiptItem).where(ReceiptItem.receipt_import_id == receipt.id))
    log_action(
        db,
        home_group_id,
        user.id,
        "receipt_delete",
        "receipt",
        f"Ticket borrado: {receipt.filename}",
        receipt.id,
    )
    db.delete(receipt)
    db.commit()
    logger.info("receipt_delete_done home_group_id=%s receipt_id=%s", home_group_id, receipt_id)
    return {"ok": True}


def _receipt_read(receipt: ReceiptImport, db: Session) -> ReceiptImportRead:
    items = list(
        db.scalars(
            select(ReceiptItem)
            .where(ReceiptItem.receipt_import_id == receipt.id)
            .order_by(ReceiptItem.id)
        )
    )
    parsed_total = sum((Decimal(item.total_amount) for item in items), Decimal("0.00")) if items else None
    return ReceiptImportRead(
        id=receipt.id,
        expense_id=receipt.expense_id,
        category_id=receipt.category_id,
        filename=receipt.filename,
        status=receipt.status,
        created_at=receipt.created_at.isoformat(),
        parsed_total=parsed_total,
        items=[
            ReceiptItemRead(
                id=item.id,
                description=item.description,
                subcategory_id=item.subcategory_id,
                suggested_subcategory_name=item.suggested_subcategory_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_amount=item.total_amount,
                status=item.status,
            )
            for item in items
        ],
    )


def _find_category_by_name(home_group_id: int, name: str, db: Session) -> Category | None:
    return db.scalar(select(Category).where(Category.home_group_id == home_group_id, Category.name == name))


def _valid_category_id(home_group_id: int, category_id: int | None, db: Session) -> int | None:
    if category_id is None:
        return None
    category = db.get(Category, category_id)
    if category is None or category.home_group_id != home_group_id:
        raise HTTPException(status_code=400, detail="Categoria invalida")
    return category.id


def _resolve_subcategory_id(
    home_group_id: int,
    category_id: int | None,
    subcategory_id: int | None,
    suggested_name: str | None,
    db: Session,
) -> int | None:
    if not category_id:
        return None
    if subcategory_id:
        subcategory = db.get(Subcategory, subcategory_id)
        if subcategory is None or subcategory.home_group_id != home_group_id or subcategory.category_id != category_id:
            raise HTTPException(status_code=400, detail="Subcategoria invalida")
        return subcategory.id
    name = (suggested_name or "").strip()
    if not name:
        return None
    existing = db.scalar(select(Subcategory).where(Subcategory.home_group_id == home_group_id, Subcategory.category_id == category_id, Subcategory.name == name))
    if existing:
        return existing.id
    subcategory = Subcategory(home_group_id=home_group_id, category_id=category_id, name=name[:80], is_system=False)
    db.add(subcategory)
    db.flush()
    logger.info("receipt_subcategory_created home_group_id=%s category_id=%s subcategory_id=%s name=%s", home_group_id, category_id, subcategory.id, subcategory.name)
    return subcategory.id
