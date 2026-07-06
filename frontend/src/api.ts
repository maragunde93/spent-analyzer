import { categories, demoDashboard, demoExpenses, demoImport } from "./mockData";
import type { AuditLog, CashWalletSummary, Category, Currency, DashboardSummary, Expense, HomeGroup, ImportBatch, ReceiptImport, User } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
const headers = { "X-Test-User-Email": "mauro@example.test" };

async function request<T>(path: string, init?: RequestInit, fallback?: T): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { ...init, headers: { ...headers, ...(init?.headers ?? {}) } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as T;
  } catch {
    if (fallback !== undefined) return fallback;
    throw new Error("No se pudo conectar con la API");
  }
}

export const api = {
  households: () => request<HomeGroup[]>("/households", undefined, [{ id: 1, name: "Casa Adrogue" }]),
  members: (homeId: number) => request<User[]>(`/households/${homeId}/members`, undefined, [
    { id: 1, email: "mauro@example.test", display_name: "Mauro", role: "owner" },
    { id: 2, email: "mica@example.test", display_name: "Mica", role: "member" }
  ]),
  dashboard: (homeId: number, paidByUserId?: string) => {
    const params = paidByUserId && paidByUserId !== "all" ? `?paid_by_user_id=${paidByUserId}` : "";
    return request<DashboardSummary>(`/households/${homeId}/dashboard${params}`, undefined, demoDashboard);
  },
  expenses: (homeId: number) => request<Expense[]>(`/households/${homeId}/expenses`, undefined, demoExpenses),
  categories: (homeId: number) => request<Category[]>(`/households/${homeId}/categories`, undefined, categories),
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
    subcategoryOverrides: Record<number, number | null>
  ) =>
    request<{ created: number }>(
      `/households/${homeId}/imports/${batchId}/commit`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          line_ids: lineIds,
          paid_by_user_id: paidByUserId,
          category_overrides: categoryOverrides,
          subcategory_overrides: subcategoryOverrides
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
  uploadReceipt: (homeId: number, file: File, expenseId?: number) => {
    const form = new FormData();
    form.append("file", file);
    if (expenseId) form.append("expense_id", String(expenseId));
    return request<ReceiptImport>(
      `/households/${homeId}/receipts`,
      { method: "POST", body: form }
    );
  }
};
