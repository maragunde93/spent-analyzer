from datetime import date as Date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class MercadoPagoIntegrationRead(BaseModel):
    user_id: int
    connected: bool
    enabled: bool = False
    mp_user_id: str | None = None
    mp_nickname: str | None = None
    mp_site_id: str | None = None
    last_sync_at: str | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None
    last_report_file_name: str | None = None
    last_sync_started_at: str | None = None
    last_sync_completed_at: str | None = None
    last_sync_begin_date: str | None = None
    last_sync_end_date: str | None = None
    last_sync_imported: int | None = None
    last_sync_ignored: int | None = None
    last_sync_duplicates: int | None = None
    updated_at: str | None = None


class MercadoPagoTokenUpdate(BaseModel):
    access_token: str = Field(min_length=10, max_length=5000)
    enabled: bool = True


class MercadoPagoSyncRequest(BaseModel):
    start_date: Date | None = None
    end_date: Date | None = None


class MercadoPagoSyncRead(BaseModel):
    batch_id: int | None = None
    report_file_name: str
    imported: int
    ignored: int
    duplicates: int
    begin_date: str | None = None
    end_date: str | None = None


class MercadoPagoSyncAccepted(BaseModel):
    status: str = "running"


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
    description: str = Field(min_length=1, max_length=240)
    category_id: int | None = None
    subcategory_id: int | None = None
    paid_by_user_id: int
    currency: Currency = Currency.ARS
    original_amount: Decimal
    amount_ars: Decimal | None = None
    source: ExpenseSource = ExpenseSource.manual
    notes: str | None = Field(default=None, max_length=500)
    is_recurring: bool = False
    is_shared: bool = False

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("La descripcion no puede estar vacia")
        return stripped


class ExpenseUpdate(BaseModel):
    date: Date | None = None
    description: str | None = Field(default=None, min_length=1, max_length=240)
    category_id: int | None = None
    subcategory_id: int | None = None
    paid_by_user_id: int | None = None
    currency: Currency | None = None
    original_amount: Decimal | None = None
    amount_ars: Decimal | None = None
    source: ExpenseSource | None = None
    notes: str | None = Field(default=None, max_length=500)
    is_recurring: bool | None = None
    is_shared: bool | None = None

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("La descripcion no puede estar vacia")
        return stripped


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
    monthly_category_by_payer: list[dict] = []
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
    suggested_shared: bool = False
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
    statement_period: str | None = None
    card_network: str | None = None
    fx_rate_ars_per_usd: Decimal | None = None
    status: str
    created_at: str | None = None
    paid_by_user_ids: list[int] = []
    lines: list[ImportLineRead] = []


class ImportBatchUpdate(BaseModel):
    statement_period: str | None = None


class ImportCommitRequest(BaseModel):
    line_ids: list[int]
    paid_by_user_id: int
    paid_by_overrides: dict[int, int] = {}
    rejected_line_ids: list[int] = []
    category_overrides: dict[int, int | None] = {}
    subcategory_overrides: dict[int, int | None] = {}
    recurring_overrides: dict[int, bool] = {}
    shared_overrides: dict[int, bool] = {}
    note_overrides: dict[int, str | None] = {}
    description_overrides: dict[int, str] = {}
    reimbursement_overrides: dict[int, bool] = {}

    @field_validator("description_overrides")
    @classmethod
    def validate_description_overrides(cls, value: dict[int, str]) -> dict[int, str]:
        cleaned: dict[int, str] = {}
        for line_id, description in value.items():
            normalized = description.strip()
            if not normalized:
                raise ValueError("La descripcion no puede estar vacia")
            if len(normalized) > 240:
                raise ValueError("La descripcion no puede superar 240 caracteres")
            cleaned[line_id] = normalized
        return cleaned


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
