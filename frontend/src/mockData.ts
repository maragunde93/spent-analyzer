import type { Category, DashboardSummary, Expense, ImportBatch } from "./types";

export const users = [
  { id: 1, email: "mauro@example.test", display_name: "Mauro", role: "owner" },
  { id: 2, email: "mica@example.test", display_name: "Mica", role: "member" }
];

export const categories: Category[] = [
  { id: 1, name: "Delivery", color: "#0ea5e9", icon: "utensils" },
  { id: 2, name: "Supermercado", color: "#a28211", icon: "shopping-cart" },
  {
    id: 3,
    name: "Servicios",
    color: "#a35a33",
    icon: "receipt",
    subcategories: [
      { id: 301, category_id: 3, name: "Electricidad" },
      { id: 302, category_id: 3, name: "Agua" },
      { id: 303, category_id: 3, name: "Gas" },
      { id: 304, category_id: 3, name: "Auto" },
      { id: 305, category_id: 3, name: "Internet" }
    ]
  },
  { id: 4, name: "Suscripciones", color: "#ffd84d", icon: "repeat" },
  { id: 5, name: "Vacaciones", color: "#08a612", icon: "plane" },
  { id: 7, name: "Transporte", color: "#8b92cb", icon: "car" }
];

export const demoExpenses: Expense[] = [
  {
    id: 1,
    date: "2026-05-30",
    description: "PEDIDOSYA*THOUSAND BURG",
    category_id: 1,
    paid_by_user_id: 1,
    uploaded_by_user_id: 1,
    source: "import_pdf",
    currency: "ARS",
    original_amount: "39380.00",
    amount_ars: "39380.00"
  },
  {
    id: 2,
    date: "2026-05-14",
    description: "DISCO SM 037",
    category_id: 2,
    paid_by_user_id: 1,
    uploaded_by_user_id: 1,
    source: "import_pdf",
    currency: "ARS",
    original_amount: "163472.90",
    amount_ars: "163472.90"
  },
  {
    id: 3,
    date: "2026-05-12",
    description: "OPENAI *CHATGPT SUBSCR",
    category_id: 4,
    paid_by_user_id: 1,
    uploaded_by_user_id: 1,
    source: "import_pdf",
    currency: "USD",
    original_amount: "20.00",
    amount_ars: "20000.00"
  },
  {
    id: 4,
    date: "2026-05-16",
    description: "CARREFOUR EXPRESS",
    category_id: 2,
    paid_by_user_id: 2,
    uploaded_by_user_id: 2,
    source: "manual",
    currency: "ARS",
    original_amount: "62240.50",
    amount_ars: "62240.50"
  },
  {
    id: 5,
    date: "2026-05-22",
    description: "CABIFY VIAJE",
    category_id: 7,
    paid_by_user_id: 2,
    uploaded_by_user_id: 2,
    source: "manual",
    currency: "ARS",
    original_amount: "7400.00",
    amount_ars: "7400.00"
  }
];

export const demoDashboard: DashboardSummary = {
  total_ars: "222852.90",
  by_category: [
    { name: "Supermercado", amount_ars: "163472.90" },
    { name: "Delivery", amount_ars: "39380.00" },
    { name: "Suscripciones", amount_ars: "20000.00" }
  ],
  by_user: [{ user_id: 1, amount_ars: "222852.90" }],
  trend: [
    { period: "2026-03", amount_ars: "129000.00" },
    { period: "2026-04", amount_ars: "315000.00" },
    { period: "2026-05", amount_ars: "222852.90" }
  ],
  monthly_by_category: [
    { period: "2026-03", Delivery: "45000.00", Supermercado: "84000.00" },
    { period: "2026-04", Delivery: "60000.00", Supermercado: "170000.00", Servicios: "85000.00" },
    { period: "2026-05", Delivery: "39380.00", Supermercado: "163472.90", Suscripciones: "20000.00" }
  ],
  cumulative_by_category: [
    { period: "2026-03", Delivery: "45000.00", Supermercado: "84000.00" },
    { period: "2026-04", Delivery: "105000.00", Supermercado: "254000.00", Servicios: "85000.00" },
    { period: "2026-05", Delivery: "144380.00", Supermercado: "417472.90", Servicios: "85000.00", Suscripciones: "20000.00" }
  ],
  recurring_preview: [
    { description: "Movistar Hogar", expected_amount: "47759.99", currency: "ARS", cadence: "monthly" },
    { description: "OSDE", expected_amount: "202741.53", currency: "ARS", cadence: "monthly" }
  ]
};

export const demoImport: ImportBatch = {
  id: 1,
  filename: "bbva-demo.pdf",
  source_type: "bbva_visa_pdf",
  statement_account: "0000000000",
  period_label: "28-May-26",
  status: "parsed",
  created_at: "2026-07-03T12:00:00",
  lines: [
    {
      id: 101,
      date: "2026-05-12",
      description: "OPENAI *CHATGPT SUBSCR",
      coupon: "886716",
      kind: "purchase",
      currency: "USD",
      original_amount: "20.00",
      suggested_category_id: 4,
      suggested_subcategory_id: null,
      status: "pending",
      duplicate_status: "new"
    },
    {
      id: 102,
      date: "2026-05-28",
      description: "DB IVA $ 21%",
      coupon: null,
      kind: "tax",
      currency: "ARS",
      original_amount: "12095.80",
      suggested_category_id: null,
      suggested_subcategory_id: null,
      status: "pending",
      duplicate_status: "new"
    }
  ]
};
