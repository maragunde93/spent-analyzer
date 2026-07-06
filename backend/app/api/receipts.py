from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_home_member
from app.database import get_db
from app.models import Expense, ReceiptImport, User
from app.schemas import ReceiptImportRead
from app.services.audit import log_action

router = APIRouter(prefix="/households/{home_group_id}/receipts", tags=["receipts"])


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
        ReceiptImportRead(
            id=receipt.id,
            expense_id=receipt.expense_id,
            filename=receipt.filename,
            status=receipt.status,
            created_at=receipt.created_at.isoformat(),
        )
        for receipt in receipts
    ]


@router.post("", response_model=ReceiptImportRead)
async def upload_receipt(
    home_group_id: int,
    expense_id: int | None = Form(default=None),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReceiptImportRead:
    require_home_member(home_group_id, user, db)
    if expense_id is not None:
        expense = db.get(Expense, expense_id)
        if expense is None or expense.home_group_id != home_group_id:
            expense_id = None
    with NamedTemporaryFile(delete=False, suffix=Path(file.filename or "ticket.jpg").suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    tmp_path.unlink(missing_ok=True)

    receipt = ReceiptImport(
        home_group_id=home_group_id,
        uploaded_by_user_id=user.id,
        expense_id=expense_id,
        filename=file.filename or "ticket.jpg",
        status="uploaded_pending_ocr",
    )
    db.add(receipt)
    db.flush()
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
    return ReceiptImportRead(
        id=receipt.id,
        expense_id=receipt.expense_id,
        filename=receipt.filename,
        status=receipt.status,
        created_at=receipt.created_at.isoformat(),
    )
