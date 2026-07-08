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
    consumption_count: int = 0


class MemberUpdate(BaseModel):
    email: str = Field(max_length=255)
    display_name: str = Field(max_length=120)


class SubcategoryRead(BaseModel):
    id: int
    category_id: int
    name: str
    is_system: bool = False

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


class SubcategoryCreate(BaseModel):
    category_id: int
    name: str = Field(max_length=80)


class SubcategoryUpdate(BaseModel):
    name: str = Field(max_length=80)


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


class DashboardFxRate(BaseModel):
    from_currency: Currency = Currency.USD
    to_currency: Currency = Currency.ARS
    rate: Decimal
    source: str
    date: Date | None = None
    is_fallback: bool = False


class DashboardSummary(BaseModel):
    total_ars: Decimal
    by_category: list[dict]
    by_user: list[dict]
    trend: list[dict]
    monthly_by_category: list[dict] = []
    cumulative_by_category: list[dict] = []
    card_statement_periods: list[str] = []
    recurring_preview: list[dict]
    fx_rate: DashboardFxRate | None = None


class ImportLineRead(BaseModel):
    id: int
    date: Date
    description: str
    cardholder_name: str | None = None
    coupon: str | None
    kind: ImportLineKind
    currency: Currency
    original_amount: Decimal
    suggested_category_id: int | None
    suggested_subcategory_id: int | None
    suggested_recurring: bool = False
    notes: str | None = Field(default=None, max_length=500)
    status: str
    duplicate_status: str = "new"

    model_config = ConfigDict(from_attributes=True)


class ImportBatchRead(BaseModel):
    id: int
    filename: str
    source_type: str
    uploaded_by_user_id: int
    statement_account: str | None
    period_label: str | None
    fx_rate_ars_per_usd: Decimal | None = None
    status: str
    created_at: str | None = None
    paid_by_user_ids: list[int] = []
    lines: list[ImportLineRead] = []


class ImportCommitRequest(BaseModel):
    line_ids: list[int]
    paid_by_user_id: int
    paid_by_overrides: dict[int, int] = {}
    rejected_line_ids: list[int] = []
    category_overrides: dict[int, int | None] = {}
    subcategory_overrides: dict[int, int | None] = {}
    recurring_overrides: dict[int, bool] = {}
    note_overrides: dict[int, str | None] = {}
    reimbursement_overrides: dict[int, bool] = {}


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


class ReceiptItemRead(BaseModel):
    id: int
    description: str
    subcategory_id: int | None = None
    suggested_subcategory_name: str | None = None
    quantity: Decimal | None
    unit_price: Decimal | None
    total_amount: Decimal
    status: str = "accepted"

    model_config = ConfigDict(from_attributes=True)


class ReceiptItemReview(BaseModel):
    id: int
    description: str = Field(max_length=240)
    subcategory_id: int | None = None
    suggested_subcategory_name: str | None = Field(default=None, max_length=80)
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    total_amount: Decimal
    accepted: bool = True


class ReceiptReviewRequest(BaseModel):
    category_id: int | None = None
    items: list[ReceiptItemReview]


class ReceiptAssociationRequest(BaseModel):
    expense_id: int
    category_id: int | None = None


class ReceiptImportRead(BaseModel):
    id: int
    expense_id: int | None
    category_id: int | None = None
    filename: str
    status: str
    created_at: str
    parsed_total: Decimal | None = None
    items: list[ReceiptItemRead] = []
