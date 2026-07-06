from datetime import date as Date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.domain import Currency, ExpenseSource, ImportLineKind


class UserRead(BaseModel):
    id: int
    email: str
    display_name: str

    model_config = ConfigDict(from_attributes=True)


class HomeGroupRead(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class MemberRead(BaseModel):
    id: int
    email: str
    display_name: str
    role: str


class SubcategoryRead(BaseModel):
    id: int
    category_id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class CategoryRead(BaseModel):
    id: int
    name: str
    color: str
    icon: str
    subcategories: list[SubcategoryRead] = []

    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    name: str
    color: str = "#38bdf8"
    icon: str = "tag"


class CategoryUpdate(BaseModel):
    name: str
    color: str
    icon: str = "tag"


class ExpenseCreate(BaseModel):
    date: Date
    description: str
    category_id: int | None = None
    subcategory_id: int | None = None
    paid_by_user_id: int
    currency: Currency = Currency.ARS
    original_amount: Decimal
    amount_ars: Decimal | None = None
    source: ExpenseSource = ExpenseSource.manual
    notes: str | None = Field(default=None, max_length=500)
    is_recurring: bool = False


class ExpenseUpdate(BaseModel):
    date: Date | None = None
    description: str | None = None
    category_id: int | None = None
    subcategory_id: int | None = None
    paid_by_user_id: int | None = None
    currency: Currency | None = None
    original_amount: Decimal | None = None
    amount_ars: Decimal | None = None
    source: ExpenseSource | None = None
    notes: str | None = Field(default=None, max_length=500)
    is_recurring: bool | None = None


class ExpenseRead(ExpenseCreate):
    id: int
    home_group_id: int
    uploaded_by_user_id: int
    amount_ars: Decimal

    model_config = ConfigDict(from_attributes=True)


class DashboardSummary(BaseModel):
    total_ars: Decimal
    by_category: list[dict]
    by_user: list[dict]
    trend: list[dict]
    monthly_by_category: list[dict] = []
    cumulative_by_category: list[dict] = []
    recurring_preview: list[dict]


class ImportLineRead(BaseModel):
    id: int
    date: Date
    description: str
    coupon: str | None
    kind: ImportLineKind
    currency: Currency
    original_amount: Decimal
    suggested_category_id: int | None
    suggested_subcategory_id: int | None
    suggested_recurring: bool = False
    status: str
    duplicate_status: str = "new"

    model_config = ConfigDict(from_attributes=True)


class ImportBatchRead(BaseModel):
    id: int
    filename: str
    source_type: str
    statement_account: str | None
    period_label: str | None
    status: str
    created_at: str | None = None
    lines: list[ImportLineRead] = []


class ImportCommitRequest(BaseModel):
    line_ids: list[int]
    paid_by_user_id: int
    category_overrides: dict[int, int | None] = {}
    subcategory_overrides: dict[int, int | None] = {}
    recurring_overrides: dict[int, bool] = {}


class CashWalletEntryCreate(BaseModel):
    user_id: int
    date: Date
    description: str
    currency: Currency = Currency.ARS
    amount: Decimal


class CashWalletAdjustment(BaseModel):
    user_id: int
    currency: Currency = Currency.ARS
    target_balance: Decimal
    description: str = "Ajuste manual de efectivo"


class CashWalletSummary(BaseModel):
    balances: list[dict]
    entries: list[dict]


class AuditLogRead(BaseModel):
    id: int
    actor_user_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    description: str
    currency: Currency | None
    amount: Decimal | None
    created_at: str


class ReceiptImportRead(BaseModel):
    id: int
    expense_id: int | None
    filename: str
    status: str
    created_at: str
