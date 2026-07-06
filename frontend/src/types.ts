export type Currency = "ARS" | "USD";
export type ExpenseSource = "manual" | "import_pdf" | "bank_import" | "cash" | "transfer" | "other";

export type Category = {
  id: number;
  name: string;
  color: string;
  icon: string;
  subcategories?: Subcategory[];
};

export type Subcategory = {
  id: number;
  category_id: number;
  name: string;
};

export type User = {
  id: number;
  email: string;
  display_name: string;
  role?: string;
};

export type HomeGroup = {
  id: number;
  name: string;
};

export type Expense = {
  id: number;
  date: string;
  description: string;
  category_id: number | null;
  subcategory_id?: number | null;
  paid_by_user_id: number;
  uploaded_by_user_id: number;
  source: ExpenseSource;
  currency: Currency;
  original_amount: string;
  amount_ars: string;
  notes?: string | null;
};

export type DashboardSummary = {
  total_ars: string;
  by_category: Array<{ name: string; amount_ars: string }>;
  by_user: Array<{ user_id: number; amount_ars: string }>;
  trend: Array<{ period: string; amount_ars: string }>;
  monthly_by_category: Array<Record<string, string>>;
  cumulative_by_category: Array<Record<string, string>>;
  recurring_preview: Array<{ description: string; expected_amount: string; currency: Currency; cadence: string }>;
};

export type ImportLine = {
  id: number;
  date: string;
  description: string;
  coupon: string | null;
  kind:
    | "purchase"
    | "refund"
    | "payment"
    | "tax"
    | "fee"
    | "adjustment"
    | "debit_purchase"
    | "cash_withdrawal"
    | "card_payment"
    | "transfer"
    | "income"
    | "previous_payment";
  currency: Currency;
  original_amount: string;
  suggested_category_id: number | null;
  suggested_subcategory_id: number | null;
  status: string;
  duplicate_status: "new" | "previously_parsed" | "already_committed";
};

export type ImportBatch = {
  id: number;
  filename: string;
  source_type: string;
  statement_account: string | null;
  period_label: string | null;
  status: string;
  created_at: string | null;
  lines: ImportLine[];
};

export type CashWalletSummary = {
  balances: Array<{ user_id: number; currency: Currency; balance: string }>;
  entries: Array<{ id: number; user_id: number; date: string; description: string; currency: Currency; amount: string }>;
};

export type AuditLog = {
  id: number;
  actor_user_id: number | null;
  action: string;
  entity_type: string;
  entity_id: number | null;
  description: string;
  currency: Currency | null;
  amount: string | null;
  created_at: string;
};

export type ReceiptImport = {
  id: number;
  expense_id: number | null;
  filename: string;
  status: string;
  created_at: string;
};
