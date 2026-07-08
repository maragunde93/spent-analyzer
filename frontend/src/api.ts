import { categories, demoDashboard, demoExpenses, demoImport } from "./mockData";
import type { AuditLog, CashWalletSummary, Category, Currency, DashboardSummary, Expense, HomeGroup, ImportBatch, ReceiptImport, Subcategory, User } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? "/api" : "/finance/api");
const TEST_USER_EMAIL = import.meta.env.VITE_TEST_USER_EMAIL;
export const apiFallbacksEnabled = import.meta.env.VITE_ENABLE_API_FALLBACKS === "true" || import.meta.env.DEV;
const authHeaders: Record<string, string> = TEST_USER_EMAIL ? { "X-Test-User-Email": String(TEST_USER_EMAIL) } : {};

async function request<T>(path: string, init?: RequestInit, fallback?: T): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      credentials: "include",
      headers: { ...authHeaders, ...(init?.headers ?? {}) }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as T;
  } catch {
    if (apiFallbacksEnabled && fallback !== undefined) return fallback;
    throw new Error("No se pudo conectar con la API");
  }
}

export const api = {
  me: () => request<User>("/auth/me"),
  login: (payload: { username: string; password: string }) =>
    request<User>(
      "/auth/login",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }
    ),
  loginUrl: () => `${API_BASE}/auth/login/google`,
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  households: () => request<HomeGroup[]>("/households", undefined, [{ id: 1, name: "Casa Adrogue" }]),
  members: (homeId: number) => request<User[]>(`/households/${homeId}/members`, undefined, [
    { id: 1, email: "mauro@example.test", display_name: "Mauro", role: "owner" },
    { id: 2, email: "mica@example.test", display_name: "Mica", role: "member" }
  ]),
  dashboard: (homeId: number, paidByUserId?: string, categoryIds: number[] = []) => {
    const search = new URLSearchParams();
    if (paidByUserId && paidByUserId !== "all") search.set("paid_by_user_id", paidByUserId);
    for (const categoryId of categoryIds) search.append("category_ids", String(categoryId));
    const params = search.toString() ? `?${search.toString()}` : "";
    return request<DashboardSummary>(`/households/${homeId}/dashboard${params}`, undefined, demoDashboard);
  },
  expenses: (homeId: number) => request<Expense[]>(`/households/${homeId}/expenses`, undefined, demoExpenses),
  categories: (homeId: number) => request<Category[]>(`/households/${homeId}/categories`, undefined, categories),
  loadDefaultCategories: (homeId: number) =>
    request<Category[]>(
      `/households/${homeId}/categories/defaults`,
      { method: "POST" },
      categories
    ),
  createCategory: (homeId: number, category: Pick<Category, "name" | "color" | "icon">) =>
    request<Category>(
      `/households/${homeId}/categories`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(category)
      },
      { id: Math.floor(Math.random() * 10000), subcategories: [], ...category }
    ),
  updateCategory: (homeId: number, categoryId: number, category: Pick<Category, "name" | "color" | "icon">) =>
    request<Category>(
      `/households/${homeId}/categories/${categoryId}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(category)
      },
      { id: categoryId, subcategories: [], ...category }
    ),
  createSubcategory: (homeId: number, payload: { category_id: number; name: string }) =>
    request<Category>(
      `/households/${homeId}/subcategories`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      },
      categories.find((category) => category.id === payload.category_id) ?? categories[0]
    ),
  updateSubcategory: (homeId: number, subcategoryId: number, payload: Pick<Subcategory, "name">) =>
    request<Category>(
      `/households/${homeId}/subcategories/${subcategoryId}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      },
      categories[0]
    ),
  deleteSubcategory: (homeId: number, subcategoryId: number) =>
    request<{ ok: boolean }>(
      `/households/${homeId}/subcategories/${subcategoryId}`,
      { method: "DELETE" }
    ),
  createExpense: (homeId: number, expense: Partial<Expense>) =>
    request<Expense>(
      `/households/${homeId}/expenses`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(expense)
      },
      { ...demoExpenses[0], id: Math.floor(Math.random() * 10000), ...expense } as Expense
    ),
  updateExpense: (homeId: number, expenseId: number, expense: Partial<Expense>) =>
    request<Expense>(
      `/households/${homeId}/expenses/${expenseId}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(expense)
      },
      { ...demoExpenses[0], id: expenseId, ...expense } as Expense
    ),
  deleteExpense: (homeId: number, expenseId: number) =>
    request<{ ok: boolean }>(
      `/households/${homeId}/expenses/${expenseId}`,
      { method: "DELETE" }
    ),
  uploadCardImport: (homeId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportBatch>(
      `/households/${homeId}/imports/bbva-visa`,
      { method: "POST", body: form },
      demoImport
    );
  },
  uploadAccountImport: (homeId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportBatch>(
      `/households/${homeId}/imports/bbva-account`,
      { method: "POST", body: form },
      demoImport
    );
  },
  imports: (homeId: number, status?: string) => {
    const params = status ? `?status=${status}` : "";
    return request<ImportBatch[]>(`/households/${homeId}/imports${params}`, undefined, [demoImport]);
  },
  importBatch: (homeId: number, batchId: number) =>
    request<ImportBatch>(`/households/${homeId}/imports/${batchId}`, undefined, demoImport),
  deleteImport: (homeId: number, batchId: number) =>
    request<{ ok: boolean }>(
      `/households/${homeId}/imports/${batchId}`,
      { method: "DELETE" }
    ),
  commitImport: (
    homeId: number,
    batchId: number,
    lineIds: number[],
    paidByUserId: number,
    categoryOverrides: Record<number, number | null>,
    subcategoryOverrides: Record<number, number | null>,
    recurringOverrides: Record<number, boolean> = {},
    noteOverrides: Record<number, string | null> = {},
    reimbursementOverrides: Record<number, boolean> = {},
    paidByOverrides: Record<number, number> = {},
    rejectedLineIds: number[] = []
  ) =>
    request<{ created: number }>(
      `/households/${homeId}/imports/${batchId}/commit`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          line_ids: lineIds,
          paid_by_user_id: paidByUserId,
          paid_by_overrides: paidByOverrides,
          rejected_line_ids: rejectedLineIds,
          category_overrides: categoryOverrides,
          subcategory_overrides: subcategoryOverrides,
          recurring_overrides: recurringOverrides,
          note_overrides: noteOverrides,
          reimbursement_overrides: reimbursementOverrides
        })
      },
      { created: lineIds.length }
    ),
  cashWallet: (homeId: number) => request<CashWalletSummary>(`/households/${homeId}/cash-wallet`, undefined, {
    balances: [{ user_id: 1, currency: "ARS", balance: "87500.00" }],
    entries: [
      { id: 1, user_id: 1, date: "2026-05-20", description: "Extraccion cajero", currency: "ARS", amount: "100000.00" },
      { id: 2, user_id: 2, date: "2026-05-21", description: "Efectivo inicial", currency: "ARS", amount: "50000.00" }
    ]
  }),
  adjustCashWallet: (homeId: number, payload: { user_id: number; currency: Currency; target_balance: string; description: string }) =>
    request<{ id: number; delta: string }>(
      `/households/${homeId}/cash-wallet/adjust`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }
    ),
  history: (homeId: number) => request<AuditLog[]>(`/households/${homeId}/history`, undefined, []),
  receipts: (homeId: number) => request<ReceiptImport[]>(`/households/${homeId}/receipts`, undefined, []),
  uploadReceipt: (homeId: number, file: File | File[], expenseId?: number, signal?: AbortSignal) => {
    const form = new FormData();
    const files = Array.isArray(file) ? file : [file];
    files.forEach((item) => form.append("files", item));
    if (expenseId) form.append("expense_id", String(expenseId));
    return request<ReceiptImport>(
      `/households/${homeId}/receipts`,
      { method: "POST", body: form, signal }
    );
  },
  updateReceiptItems: (homeId: number, receiptId: number, categoryId: number | null, items: Array<{ id: number; description: string; subcategory_id: number | null; suggested_subcategory_name: string | null; quantity: string | null; unit_price: string | null; total_amount: string; accepted: boolean }>) =>
    request<ReceiptImport>(
      `/households/${homeId}/receipts/${receiptId}/items`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category_id: categoryId, items })
      }
    ),
  associateReceipt: (homeId: number, receiptId: number, payload: { expense_id: number; category_id: number | null }) =>
    request<ReceiptImport>(
      `/households/${homeId}/receipts/${receiptId}/association`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }
    ),
  deleteReceipt: (homeId: number, receiptId: number) =>
    request<{ ok: boolean }>(
      `/households/${homeId}/receipts/${receiptId}`,
      { method: "DELETE" }
    )
};
