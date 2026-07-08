import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bell,
  CalendarClock,
  ChevronDown,
  ChevronRight,
  CircleDollarSign,
  Copy,
  ClipboardList,
  History as HistoryIcon,
  Home,
  LogOut,
  MessageSquare,
  PiggyBank,
  Plus,
  ReceiptText,
  Search,
  Settings,
  Save,
  SwatchBook,
  Trash2,
  Upload,
  UserCircle,
  WalletCards,
  Wrench,
  X
} from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, apiFallbacksEnabled } from "./api";
import { categories as fallbackCategories, users as fallbackUsers } from "./mockData";
import type { Category, Currency, Expense, ExpenseSource, ImportBatch, ImportLine, ReceiptImport, ReceiptItem, User } from "./types";

function money(value: string | number, currency = "ARS") {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "ARS" ? 0 : 2,
    minimumFractionDigits: currency === "ARS" ? 0 : 2
  }).format(Number(value));
}

function numberFormat(value: string | number) {
  return new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(Number(value));
}

function fxSourceLabel(source?: string) {
  return {
    blue_average: "Dolar blue promedio",
    fallback_local: "Fallback local"
  }[source ?? ""] ?? source ?? "Sin fuente";
}

const chartColors = ["#334155", "#475569", "#64748b", "#71717a", "#94a3b8", "#0ea5e9", "#2563eb", "#60a5fa", "#38bdf8", "#ef4444"];
const noDashboardCategoriesSelected = -1;
const legendOrder = [
  "Delivery",
  "Servicios",
  "Suscripciones",
  "Salud",
  "Auto",
  "Transporte",
  "Ocio / gasto personal",
  "Vacaciones",
  "Vestimenta",
  "Regalos",
  "Sin categoria"
];

function toChartRows(rows: Array<Record<string, string>>) {
  return rows.map((row) =>
    Object.fromEntries(
      Object.entries(row).map(([key, value]) => [key, key === "period" ? value : Number(value)])
    )
  ) as Array<Record<string, string | number>>;
}

function chartKeys(rows: Array<Record<string, string | number>>) {
  return Array.from(new Set(rows.flatMap((row) => Object.keys(row).filter((key) => key !== "period"))));
}

function orderedKeysByFirstValue(rows: Array<Record<string, string | number>>, categories: Array<Pick<Category, "name">>) {
  const keys = chartKeys(rows);
  const categoryOrder = new Map(categories.map((category, index) => [category.name, index]));
  return keys.sort((a, b) => {
    const firstA = rows.findIndex((row) => Number(row[a] ?? 0) !== 0);
    const firstB = rows.findIndex((row) => Number(row[b] ?? 0) !== 0);
    if (firstA !== firstB) return firstA - firstB;
    return (categoryOrder.get(a) ?? 999) - (categoryOrder.get(b) ?? 999);
  });
}

function rowTotal(row: Record<string, string | number> | undefined, keys: string[]) {
  if (!row) return 0;
  return keys.reduce((sum, key) => sum + Number(row[key] ?? 0), 0);
}

function netVisibleConsumptionRows(rows: Array<Record<string, string | number>>, keys: string[]) {
  return rows.map((row) => {
    const positiveTotal = keys.reduce((sum, key) => sum + Math.max(0, Number(row[key] ?? 0)), 0);
    const netTotal = Math.max(0, rowTotal(row, keys));
    const ratio = positiveTotal > 0 && netTotal < positiveTotal ? netTotal / positiveTotal : 1;
    return Object.fromEntries([
      ["period", row.period],
      ...keys.map((key) => [key, Math.max(0, Number(row[key] ?? 0)) * ratio])
    ]);
  }) as Array<Record<string, string | number>>;
}

function sortKeysByFinalAmount(rows: Array<Record<string, string | number>>, keys: string[]) {
  const row = [...rows].reverse().find((item) => rowTotal(item, keys) !== 0);
  return [...keys].sort((a, b) => Number(row?.[b] ?? 0) - Number(row?.[a] ?? 0));
}

function categoryNames(categories: Array<Pick<Category, "name">>) {
  return categories.map((category) => category.name);
}

function sortLegendNames(names: string[]) {
  const order = new Map(legendOrder.map((name, index) => [name, index]));
  return [...names].sort((a, b) => (order.get(a) ?? 999) - (order.get(b) ?? 999) || a.localeCompare(b));
}

function monthPeriods(year: number) {
  return Array.from({ length: 12 }, (_, index) => `${year}-${String(index + 1).padStart(2, "0")}`);
}

function shiftMonthPeriod(period: string, offset: number) {
  const [year, month] = period.split("-").map(Number);
  const date = new Date(year, month - 1 + offset, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function monthWindowEnding(period: string, size: number) {
  return Array.from({ length: size }, (_, index) => shiftMonthPeriod(period, index - size + 1));
}

function fillMonthlyRows(rows: Array<Record<string, string | number>>, periods: string[], keys: string[]) {
  const byPeriod = new Map(rows.map((row) => [String(row.period), row]));
  return periods.map((period) => {
    const existing = byPeriod.get(period) ?? { period };
    return Object.fromEntries([
      ["period", period],
      ...keys.map((key) => [key, Number(existing[key] ?? 0)])
    ]);
  }) as Array<Record<string, string | number>>;
}

function fillCumulativeRows(rows: Array<Record<string, string | number>>, periods: string[], keys: string[]) {
  const byPeriod = new Map(rows.map((row) => [String(row.period), row]));
  const running: Record<string, number> = Object.fromEntries(keys.map((key) => [key, 0]));
  return periods.map((period) => {
    const existing = byPeriod.get(period);
    for (const key of keys) {
      if (existing && existing[key] !== undefined) running[key] = Number(existing[key] ?? 0);
    }
    return Object.fromEntries([
      ["period", period],
      ...keys.map((key) => [key, running[key] ?? 0])
    ]);
  }) as Array<Record<string, string | number>>;
}

function monthLabel(period: string) {
  const [year, month] = period.split("-").map(Number);
  return new Intl.DateTimeFormat("es-AR", { month: "long", year: "numeric" }).format(new Date(year, month - 1, 1));
}

function axisMonthLabel(period: string) {
  const [year, month] = period.split("-").map(Number);
  const name = new Intl.DateTimeFormat("es-AR", { month: "long" }).format(new Date(year, month - 1, 1));
  return `${period} (${name.charAt(0).toUpperCase()}${name.slice(1)})`;
}

function buildSortedStackRows(rows: Array<Record<string, string | number>>, periods: string[], keys: string[]) {
  const byPeriod = new Map(rows.map((row) => [String(row.period), row]));
  return periods.map((period) => {
    const row = byPeriod.get(period) ?? { period };
    const sorted = [...keys].sort((a, b) => Number(row[b] ?? 0) - Number(row[a] ?? 0));
    const output: Record<string, string | number> = { period, period_label: axisMonthLabel(period) };
    sorted.forEach((key, index) => {
      output[`slot_${index}`] = Number(row[key] ?? 0);
      output[`slot_${index}_category`] = key;
    });
    return output;
  });
}

function expensePeriod(expense: Pick<Expense, "date">) {
  return expense.date.slice(0, 7);
}

function groupExpensesByMonth(expenses: Expense[]) {
  return expenses.reduce<Record<string, Expense[]>>((acc, expense) => {
    const period = expensePeriod(expense);
    acc[period] = acc[period] ?? [];
    acc[period].push(expense);
    return acc;
  }, {});
}

function totalsByCurrency(expenses: Expense[]) {
  return expenses.reduce<Record<Currency, number>>((acc, expense) => {
    acc[expense.currency] = (acc[expense.currency] ?? 0) + Number(expense.original_amount);
    return acc;
  }, {} as Record<Currency, number>);
}

function formatCurrencyTotals(totals: Partial<Record<Currency, number>>) {
  return (["ARS", "USD"] as Currency[])
    .filter((currency) => Math.abs(totals[currency] ?? 0) > 0)
    .map((currency) => money(totals[currency] ?? 0, currency))
    .join(" / ") || money(0);
}

type ExpenseSortKey = "date" | "description" | "paid_by" | "category" | "source" | "recurring" | "amount" | "notes";
type ExpenseSort = { key: ExpenseSortKey; direction: "asc" | "desc" };
type AverageSortKey = "category" | "lastMonth" | "average3" | "average6" | "annualAverage";
type AverageSort = { key: AverageSortKey; direction: "asc" | "desc" };

function sortIndicator(sort: ExpenseSort, key: ExpenseSortKey) {
  if (sort.key !== key) return "";
  return sort.direction === "asc" ? " ↑" : " ↓";
}

function averageSortIndicator(sort: AverageSort, key: AverageSortKey) {
  if (sort.key !== key) return "";
  return sort.direction === "asc" ? " ↑" : " ↓";
}

function compareExpenseValues(a: string | number | boolean, b: string | number | boolean) {
  if (typeof a === "number" && typeof b === "number") return a - b;
  if (typeof a === "boolean" && typeof b === "boolean") return Number(a) - Number(b);
  return String(a).localeCompare(String(b), "es-AR", { sensitivity: "base" });
}

function expenseSortValue(expense: Expense, key: ExpenseSortKey, categories: Category[], users: User[]) {
  const category = categories.find((item) => item.id === expense.category_id);
  const subcategory = category?.subcategories?.find((item) => item.id === expense.subcategory_id);
  const user = users.find((item) => item.id === expense.paid_by_user_id);
  return {
    date: expense.date,
    description: expense.description,
    paid_by: user?.display_name ?? "",
    category: `${category?.name ?? "Sin categoria"} ${subcategory?.name ?? ""}`,
    source: sourceLabel(expense.source),
    recurring: !!expense.is_recurring,
    amount: Number(expense.original_amount),
    notes: expense.notes ?? ""
  }[key];
}

function sortExpenses(expenses: Expense[], sort: ExpenseSort, categories: Category[], users: User[]) {
  return [...expenses].sort((a, b) => {
    const comparison = compareExpenseValues(expenseSortValue(a, sort.key, categories, users), expenseSortValue(b, sort.key, categories, users));
    if (comparison !== 0) return sort.direction === "asc" ? comparison : -comparison;
    return b.id - a.id;
  });
}

function categoryDeltaRows(rows: Array<Record<string, string | number>>, keys: string[], loadedPeriods: string[]) {
  const rowsByPeriod = new Map(rows.map((row) => [String(row.period), row]));
  return loadedPeriods.slice(1).map((period, periodIndex) => {
    const index = periodIndex + 1;
    const previousPeriods = loadedPeriods.slice(Math.max(0, index - 3), index);
    const row = rowsByPeriod.get(period) ?? { period };
    return {
      period: String(row.period),
      values: keys.map((key) => {
        const current = Number(row[key] ?? 0);
        const prior = previousPeriods.length
          ? previousPeriods.reduce((sum, priorPeriod) => sum + Number(rowsByPeriod.get(priorPeriod)?.[key] ?? 0), 0) / previousPeriods.length
          : 0;
        const percent = prior === 0 ? (current === 0 ? 0 : null) : ((current - prior) / Math.abs(prior)) * 100;
        return { key, current, prior, percent };
      })
    };
  });
}

function averageForPeriods(rowsByPeriod: Map<string, Record<string, string | number>>, key: string, periods: string[], loadedPeriods: Set<string>) {
  const values = periods
    .filter((period) => loadedPeriods.has(period))
    .map((period) => Number(rowsByPeriod.get(period)?.[key] ?? 0));
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

function categoryAverageRows(
  rows: Array<Record<string, string | number>>,
  keys: string[],
  latestStatementPeriod: string | null,
  loadedStatementPeriods: string[],
  annualReferenceYear: number
) {
  if (!latestStatementPeriod) return [];
  const rowsByPeriod = new Map(rows.map((row) => [String(row.period), row]));
  const loadedPeriods = new Set(loadedStatementPeriods);
  const previousYearPeriods = monthPeriods(annualReferenceYear);
  return keys
    .map((key) => ({
      key,
      lastMonth: Number(rowsByPeriod.get(latestStatementPeriod)?.[key] ?? 0),
      average3: averageForPeriods(rowsByPeriod, key, monthWindowEnding(latestStatementPeriod, 3), loadedPeriods),
      average6: averageForPeriods(rowsByPeriod, key, monthWindowEnding(latestStatementPeriod, 6), loadedPeriods),
      annualAverage: averageForPeriods(rowsByPeriod, key, previousYearPeriods, loadedPeriods)
    }));
}

type CategoryAverageRow = ReturnType<typeof categoryAverageRows>[number];

function sortCategoryAverageRows(rows: CategoryAverageRow[], sort: AverageSort) {
  return [...rows].sort((a, b) => {
    const left = sort.key === "category" ? a.key : a[sort.key];
    const right = sort.key === "category" ? b.key : b[sort.key];
    const comparison = typeof left === "number" && typeof right === "number"
      ? left - right
      : String(left).localeCompare(String(right), "es-AR", { sensitivity: "base" });
    if (comparison !== 0) return sort.direction === "asc" ? comparison : -comparison;
    return a.key.localeCompare(b.key, "es-AR", { sensitivity: "base" });
  });
}

function importSourceLabel(batch: Pick<ImportBatch, "source_type" | "filename">) {
  const filename = batch.filename.toLowerCase();
  if (batch.source_type === "bbva_account_xls") return "Statement cuenta";
  if (filename.includes("master")) return "Statement tarjeta master";
  return "Statement tarjeta visa";
}

type ImportCoverageCell = { status: "Pendiente" | "Procesado"; fxRate: string | null };

function buildImportCoverage(imports: ImportBatch[], users: User[]) {
  const rows = new Map<string, { key: string; source: string; uploadedByUserId: number; paidByUserId: number | null; months: Record<string, ImportCoverageCell> }>();
  const years = new Set<number>();
  const orderedImports = [...imports].sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? "") || a.id - b.id);
  for (const batch of orderedImports) {
    if (batch.lines.length && batch.lines.every((line) => line.duplicate_status === "already_committed" || line.status === "duplicate")) {
      continue;
    }
    const source = importSourceLabel(batch);
    const periods = new Set(
      batch.source_type === "bbva_account_xls"
        ? batch.lines.length ? batch.lines.map((line) => line.date.slice(0, 7)) : batch.created_at ? [batch.created_at.slice(0, 7)] : []
        : batch.statement_period ? [batch.statement_period] : batch.created_at ? [batch.created_at.slice(0, 7)] : []
    );
    const isProcessed = batch.status === "committed" || batch.lines.some((line) => line.status === "committed" || line.status === "ignored");
    const paidByIds = batch.paid_by_user_ids.length ? batch.paid_by_user_ids : [null];
    for (const paidByUserId of paidByIds) {
      const key = `${source}:${batch.statement_account ?? ""}:${paidByUserId ?? "pending"}`;
      if (!rows.has(key)) rows.set(key, { key, source, uploadedByUserId: batch.uploaded_by_user_id, paidByUserId, months: {} });
      const row = rows.get(key)!;
      for (const period of periods) {
        const year = Number(period.slice(0, 4));
        if (year) years.add(year);
        const status = isProcessed ? "Procesado" : "Pendiente";
        const current = row.months[period];
        if (!current || (current.status === "Pendiente" && status === "Procesado")) {
          row.months[period] = { status, fxRate: batch.fx_rate_ars_per_usd };
        }
      }
    }
  }
  const userOrder = new Map(users.map((user, index) => [user.id, index]));
  return {
    years: Array.from(years).sort((a, b) => b - a),
    rows: Array.from(rows.values()).sort((a, b) => a.source.localeCompare(b.source) || (userOrder.get(a.uploadedByUserId) ?? 999) - (userOrder.get(b.uploadedByUserId) ?? 999) || (userOrder.get(a.paidByUserId ?? -1) ?? 999) - (userOrder.get(b.paidByUserId ?? -1) ?? 999))
  };
}

function importTotals(lines: ImportLine[], selected: number[], sourceType?: string, reimbursementByLine: Record<number, boolean> = {}) {
  const totals = {
    total: {} as Record<string, number>,
    income: {} as Record<string, number>,
    expense: {} as Record<string, number>
  };
  for (const line of lines) {
    if (!selected.includes(line.id)) continue;
    const amount = Number(line.original_amount);
    totals.total[line.currency] = (totals.total[line.currency] ?? 0) + amount;
    if (sourceType === "bbva_account_xls") {
      if (line.kind === "income" && !reimbursementByLine[line.id]) totals.income[line.currency] = (totals.income[line.currency] ?? 0) + Math.abs(amount);
      else totals.expense[line.currency] = (totals.expense[line.currency] ?? 0) + Math.abs(amount);
    }
  }
  return totals;
}

function cardholderKey(line: Pick<ImportLine, "cardholder_name">) {
  return (line.cardholder_name?.trim() || "Titular").replace(/\s+/g, " ").toUpperCase();
}

function cardholderLabel(line: Pick<ImportLine, "cardholder_name">) {
  return line.cardholder_name?.trim() || "Titular";
}

function userIdForCardholder(name: string, users: User[], fallback: string) {
  const normalizedName = name.toLowerCase();
  const matched = users.find((user) => {
    const display = user.display_name.toLowerCase();
    return normalizedName.includes(display) || display.split(/\s+/).some((part) => part.length > 2 && normalizedName.includes(part));
  });
  return String(matched?.id ?? fallback);
}

function orderedImportLines(lines: ImportLine[], sourceType?: string) {
  if (sourceType === "bbva_account_xls") {
    return [...lines].sort((a, b) => a.date.localeCompare(b.date) || a.id - b.id);
  }
  const currencyOrder: Record<Currency, number> = { USD: 0, ARS: 1 };
  return [...lines].sort((a, b) => {
    const holderDiff = cardholderKey(a).localeCompare(cardholderKey(b));
    if (holderDiff) return holderDiff;
    const currencyDiff = currencyOrder[a.currency] - currencyOrder[b.currency];
    if (currencyDiff) return currencyDiff;
    return a.id - b.id;
  });
}

function importLinePeriod(line: ImportLine) {
  return line.date.slice(0, 7);
}

function importMonthTotals(lines: ImportLine[], selected: number[], period: string, reimbursementByLine: Record<number, boolean>) {
  return importTotals(lines.filter((line) => importLinePeriod(line) === period), selected, "bbva_account_xls", reimbursementByLine);
}

function importMonthCurrencies(lines: ImportLine[], period: string) {
  return Array.from(new Set(lines.filter((line) => importLinePeriod(line) === period).map((line) => line.currency)));
}

function importShareText(lines: ImportLine[], selected: number[], sourceType?: string) {
  const selectedLines = orderedImportLines(lines, sourceType).filter((line) => selected.includes(line.id) && !isIgnoredImportLine(line));
  const totals = importTotals(selectedLines, selected, sourceType);
  const header = [
    `Total ARS: ${money(Math.abs(totals.total.ARS ?? 0), "ARS")}`,
    `Total USD: ${money(Math.abs(totals.total.USD ?? 0), "USD")}`
  ].join(" ");
  const details = selectedLines.map((line) => `${line.description} - ${money(line.original_amount, line.currency)}`);
  return [header, ...details].join("\n");
}

async function copyTextToClipboard(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

function ImportMonthTotals({ lines, selected, period, reimbursementByLine }: { lines: ImportLine[]; selected: number[]; period: string; reimbursementByLine: Record<number, boolean> }) {
  const totals = importMonthTotals(lines, selected, period, reimbursementByLine);
  const currencies = importMonthCurrencies(lines, period);
  return (
    <div className="import-totals month-totals" aria-label={`Totales ${period}`}>
      {currencies.includes("ARS") && (
        <>
          <span>Ingresos ARS <strong>{money(totals.income.ARS ?? 0, "ARS")}</strong></span>
          <span>Egresos ARS <strong>{money(totals.expense.ARS ?? 0, "ARS")}</strong></span>
        </>
      )}
      {currencies.includes("USD") && (
        <>
          <span>Ingresos USD <strong>{money(totals.income.USD ?? 0, "USD")}</strong></span>
          <span>Egresos USD <strong>{money(totals.expense.USD ?? 0, "USD")}</strong></span>
        </>
      )}
    </div>
  );
}

function categoryColor(name: string, categories: Array<Pick<Category, "name" | "color">>, keys: string[]) {
  return categories.find((category) => category.name === name)?.color ?? chartColors[Math.max(keys.indexOf(name), 0) % chartColors.length];
}

function categoryOpacity(active: string | null, name: string) {
  return active && active !== name ? 0.18 : 1;
}

export function App() {
  const [section, setSection] = useState("dashboard");
  const [query, setQuery] = useState("");
  const [paidBy, setPaidBy] = useState("all");
  const [expenseCurrency, setExpenseCurrency] = useState<"all" | Currency>("all");
  const [dashboardCategoryIds, setDashboardCategoryIds] = useState<number[]>([]);
  const queryClient = useQueryClient();
  const currentUser = useQuery({ queryKey: ["me"], queryFn: api.me, retry: false });
  const households = useQuery({ queryKey: ["households"], queryFn: api.households, enabled: !!currentUser.data });
  const homeId = households.data?.[0]?.id ?? 1;
  const members = useQuery({ queryKey: ["members", homeId], queryFn: () => api.members(homeId), enabled: !!currentUser.data });
  const dashboard = useQuery({ queryKey: ["dashboard", homeId, paidBy, dashboardCategoryIds.join(",")], queryFn: () => api.dashboard(homeId, paidBy, dashboardCategoryIds), enabled: !!currentUser.data });
  const expenses = useQuery({ queryKey: ["expenses", homeId], queryFn: () => api.expenses(homeId), enabled: !!currentUser.data });
  const categoryQuery = useQuery({ queryKey: ["categories", homeId], queryFn: () => api.categories(homeId), enabled: !!currentUser.data });
  const cats = categoryQuery.data ?? (apiFallbacksEnabled ? fallbackCategories : []);
  const people = members.data?.length ? members.data : apiFallbacksEnabled ? fallbackUsers : [];
  const addExpense = useMutation({
    mutationFn: (expense: Partial<Expense>) => api.createExpense(homeId, expense),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["expenses", homeId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", homeId] });
      queryClient.invalidateQueries({ queryKey: ["cash", homeId] });
    }
  });
  const updateExpense = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<Expense> }) => api.updateExpense(homeId, id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["expenses", homeId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", homeId] });
      queryClient.invalidateQueries({ queryKey: ["cash", homeId] });
    }
  });
  const deleteExpense = useMutation({
    mutationFn: (id: number) => api.deleteExpense(homeId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["expenses", homeId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", homeId] });
      queryClient.invalidateQueries({ queryKey: ["cash", homeId] });
    }
  });
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      queryClient.clear();
      window.location.assign(import.meta.env.BASE_URL || "/");
    }
  });

  const filteredExpenses = useMemo(() => {
    return (expenses.data ?? []).filter((expense) => {
      const category = cats.find((cat) => cat.id === expense.category_id);
      const subcategory = category?.subcategories?.find((item) => item.id === expense.subcategory_id);
      const categoryName = category?.name ?? "Sin categoria";
      const haystack = `${expense.description} ${categoryName} ${subcategory?.name ?? ""}`.toLowerCase();
      const matchesText = haystack.includes(query.toLowerCase());
      const matchesUser = paidBy === "all" || String(expense.paid_by_user_id) === paidBy;
      const matchesCurrency = expenseCurrency === "all" || expense.currency === expenseCurrency;
      return matchesText && matchesUser && matchesCurrency;
    });
  }, [expenses.data, cats, query, paidBy, expenseCurrency]);

  if (currentUser.isLoading) return <LoadingScreen />;
  if (currentUser.isError || !currentUser.data) return <LoginScreen />;
  const authenticatedUser = currentUser.data;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Home size={20} /></div>
          <div>
            <strong>Spent Analyzer</strong>
            <span>{households.data?.[0]?.name ?? "Casa Adrogue"}</span>
          </div>
        </div>
        <nav>
          <NavButton active={section === "dashboard"} icon={<CircleDollarSign />} label="Resumen" onClick={() => setSection("dashboard")} />
          <NavButton active={section === "expenses"} icon={<ReceiptText />} label="Consumos" onClick={() => setSection("expenses")} />
          <NavButton active={section === "imports"} icon={<Upload />} label="Carga de Resumenes" onClick={() => setSection("imports")} />
          <NavButton active={section === "cash"} icon={<WalletCards />} label="Efectivo" onClick={() => setSection("cash")} />
          <NavButton active={section === "history"} icon={<HistoryIcon />} label="Historial" onClick={() => setSection("history")} />
          <NavButton active={section === "receipts"} icon={<ClipboardList />} label="Tickets" onClick={() => setSection("receipts")} />
          <NavButton active={section === "settings"} icon={<Settings />} label="Casa" onClick={() => setSection("settings")} />
        </nav>
        <div className="soon">
          <span>Proximas secciones</span>
          <button><PiggyBank size={16} /> Ahorros</button>
          <button><CalendarClock size={16} /> Compras futuras</button>
          <button><Wrench size={16} /> Mantenimiento</button>
        </div>
      </aside>
      <main className="content">
        <header className="topbar">
          <div>
            <p>Panel del hogar</p>
            <h1>{titleFor(section)}</h1>
          </div>
          <div className="top-actions">
            {section === "dashboard" && dashboard.data?.fx_rate && <FxRateBadge fxRate={dashboard.data.fx_rate} />}
            <button className="user-chip" type="button" title="Ver mi usuario" onClick={() => setSection("profile")}>
              <UserCircle size={16} />
              {authenticatedUser.display_name}
            </button>
            <button className="icon-button" title="Alertas"><Bell size={18} /></button>
            <button className="icon-button" title="Cerrar sesion" onClick={() => logout.mutate()}><LogOut size={18} /></button>
          </div>
        </header>
        {section === "dashboard" && (
          <Dashboard
            categories={cats}
            data={dashboard.data}
            users={people}
            paidBy={paidBy}
            setPaidBy={setPaidBy}
            categoryIds={dashboardCategoryIds}
            setCategoryIds={setDashboardCategoryIds}
          />
        )}
        {section === "expenses" && (
          <Expenses
            categories={cats}
            expenses={filteredExpenses}
            users={people}
            onAdd={(payload) => addExpense.mutate(payload)}
            onUpdate={(id, payload) => updateExpense.mutate({ id, payload })}
            onDelete={(id) => deleteExpense.mutate(id)}
            paidBy={paidBy}
            currencyFilter={expenseCurrency}
            query={query}
            setPaidBy={setPaidBy}
            setCurrencyFilter={setExpenseCurrency}
            setQuery={setQuery}
          />
        )}
        {section === "imports" && <Imports categories={cats} users={people} homeId={homeId} />}
        {section === "cash" && <CashWallet users={people} homeId={homeId} />}
        {section === "history" && <HistoryPanel users={people} homeId={homeId} />}
        {section === "receipts" && <ReceiptsLab categories={cats} expenses={expenses.data ?? []} homeId={homeId} />}
        {section === "settings" && <SettingsPanel categories={cats} users={people} homeId={homeId} />}
        {section === "profile" && <UserProfile currentUser={authenticatedUser} users={people} homeName={households.data?.[0]?.name ?? "Casa Adrogue"} />}
      </main>
    </div>
  );
}

function LoadingScreen() {
  return (
    <main className="auth-screen">
      <section className="auth-panel">
        <div className="brand-mark"><Home size={20} /></div>
        <h1>Finance</h1>
        <p>Cargando sesion...</p>
      </section>
    </main>
  );
}

function LoginScreen() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const login = useMutation({
    mutationFn: api.login,
    onSuccess: () => window.location.assign(import.meta.env.BASE_URL || "/")
  });

  return (
    <main className="auth-screen">
      <form
        className="auth-panel"
        onSubmit={(event) => {
          event.preventDefault();
          login.mutate({ username, password });
        }}
      >
        <div className="brand-mark"><Home size={20} /></div>
        <h1>Finance</h1>
        <p>Ingresa con tu usuario local para ver los consumos del hogar.</p>
        <label>
          <span>Usuario</span>
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required />
        </label>
        <label>
          <span>Contrasena</span>
          <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" required />
        </label>
        {login.isError && <p className="form-error">Usuario o contrasena incorrectos.</p>}
        <button className="primary" type="submit" disabled={login.isPending}>Ingresar</button>
      </form>
    </main>
  );
}

function NavButton(props: { active: boolean; icon: ReactNode; label: string; onClick: () => void }) {
  return (
    <button className={props.active ? "nav active" : "nav"} type="button" onClick={props.onClick}>
      {props.icon}
      <span>{props.label}</span>
    </button>
  );
}

function titleFor(section: string) {
  return {
    dashboard: "Resumen de consumos",
    expenses: "Consumos del hogar",
    imports: "Carga de Resumenes",
    cash: "Billetera de efectivo",
    history: "Historial",
    receipts: "Tickets de compras",
    settings: "Configuracion de casa",
    profile: "Mi usuario"
  }[section];
}

function UserProfile({ currentUser, users, homeName }: { currentUser: User; users: User[]; homeName: string }) {
  const member = users.find((user) => user.id === currentUser.id);
  const sameNameMembers = users.filter(
    (user) => user.id !== currentUser.id && user.display_name.trim().toLowerCase() === currentUser.display_name.trim().toLowerCase()
  );
  return (
    <section className="grid two">
      <div className="panel profile-panel">
        <h2>Usuario autenticado</h2>
        <div className="profile-identity">
          <UserCircle size={42} />
          <div>
            <strong>{currentUser.display_name}</strong>
            <span>{currentUser.email}</span>
          </div>
        </div>
        <dl className="profile-details">
          <div>
            <dt>ID</dt>
            <dd>#{currentUser.id}</dd>
          </div>
          <div>
            <dt>Rol en la casa</dt>
            <dd>{member?.role ?? "Sin membresia"}</dd>
          </div>
          <div>
            <dt>Consumos asociados</dt>
            <dd>{numberFormat(member?.consumption_count ?? 0)}</dd>
          </div>
          <div>
            <dt>Casa</dt>
            <dd>{homeName}</dd>
          </div>
        </dl>
      </div>
      <div className="panel profile-panel">
        <h2>Coincidencias</h2>
        {sameNameMembers.length ? (
          <div className="stack">
            <p className="warning">Hay otros miembros con el mismo nombre visible. Para distinguirlos, usá el mail o el ID.</p>
            {sameNameMembers.map((user) => (
              <div className="member-row profile-match-row" key={user.id}>
                <div className="member-name">
                  <strong>{user.display_name}</strong>
                  <small>#{user.id} - {user.role ?? "member"}</small>
                </div>
                <span>{user.email}</span>
                <strong>{numberFormat(user.consumption_count ?? 0)}</strong>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">No hay otros miembros con el mismo nombre visible.</p>
        )}
      </div>
    </section>
  );
}

function FxRateBadge({
  fxRate
}: {
  fxRate: NonNullable<Awaited<ReturnType<typeof api.dashboard>>["fx_rate"]>;
}) {
  return (
    <div className="fx-rate-badge" aria-label="Tipo de cambio Blue usado para conversiones">
      <div>
        <span>Tipo de cambio Blue</span>
        <small>{fxRate.date ?? "sin fecha"}{fxRate.is_fallback ? " - sin cotizacion cargada" : ""}</small>
      </div>
      <strong>US$ 1 = {money(fxRate.rate, "ARS")}</strong>
    </div>
  );
}

function Dashboard({
  categories,
  data,
  users,
  paidBy,
  setPaidBy,
  categoryIds,
  setCategoryIds
}: {
  categories: Array<Pick<Category, "id" | "name" | "color">>;
  data?: Awaited<ReturnType<typeof api.dashboard>>;
  users: User[];
  paidBy: string;
  setPaidBy: (value: string) => void;
  categoryIds: number[];
  setCategoryIds: (value: number[]) => void;
}) {
  const [activeMonthlyCategory, setActiveMonthlyCategory] = useState<string | null>(null);
  const [activeLegendCategory, setActiveLegendCategory] = useState<string | null>(null);
  const [expandedRecurring, setExpandedRecurring] = useState<Record<string, boolean>>({});
  const [averageSort, setAverageSort] = useState<AverageSort>({ key: "average6", direction: "desc" });
  const currentYear = new Date().getFullYear();
  const periods = monthPeriods(currentYear);
  const rawMonthlyData = toChartRows(data?.monthly_by_category ?? []);
  const baseMonthlyKeys = Array.from(new Set([...categoryNames(categories), ...chartKeys(rawMonthlyData)]));
  const categoryKeys = categoryNames(categories).filter((name) => baseMonthlyKeys.includes(name));
  const legendKeys = sortLegendNames(categoryKeys);
  const monthlyData = netVisibleConsumptionRows(fillMonthlyRows(rawMonthlyData, periods, baseMonthlyKeys), baseMonthlyKeys);
  const monthlyStackData = buildSortedStackRows(monthlyData, periods, baseMonthlyKeys);
  const rawCumulativeData = toChartRows(data?.cumulative_by_category ?? []);
  const cumulativeKeys = sortKeysByFinalAmount(rawCumulativeData, orderedKeysByFirstValue(rawCumulativeData, categories));
  const cumulativeData = netVisibleConsumptionRows(fillCumulativeRows(rawCumulativeData, periods, cumulativeKeys), cumulativeKeys);
  const cardStatementPeriods = [...(data?.card_statement_periods ?? [])].sort();
  const currentYearStatementPeriods = cardStatementPeriods.filter((period) => period.startsWith(`${currentYear}-`));
  const deltaRows = categoryDeltaRows(monthlyData, categoryKeys, currentYearStatementPeriods);
  const deltaPeriods = deltaRows.map((row) => row.period);
  const latestCardStatementPeriod = cardStatementPeriods.length ? cardStatementPeriods[cardStatementPeriods.length - 1] : null;
  const annualAverageYear = currentYear - 1;
  const averageRows = sortCategoryAverageRows(
    categoryAverageRows(rawMonthlyData, categoryKeys, latestCardStatementPeriod, cardStatementPeriods, annualAverageYear),
    averageSort
  );
  const allCategoryIds = categories.map((category) => Number(category.id));
  const noCategoriesSelected = categoryIds.includes(noDashboardCategoriesSelected);
  const activeChartCategory = activeLegendCategory ?? activeMonthlyCategory;
  const toggleLegendCategory = (name: string) => setActiveLegendCategory((current) => (current === name ? null : name));
  const updateAverageSort = (key: AverageSortKey) => {
    setAverageSort((current) => current.key === key ? { key, direction: current.direction === "asc" ? "desc" : "asc" } : { key, direction: key === "category" ? "asc" : "desc" });
  };
  return (
    <section className="grid dashboard-grid">
      <div className="panel dashboard-filters wide">
        <h2>Filtros</h2>
        <div className="filter-summary-row">
          <label>
            <span>Vista</span>
            <select value={paidBy} onChange={(event) => setPaidBy(event.target.value)} aria-label="Filtrar resumen por usuario">
              <option value="all">Todo el hogar</option>
              {users.map((user) => <option value={user.id} key={user.id}>{user.display_name}</option>)}
            </select>
          </label>
        </div>
        <div className="filter-checks" aria-label="Filtrar resumen por categorias">
          <div className="filter-heading">
            <span>Categorias</span>
            <div className="filter-actions">
              <button className="text-button" onClick={() => setCategoryIds([])} disabled={!categoryIds.length}>Todas</button>
              <button className="text-button" onClick={() => setCategoryIds([noDashboardCategoriesSelected])} disabled={noCategoriesSelected}>Limpiar</button>
            </div>
          </div>
          <div className="filter-grid">
          {sortLegendNames(categories.map((category) => category.name)).map((categoryName) => {
            const category = categories.find((item) => item.name === categoryName);
            if (!category) return null;
            const categoryId = Number(category.id);
            return (
            <label key={category.name} className="check-row">
              <input
                type="checkbox"
                aria-label={`Categoria ${category.name}`}
                checked={!noCategoriesSelected && (!categoryIds.length || categoryIds.includes(categoryId))}
                onChange={(event) => {
                  if (event.target.checked) {
                    if (noCategoriesSelected) {
                      setCategoryIds([categoryId]);
                    } else {
                      setCategoryIds(categoryIds.length ? [...categoryIds, categoryId] : allCategoryIds);
                    }
                  } else {
                    const current = categoryIds.length ? categoryIds.filter((id) => id !== noDashboardCategoriesSelected) : allCategoryIds;
                    const next = current.filter((item) => item !== categoryId);
                    setCategoryIds(next.length ? next : [noDashboardCategoriesSelected]);
                  }
                }}
              />
              <i style={{ background: category.color }} />
              {category.name}
            </label>
            );
          })}
          </div>
        </div>
      </div>
      <div className="panel chart-panel wide" data-testid="monthly-chart-panel">
        <h2>Consumo mensual {currentYear}</h2>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={monthlyStackData} onMouseLeave={() => setActiveMonthlyCategory(null)}>
            <CartesianGrid stroke="#223047" vertical={false} />
            <XAxis dataKey="period_label" tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <YAxis tickFormatter={(value) => numberFormat(value)} tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <Tooltip
              content={<MonthlySegmentTooltip activeCategory={activeMonthlyCategory} />}
              cursor={false}
              contentStyle={{ background: "#0f172a", border: "1px solid #263449", color: "#e2e8f0" }}
              itemStyle={{ color: "#e2e8f0" }}
              labelStyle={{ color: "#e2e8f0" }}
            />
            {baseMonthlyKeys.map((_, slotIndex) => (
              <Bar key={slotIndex} dataKey={`slot_${slotIndex}`} stackId="month" isAnimationActive={false} activeBar={false}>
                {monthlyStackData.map((row) => {
                  const category = String(row[`slot_${slotIndex}_category`] ?? "");
                  const value = Number(row[`slot_${slotIndex}`] ?? 0);
                  return (
                    <Cell
                      key={`${row.period}-${slotIndex}`}
                      data-testid={value ? "monthly-segment" : undefined}
                      fill={categoryColor(category, categories, legendKeys)}
                      fillOpacity={categoryOpacity(activeChartCategory, category)}
                      stroke={activeChartCategory === category ? "#f8fafc" : undefined}
                      strokeWidth={activeChartCategory === category ? 1 : 0}
                      onMouseEnter={() => setActiveMonthlyCategory(category)}
                    />
                  );
                })}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
        <CategoryLegend categories={categories} names={legendKeys} active={activeChartCategory} onToggle={toggleLegendCategory} />
      </div>
      <div className="panel recurring-panel wide">
        <h2>Proyeccion recurrente</h2>
        {(data?.recurring_preview ?? []).length ? (
          <div className="recurring-table-wrap">
            <table className="recurring-table">
              <colgroup>
                <col className="recurring-name-col" />
                <col className="recurring-category-col" />
                <col className="recurring-subcategory-col" />
                <col className="recurring-month-col" />
                <col className="recurring-money-col" />
                <col className="recurring-money-col" />
                <col className="recurring-money-col" />
                <col className="recurring-money-col" />
              </colgroup>
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Categoria</th>
                  <th>Subcategoria</th>
                  <th>Ultimo mes</th>
                  <th>Ultimo consumo</th>
                  <th>Promedio mensual</th>
                  <th>Acumulado</th>
                  <th>Proyeccion anualizada</th>
                </tr>
              </thead>
              <tbody>
                {(data?.recurring_preview ?? []).map((item, index) => {
                  const rowKey = `${item.description}-${item.category ?? ""}-${item.subcategory ?? ""}-${index}`;
                  const monthly = Number(item.monthly_average ?? item.expected_amount);
                  const lastAmount = Number(item.last_amount ?? item.expected_amount);
                  const accumulated = Number(item.accumulated_amount ?? monthly);
                  const annualized = Number(item.annualized_amount ?? monthly * 12);
                  const itemCount = item.items?.length ?? 0;
                  return (
                    <Fragment key={rowKey}>
                      <tr>
                        <td>
                          <button
                            className="link-button recurring-name"
                            onClick={() => setExpandedRecurring((current) => ({ ...current, [rowKey]: !current[rowKey] }))}
                            disabled={!itemCount}
                            type="button"
                          >
                            {expandedRecurring[rowKey] ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                            {item.description}
                          </button>
                        </td>
                        <td>{item.category ?? "Sin categoria"}</td>
                        <td>{item.subcategory ?? "-"}</td>
                        <td>{item.last_period ? axisMonthLabel(item.last_period) : "-"}</td>
                        <td>{money(lastAmount, item.currency)}</td>
                        <td>{money(monthly, item.currency)}</td>
                        <td>{money(accumulated, item.currency)}</td>
                        <td><strong>{money(annualized, item.currency)}</strong></td>
                      </tr>
                      {expandedRecurring[rowKey] && item.items?.map((expense) => (
                        <tr className="recurring-detail-row" key={`${rowKey}-${expense.date}-${expense.description}-${expense.amount}`}>
                          <td>{expense.date} - {expense.description}</td>
                          <td></td>
                          <td></td>
                          <td></td>
                          <td>{money(expense.amount, expense.currency)}</td>
                          <td>{money(expense.amount_ars, "ARS")}</td>
                          <td></td>
                          <td></td>
                        </tr>
                      ))}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : <p className="muted">Todavia no hay consumos marcados como recurrentes.</p>}
      </div>
      <div className="panel chart-panel wide cumulative-chart">
        <h2>Consumo acumulado {currentYear}</h2>
        <ResponsiveContainer width="100%" height={420}>
          <AreaChart data={cumulativeData}>
            <CartesianGrid stroke="#223047" vertical={false} />
            <XAxis dataKey="period" tickFormatter={(value) => axisMonthLabel(String(value))} tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <YAxis tickFormatter={(value) => numberFormat(value)} tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <Tooltip
              formatter={(value, name) => [money(Number(value)), String(name)]}
              cursor={false}
              offset={24}
              allowEscapeViewBox={{ x: true, y: true }}
              wrapperStyle={{ zIndex: 20 }}
              contentStyle={{ background: "#0f172a", border: "1px solid #263449", color: "#e2e8f0" }}
              itemStyle={{ color: "#e2e8f0" }}
              labelStyle={{ color: "#e2e8f0" }}
            />
            {cumulativeKeys.map((key) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                stackId="year"
                stroke={categoryColor(key, categories, cumulativeKeys)}
                strokeOpacity={activeChartCategory && activeChartCategory !== key ? 0.22 : 1}
                fill={categoryColor(key, categories, cumulativeKeys)}
                fillOpacity={activeChartCategory && activeChartCategory !== key ? 0.12 : 0.78}
                isAnimationActive={false}
                activeDot={{
                  r: 5,
                  stroke: "#f8fafc",
                  strokeWidth: 2,
                  fill: categoryColor(key, categories, cumulativeKeys)
                }}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
        <CategoryLegend categories={categories} names={legendKeys.filter((name) => cumulativeKeys.includes(name))} active={activeChartCategory} onToggle={toggleLegendCategory} />
      </div>
      <div className="panel chart-panel wide">
        <h2>Promedio mensual por categoria</h2>
        {latestCardStatementPeriod ? (
          <div className="average-table-wrap">
            <table className="average-table">
              <thead>
                <tr>
                  <th>
                    <button className="sort-header" type="button" onClick={() => updateAverageSort("category")}>
                      Categoria{averageSortIndicator(averageSort, "category")}
                    </button>
                  </th>
                  <th>
                    <button className="sort-header" type="button" onClick={() => updateAverageSort("lastMonth")}>
                      <span className="header-lines">
                        <span>Ultimo mes</span>
                        <span>({axisMonthLabel(latestCardStatementPeriod)}){averageSortIndicator(averageSort, "lastMonth")}</span>
                      </span>
                    </button>
                  </th>
                  <th>
                    <button className="sort-header" type="button" onClick={() => updateAverageSort("average3")}>
                      <span className="header-lines">
                        <span>Promedio mensual</span>
                        <span>(3 meses){averageSortIndicator(averageSort, "average3")}</span>
                      </span>
                    </button>
                  </th>
                  <th>
                    <button className="sort-header" type="button" onClick={() => updateAverageSort("average6")}>
                      <span className="header-lines">
                        <span>Promedio mensual</span>
                        <span>(6 meses){averageSortIndicator(averageSort, "average6")}</span>
                      </span>
                    </button>
                  </th>
                  <th>
                    <button className="sort-header" type="button" onClick={() => updateAverageSort("annualAverage")}>
                      <span className="header-lines">
                        <span>Promedio anual</span>
                        <span>({annualAverageYear}){averageSortIndicator(averageSort, "annualAverage")}</span>
                      </span>
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {averageRows.map((row) => (
                  <tr key={row.key}>
                    <td>
                      <span className="category-cell">
                        <i style={{ background: categoryColor(row.key, categories, legendKeys) }} />
                        {row.key}
                      </span>
                    </td>
                    <td>{money(row.lastMonth)}</td>
                    <td>{money(row.average3)}</td>
                    <td>{money(row.average6)}</td>
                    <td>{row.annualAverage ? money(row.annualAverage) : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="muted">Todavia no hay resumenes de tarjeta comparables para esta vista.</p>}
      </div>
      <div className="panel chart-panel wide">
        <h2>Variacion mensual por categoria {currentYear}</h2>
        <div className="delta-table-wrap">
          <table className="delta-table">
            <thead>
              <tr>
                <th>Categoria</th>
                {deltaPeriods.map((period) => <th key={period}>{axisMonthLabel(period)}</th>)}
              </tr>
            </thead>
            <tbody>
              {categoryKeys.map((key) => (
                <tr key={key}>
                  <td>{key}</td>
                  {deltaPeriods.map((period) => {
                    const value = deltaRows.find((row) => row.period === period)?.values.find((item) => item.key === key) ?? { percent: 0 };
                    return (
                    <td key={period}>
                      <span className={value.percent === null ? "delta new" : value.percent > 0 ? "delta up" : value.percent < 0 ? "delta down" : "delta flat"}>
                        {value.percent === null ? "Nuevo" : `${value.percent > 0 ? "+" : ""}${numberFormat(value.percent)}%`}
                      </span>
                    </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function MonthlySegmentTooltip({
  active,
  payload,
  activeCategory
}: {
  active?: boolean;
  payload?: Array<{ payload?: Record<string, string | number> }>;
  activeCategory?: string | null;
}) {
  if (!active || !payload?.length || !activeCategory) return null;
  const row = payload[0].payload ?? {};
  const slot = Object.keys(row).find((key) => key.startsWith("slot_") && !key.endsWith("_category") && row[`${key}_category`] === activeCategory);
  const value = slot ? Number(row[slot] ?? 0) : 0;
  if (!value) return null;
  return (
    <div className="chart-tooltip" role="tooltip">
      <strong>{activeCategory}</strong>
      <span>{money(value)}</span>
    </div>
  );
}

function CategoryLegend({
  categories,
  names,
  active,
  onToggle
}: {
  categories: Array<Pick<Category, "name" | "color">>;
  names: string[];
  active?: string | null;
  onToggle?: (name: string) => void;
}) {
  if (!names.length) return null;
  return (
    <div className="chart-legend" aria-label="Leyenda de categorias">
      {names.map((name) => (
        <button
          key={name}
          className={active && active !== name ? "dimmed" : undefined}
          onClick={() => onToggle?.(name)}
          aria-pressed={active === name}
          type="button"
        >
          <i style={{ background: categoryColor(name, categories, names) }} />
          {name}
        </button>
      ))}
    </div>
  );
}

function Expenses(props: {
  categories: Category[];
  expenses: Expense[];
  users: User[];
  query: string;
  paidBy: string;
  currencyFilter: "all" | Currency;
  setQuery: (value: string) => void;
  setPaidBy: (value: string) => void;
  setCurrencyFilter: (value: "all" | Currency) => void;
  onAdd: (payload: Partial<Expense>) => void;
  onUpdate: (id: number, payload: Partial<Expense>) => void;
  onDelete: (id: number) => void;
}) {
  const [amount, setAmount] = useState("0");
  const [description, setDescription] = useState("");
  const [notes, setNotes] = useState("");
  const [paidByUserId, setPaidByUserId] = useState(String(props.users[0]?.id ?? 1));
  const [categoryId, setCategoryId] = useState(String(props.categories[0]?.id ?? ""));
  const [subcategoryId, setSubcategoryId] = useState("");
  const [source, setSource] = useState<ExpenseSource>("cash");
  const [isRecurring, setIsRecurring] = useState(false);
  const [editingExpenseId, setEditingExpenseId] = useState<number | null>(null);
  const [editAmount, setEditAmount] = useState("");
  const [editCategoryId, setEditCategoryId] = useState("");
  const [editSubcategoryId, setEditSubcategoryId] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editIsRecurring, setEditIsRecurring] = useState(false);
  const [openNoteId, setOpenNoteId] = useState<number | null>(null);
  const [expandedMonths, setExpandedMonths] = useState<Record<string, boolean>>({});
  const [sort, setSort] = useState<ExpenseSort>({ key: "date", direction: "desc" });
  const selectedCategory = props.categories.find((category) => String(category.id) === categoryId);
  const editingCategory = props.categories.find((category) => String(category.id) === editCategoryId);
  const currentMonth = new Date().toISOString().slice(0, 7);
  const groupedExpenses = groupExpensesByMonth(props.expenses);
  const visibleTotals = totalsByCurrency(props.expenses);
  const periods = Object.keys(groupedExpenses).sort().reverse();
  const hasActiveFilters = !!props.query.trim() || props.paidBy !== "all" || props.currencyFilter !== "all";
  const activeFilterKey = `${props.query.trim().toLowerCase()}|${props.paidBy}|${props.currencyFilter}`;
  const periodKey = periods.join("|");
  const previousFilterKey = useRef(activeFilterKey);
  useEffect(() => {
    const filterChanged = previousFilterKey.current !== activeFilterKey;
    previousFilterKey.current = activeFilterKey;
    if (!hasActiveFilters) return;
    setExpandedMonths((current) => {
      const next = { ...current };
      let changed = false;
      for (const period of periods) {
        if ((filterChanged || next[period] === undefined) && next[period] !== true) {
          next[period] = true;
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [activeFilterKey, hasActiveFilters, periodKey]);
  const isMonthExpanded = (period: string) => expandedMonths[period] ?? period === currentMonth;
  const allMonthsExpanded = periods.length > 0 && periods.every((period) => isMonthExpanded(period));
  const setAllMonthsExpanded = (expanded: boolean) => {
    setExpandedMonths((current) => {
      const next = { ...current };
      for (const period of periods) next[period] = expanded;
      return next;
    });
  };
  const updateSort = (key: ExpenseSortKey) => {
    setSort((current) => current.key === key ? { key, direction: current.direction === "asc" ? "desc" : "asc" } : { key, direction: key === "amount" || key === "date" ? "desc" : "asc" });
  };
  const startEditing = (expense: Expense) => {
    setEditingExpenseId(expense.id);
    setEditAmount(String(expense.original_amount));
    setEditCategoryId(expense.category_id ? String(expense.category_id) : "");
    setEditSubcategoryId(expense.subcategory_id ? String(expense.subcategory_id) : "");
    setEditNotes(expense.notes ?? "");
    setEditIsRecurring(!!expense.is_recurring);
  };
  return (
    <section className="stack">
      <div className="expense-layout">
        <div className="expense-side">
          <div className="panel form-panel expense-filter-panel">
            <h2>Filtros</h2>
            <label className="search">
              <Search size={16} />
              <input value={props.query} onChange={(e) => props.setQuery(e.target.value)} placeholder="Buscar gasto" aria-label="Buscar gasto" />
            </label>
            <label>
              <span>Pagado por</span>
              <select value={props.paidBy} onChange={(e) => props.setPaidBy(e.target.value)} aria-label="Filtrar por usuario">
                <option value="all">Hogar</option>
                {props.users.map((u) => <option value={u.id} key={u.id}>{u.display_name}</option>)}
              </select>
            </label>
            <label>
              <span>Moneda</span>
              <select value={props.currencyFilter} onChange={(e) => props.setCurrencyFilter(e.target.value as "all" | Currency)} aria-label="Filtrar por moneda">
                <option value="all">Todas</option>
                <option value="ARS">ARS</option>
                <option value="USD">USD</option>
              </select>
            </label>
          </div>
          <form
            className="panel form-panel"
            onSubmit={(e) => {
              e.preventDefault();
              props.onAdd({
                date: new Date().toISOString().slice(0, 10),
                description,
                paid_by_user_id: Number(paidByUserId),
                category_id: categoryId ? Number(categoryId) : null,
                subcategory_id: subcategoryId ? Number(subcategoryId) : null,
                source,
                currency: "ARS" as Currency,
                original_amount: amount,
                notes: notes.trim() || null,
                is_recurring: isRecurring
              });
              setDescription("");
              setAmount("0");
              setNotes("");
              setSubcategoryId("");
              setIsRecurring(false);
            }}
          >
            <h2>Nuevo gasto</h2>
            <input value={description} onChange={(e) => setDescription(e.target.value)} aria-label="Descripcion" placeholder="Descripcion" />
            <input value={amount} onChange={(e) => setAmount(e.target.value)} aria-label="Importe" inputMode="decimal" />
            <select value={paidByUserId} onChange={(e) => setPaidByUserId(e.target.value)} aria-label="Pagado por">
              {props.users.map((u) => <option value={u.id} key={u.id}>{u.display_name}</option>)}
            </select>
            <select value={categoryId} onChange={(e) => {
              const nextCategory = props.categories.find((category) => String(category.id) === e.target.value);
              setCategoryId(e.target.value);
              setSubcategoryId("");
              if (nextCategory?.name === "Suscripciones" || nextCategory?.name === "Servicios") setIsRecurring(true);
            }} aria-label="Categoria">
              {props.categories.map((c) => <option value={c.id} key={c.id}>{c.name}</option>)}
            </select>
            <select value={subcategoryId} onChange={(e) => setSubcategoryId(e.target.value)} aria-label="Subcategoria">
              <option value="">Sin subcategoria</option>
              {(selectedCategory?.subcategories ?? []).map((subcategory) => <option value={subcategory.id} key={subcategory.id}>{subcategory.name}</option>)}
            </select>
            <select value={source} onChange={(e) => setSource(e.target.value as ExpenseSource)} aria-label="Origen">
              <option value="cash">Efectivo</option>
              <option value="transfer">Transferencia</option>
              <option value="other">Otro</option>
            </select>
            <label className="check-row form-check">
              <input type="checkbox" checked={isRecurring} onChange={(event) => setIsRecurring(event.target.checked)} />
              Recurrente
            </label>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value.slice(0, 500))} aria-label="Nota" placeholder="Nota opcional" maxLength={500} />
            <button className="primary" type="submit"><Plus size={16} /> Agregar</button>
          </form>
        </div>
        <div className="panel table-panel">
          <div className="table-heading">
            <div>
              <h2>Movimientos</h2>
              <div className="import-totals">
                <span>Total ARS <strong>{money(visibleTotals.ARS ?? 0, "ARS")}</strong></span>
                <span>Total USD <strong>{money(visibleTotals.USD ?? 0, "USD")}</strong></span>
              </div>
            </div>
            <button
              className="primary month-bulk-toggle"
              type="button"
              disabled={!periods.length}
              onClick={() => setAllMonthsExpanded(!allMonthsExpanded)}
              aria-label={allMonthsExpanded ? "Colapsar todos los meses" : "Expandir todos los meses"}
            >
              {allMonthsExpanded ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
              {allMonthsExpanded ? "Colapsar todos" : "Expandir todos"}
            </button>
          </div>
          <table className="expense-table">
            <colgroup>
              <col className="expense-date-col" />
              <col className="expense-description-col" />
              <col className="expense-paid-col" />
              <col className="expense-category-col" />
              <col className="expense-source-col" />
              <col className="expense-recurring-col" />
              <col className="expense-amount-col" />
              <col className="expense-note-col" />
              <col className="expense-actions-col" />
            </colgroup>
            <thead>
              <tr>
                <th><button className="sort-header" onClick={() => updateSort("date")}>Fecha{sortIndicator(sort, "date")}</button></th>
                <th><button className="sort-header" onClick={() => updateSort("description")}>Descripcion{sortIndicator(sort, "description")}</button></th>
                <th><button className="sort-header" onClick={() => updateSort("paid_by")}>Pago{sortIndicator(sort, "paid_by")}</button></th>
                <th><button className="sort-header" onClick={() => updateSort("category")}>Categoria{sortIndicator(sort, "category")}</button></th>
                <th><button className="sort-header" onClick={() => updateSort("source")}>Origen{sortIndicator(sort, "source")}</button></th>
                <th><button className="sort-header" onClick={() => updateSort("recurring")}>Recurrente{sortIndicator(sort, "recurring")}</button></th>
                <th><button className="sort-header" onClick={() => updateSort("amount")}>Importe{sortIndicator(sort, "amount")}</button></th>
                <th><button className="sort-header" onClick={() => updateSort("notes")}>Nota{sortIndicator(sort, "notes")}</button></th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {periods.map((period) => {
                const monthExpenses = groupedExpenses[period];
                const sortedMonthExpenses = sortExpenses(monthExpenses, sort, props.categories, props.users);
                const expanded = isMonthExpanded(period);
                const monthTotals = totalsByCurrency(monthExpenses);
                return (
                  <Fragment key={period}>
                    <tr className="month-group-row">
                      <td colSpan={9}>
                        <button
                          className="month-toggle"
                          onClick={() => setExpandedMonths((current) => ({ ...current, [period]: !expanded }))}
                          aria-label={`${expanded ? "Colapsar" : "Expandir"} ${monthLabel(period)}`}
                        >
                          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                          <strong>{monthLabel(period)}</strong>
                          <span>{monthExpenses.length} gastos</span>
                          <b>{formatCurrencyTotals(monthTotals)}</b>
                        </button>
                      </td>
                    </tr>
                    {expanded && sortedMonthExpenses.map((expense) => {
                      const cat = props.categories.find((c) => c.id === expense.category_id);
                      const subcat = cat?.subcategories?.find((subcategory) => subcategory.id === expense.subcategory_id);
                      const isEditing = editingExpenseId === expense.id;
                      const hasNotes = !!expense.notes?.trim();
                      return (
                        <Fragment key={expense.id}>
                          <tr className={!expense.category_id ? "needs-review-row" : undefined}>
                            <td>{expense.date}</td>
                            <td className="description-cell">{expense.description}</td>
                            <td>{props.users.find((u) => u.id === expense.paid_by_user_id)?.display_name ?? "Usuario"}</td>
                            <td className="category-cell">
                              {isEditing ? (
                                <div className="inline-edit-fields">
                                  <select
                                    value={editCategoryId}
                                    onChange={(event) => {
                                      setEditCategoryId(event.target.value);
                                      setEditSubcategoryId("");
                                      const nextCategory = props.categories.find((category) => String(category.id) === event.target.value);
                                      if (nextCategory?.name === "Suscripciones" || nextCategory?.name === "Servicios") setEditIsRecurring(true);
                                    }}
                                    aria-label={`Editar categoria ${expense.description}`}
                                  >
                                    <option value="">Sin categoria</option>
                                    {props.categories.map((category) => <option value={category.id} key={category.id}>{category.name}</option>)}
                                  </select>
                                  <select
                                    value={editSubcategoryId}
                                    disabled={!editingCategory?.subcategories?.length}
                                    onChange={(event) => setEditSubcategoryId(event.target.value)}
                                    aria-label={`Editar subcategoria ${expense.description}`}
                                  >
                                    <option value="">Sin subcategoria</option>
                                    {(editingCategory?.subcategories ?? []).map((subcategory) => <option value={subcategory.id} key={subcategory.id}>{subcategory.name}</option>)}
                                  </select>
                                </div>
                              ) : (
                                <span className={!expense.category_id ? "chip warning-chip" : "chip"} style={{ borderColor: cat?.color }}>
                                  {!expense.category_id && <AlertTriangle size={14} />}
                                  {cat?.name ?? "Sin categoria"}{subcat ? ` / ${subcat.name}` : ""}
                                </span>
                              )}
                            </td>
                            <td>{sourceLabel(expense.source)}</td>
                            <td>
                              {isEditing ? (
                                <input type="checkbox" checked={editIsRecurring} onChange={(event) => setEditIsRecurring(event.target.checked)} aria-label={`Editar recurrente ${expense.description}`} />
                              ) : (
                                <input
                                  type="checkbox"
                                  checked={!!expense.is_recurring}
                                  onChange={(event) => props.onUpdate(expense.id, { is_recurring: event.target.checked })}
                                  aria-label={`Recurrente ${expense.description}`}
                                />
                              )}
                            </td>
                            <td>
                              {isEditing ? (
                                <input className="amount-cell-input" value={editAmount} onChange={(event) => setEditAmount(event.target.value)} aria-label={`Editar importe ${expense.description}`} inputMode="decimal" />
                              ) : (
                                money(expense.original_amount, expense.currency)
                              )}
                            </td>
                            <td className="note-cell">
                              {isEditing ? (
                                <textarea className="note-edit" value={editNotes} onChange={(event) => setEditNotes(event.target.value.slice(0, 500))} aria-label={`Editar nota ${expense.description}`} maxLength={500} />
                              ) : hasNotes ? (
                                <button className="icon-button" title="Ver nota" aria-label={`Ver nota ${expense.description}`} onClick={() => setOpenNoteId(openNoteId === expense.id ? null : expense.id)}>
                                  <MessageSquare size={16} />
                                </button>
                              ) : (
                                <span className="muted">-</span>
                              )}
                            </td>
                            <td className="actions-cell">
                              {isEditing ? (
                                <div className="row-actions">
                                  <button
                                    className="icon-button"
                                    title="Guardar gasto"
                                    aria-label={`Guardar gasto ${expense.description}`}
                                    onClick={() => {
                                      props.onUpdate(expense.id, {
                                        category_id: editCategoryId ? Number(editCategoryId) : null,
                                        subcategory_id: editSubcategoryId ? Number(editSubcategoryId) : null,
                                        original_amount: editAmount,
                                        notes: editNotes.trim() || null,
                                        is_recurring: editIsRecurring
                                      });
                                      setEditingExpenseId(null);
                                    }}
                                  >
                                    <Save size={16} />
                                  </button>
                                  <button className="icon-button" title="Cancelar" aria-label={`Cancelar edicion ${expense.description}`} onClick={() => setEditingExpenseId(null)}>
                                    <X size={16} />
                                  </button>
                                </div>
                              ) : (
                                <div className="row-actions">
                                  <button className="icon-button" title="Editar gasto" aria-label={`Editar gasto ${expense.description}`} onClick={() => startEditing(expense)}>
                                    <Settings size={16} />
                                  </button>
                                  <button
                                    className="icon-button danger"
                                    title="Eliminar gasto"
                                    aria-label={`Eliminar gasto ${expense.description}`}
                                    onClick={() => {
                                      if (window.confirm(`Eliminar el gasto "${expense.description}"?`)) {
                                        props.onDelete(expense.id);
                                      }
                                    }}
                                  >
                                    <Trash2 size={16} />
                                  </button>
                                </div>
                              )}
                            </td>
                          </tr>
                          {openNoteId === expense.id && hasNotes && (
                            <tr className="note-row">
                              <td colSpan={9}>{expense.notes}</td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function Imports({ categories, users, homeId }: { categories: Category[]; users: User[]; homeId: number }) {
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [categoryByLine, setCategoryByLine] = useState<Record<number, number | null>>({});
  const [subcategoryByLine, setSubcategoryByLine] = useState<Record<number, number | null>>({});
  const [recurringByLine, setRecurringByLine] = useState<Record<number, boolean>>({});
  const [notesByLine, setNotesByLine] = useState<Record<number, string>>({});
  const [reimbursementByLine, setReimbursementByLine] = useState<Record<number, boolean>>({});
  const [paidByByHolder, setPaidByByHolder] = useState<Record<string, string>>({});
  const [copiedHolder, setCopiedHolder] = useState<string | null>(null);
  const [statementPeriod, setStatementPeriod] = useState("");
  const [paidByUserId, setPaidByUserId] = useState(String(users[0]?.id ?? 1));
  const queryClient = useQueryClient();
  const pendingImports = useQuery({ queryKey: ["imports", homeId, "parsed"], queryFn: () => api.imports(homeId, "parsed") });
  const loadBatch = (data: ImportBatch) => {
    setBatch(data);
    setSelected(data.lines.filter((line) => line.status === "pending" && line.duplicate_status !== "already_committed" && !isIgnoredImportLine(line)).map((line) => line.id));
    setCategoryByLine(Object.fromEntries(data.lines.map((line) => [line.id, line.suggested_category_id])));
    setSubcategoryByLine(Object.fromEntries(data.lines.map((line) => [line.id, line.suggested_subcategory_id])));
    setRecurringByLine(Object.fromEntries(data.lines.map((line) => [line.id, line.suggested_recurring])));
    setNotesByLine(Object.fromEntries(data.lines.map((line) => [line.id, line.notes ?? ""])));
    setReimbursementByLine(Object.fromEntries(data.lines.map((line) => [line.id, line.kind === "reimbursement"])));
    setPaidByByHolder(Object.fromEntries(Array.from(new Set(data.lines.map(cardholderKey))).map((holder) => [holder, userIdForCardholder(holder, users, String(users[0]?.id ?? 1))])));
    setStatementPeriod(data.statement_period ?? "");
    setCopiedHolder(null);
  };
  const updateBatch = useMutation({
    mutationFn: ({ batchId, nextStatementPeriod }: { batchId: number; nextStatementPeriod: string }) =>
      api.updateImportBatch(homeId, batchId, { statement_period: nextStatementPeriod || null }),
    onSuccess: (data) => {
      setBatch(data);
      setStatementPeriod(data.statement_period ?? "");
      queryClient.invalidateQueries({ queryKey: ["imports", homeId, "parsed"] });
      queryClient.invalidateQueries({ queryKey: ["imports", homeId, "all"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", homeId] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    }
  });
  const uploadCard = useMutation({
    mutationFn: (file: File) => api.uploadCardImport(homeId, file),
    onSuccess: (data) => {
      loadBatch(data);
      queryClient.invalidateQueries({ queryKey: ["imports", homeId, "parsed"] });
    }
  });
  const uploadAccount = useMutation({
    mutationFn: (file: File) => api.uploadAccountImport(homeId, file),
    onSuccess: (data) => {
      loadBatch(data);
      queryClient.invalidateQueries({ queryKey: ["imports", homeId, "parsed"] });
    }
  });
  const commit = useMutation({
    mutationFn: async () => {
      const rejected = (batch?.lines ?? [])
        .filter((line) => line.status === "pending" && !selected.includes(line.id) && !isIgnoredImportLine(line))
        .map((line) => line.id);
      const paidByOverrides = Object.fromEntries(
        (batch?.lines ?? [])
          .filter((line) => selected.includes(line.id))
          .map((line) => [line.id, Number(paidByByHolder[cardholderKey(line)] ?? paidByUserId)])
      );
      if (batch!.source_type !== "bbva_account_xls" && statementPeriod !== (batch!.statement_period ?? "")) {
        await api.updateImportBatch(homeId, batch!.id, { statement_period: statementPeriod || null });
      }
      return api.commitImport(homeId, batch!.id, selected, Number(paidByUserId), categoryByLine, subcategoryByLine, recurringByLine, notesByLine, reimbursementByLine, paidByOverrides, rejected);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["expenses", homeId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", homeId] });
      setBatch(null);
      setSelected([]);
      setCategoryByLine({});
      setSubcategoryByLine({});
      setRecurringByLine({});
      setNotesByLine({});
      setReimbursementByLine({});
      setPaidByByHolder({});
      setStatementPeriod("");
      setCopiedHolder(null);
      queryClient.invalidateQueries({ queryKey: ["imports", homeId, "parsed"] });
      queryClient.invalidateQueries({ queryKey: ["imports", homeId, "all"] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    }
  });
  const deleteImport = useMutation({
    mutationFn: (batchId: number) => api.deleteImport(homeId, batchId),
    onSuccess: (_, batchId) => {
      if (batch?.id === batchId) {
        setBatch(null);
        setSelected([]);
        setCategoryByLine({});
        setSubcategoryByLine({});
        setRecurringByLine({});
        setNotesByLine({});
        setReimbursementByLine({});
        setPaidByByHolder({});
        setStatementPeriod("");
        setCopiedHolder(null);
      }
      queryClient.invalidateQueries({ queryKey: ["imports", homeId, "parsed"] });
    }
  });
  const totals = importTotals(batch?.lines ?? [], selected, batch?.source_type, reimbursementByLine);
  const reviewCount = (batch?.lines ?? []).filter((line) => selected.includes(line.id) && !categoryByLine[line.id] && !isIgnoredImportLine(line)).length;
  const reviewLines = useMemo(() => orderedImportLines(batch?.lines ?? [], batch?.source_type), [batch]);
  const duplicateCounts = batch?.lines.reduce<Record<string, number>>((acc, line) => {
    acc[line.duplicate_status] = (acc[line.duplicate_status] ?? 0) + 1;
    return acc;
  }, {}) ?? {};
  const visibleDuplicateCounts = {
    previously_parsed: batch?.source_type === "bbva_account_xls" ? 0 : duplicateCounts.previously_parsed ?? 0,
    already_committed: duplicateCounts.already_committed ?? 0
  };
  return (
    <section className="stack">
      <div className="import-choice-grid">
      <div className="panel import-drop">
        <div>
          <h2>Importar resumen Tarjeta BBVA</h2>
          <p>Subi un PDF para revisar cada linea antes de convertirla en gasto.</p>
        </div>
        <label className="primary file-button">
          <Upload size={16} /> Elegir PDF
          <input
            type="file"
            accept="application/pdf"
            aria-label="Elegir resumen de tarjeta PDF"
            onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              if (file) uploadCard.mutate(file);
              event.currentTarget.value = "";
            }}
          />
        </label>
      </div>
      <div className="panel import-drop">
        <div>
          <h2>Importar movimientos de cuenta</h2>
          <p>Subi un XLS para separar debitos, transferencias, extracciones, ingresos y pagos de tarjeta.</p>
        </div>
        <label className="primary file-button">
          <Upload size={16} /> Elegir XLS
          <input
            type="file"
            accept=".xls,application/vnd.ms-excel"
            aria-label="Elegir movimientos de cuenta XLS"
            onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              if (file) uploadAccount.mutate(file);
              event.currentTarget.value = "";
            }}
          />
        </label>
      </div>
      </div>
      {!!pendingImports.data?.length && (
        <div className="panel">
          <h2>Importaciones no finalizadas</h2>
          {deleteImport.isError && <div className="warning">No se pudo borrar la importacion. Si ya fue convertida, no se elimina para proteger los gastos creados.</div>}
          <div className="stack">
            {pendingImports.data.map((item) => (
              <div className="list-row pending-import-row" data-testid={`pending-import-${item.id}`} key={item.id}>
                <span>{item.filename} - {item.created_at ? new Date(item.created_at).toLocaleString("es-AR") : "Sin fecha"} - {item.lines.length} lineas</span>
                <div className="row-actions">
                  <button className="primary" onClick={() => loadBatch(item)}>Continuar</button>
                  <button
                    className="icon-button danger"
                    title="Borrar importacion"
                    aria-label="Borrar importacion"
                    disabled={deleteImport.isPending}
                    onClick={() => {
                      if (window.confirm(`Borrar la importacion "${item.filename}"? Esta accion elimina las lineas parseadas no convertidas.`)) {
                        deleteImport.mutate(item.id);
                      }
                    }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {(uploadCard.isPending || uploadAccount.isPending) && <div className="panel">Parseando resumen...</div>}
      {batch && (
        <div className="panel table-panel" data-testid={`active-import-${batch.id}`}>
          {(visibleDuplicateCounts.previously_parsed || visibleDuplicateCounts.already_committed) && (
            <div className="warning">
              {visibleDuplicateCounts.previously_parsed ? `${visibleDuplicateCounts.previously_parsed} lineas ya habian sido parseadas pero no convertidas. ` : ""}
              {visibleDuplicateCounts.already_committed ? `${visibleDuplicateCounts.already_committed} lineas ya fueron convertidas a consumos y quedan desmarcadas para evitar duplicarlas.` : ""}
            </div>
          )}
          <div className="table-heading">
            <div>
              <h2>Lineas detectadas</h2>
              {batch.source_type !== "bbva_account_xls" && (
                <div className="import-totals" aria-label="Totales importados">
                  <>
                    <span>Total ARS <strong>{money(Math.abs(totals.total.ARS ?? 0), "ARS")}</strong></span>
                    <span>Total USD <strong>{money(Math.abs(totals.total.USD ?? 0), "USD")}</strong></span>
                  </>
                </div>
              )}
              <div className={reviewCount ? "review-counter warning-status" : "review-counter"}>
                <AlertTriangle size={16} />
                Consumos a revisar: <strong>{reviewCount}</strong>
              </div>
            </div>
            <div className="toolbar compact">
              {batch.source_type !== "bbva_account_xls" && (
                <label className="statement-period-control">
                  <span>Mes del resumen</span>
                  <input
                    type="month"
                    value={statementPeriod}
                    onChange={(event) => setStatementPeriod(event.target.value)}
                    onBlur={() => {
                      if (statementPeriod !== (batch.statement_period ?? "")) {
                        updateBatch.mutate({ batchId: batch.id, nextStatementPeriod: statementPeriod });
                      }
                    }}
                    aria-label="Mes del resumen de tarjeta"
                  />
                </label>
              )}
              <select value={paidByUserId} onChange={(e) => setPaidByUserId(e.target.value)} aria-label="Pagador del resumen">
                {users.map((u) => <option value={u.id} key={u.id}>{u.display_name}</option>)}
              </select>
              <button className="primary" disabled={!selected.length || commit.isPending || updateBatch.isPending} onClick={() => commit.mutate()}>
                Procesar {selected.length} lineas
              </button>
            </div>
          </div>
          <table>
            <thead><tr><th></th><th>Fecha</th><th>Descripcion</th><th>Tipo</th><th>Reintegro</th><th>Categoria</th><th>Subcategoria</th><th>Recurrente</th><th>Nota</th><th>Importe</th><th>Estado</th></tr></thead>
            <tbody>
              {reviewLines.map((line, index) => {
                const selectedCategory = categories.find((category) => category.id === categoryByLine[line.id]);
                const isIgnoredCardPayment = isIgnoredImportLine(line);
                const isLineDisabled = isIgnoredCardPayment || line.status !== "pending";
                const hidePreviouslyParsed = batch.source_type === "bbva_account_xls" && line.duplicate_status === "previously_parsed";
                const showDuplicateWarning = line.duplicate_status !== "new" && !hidePreviouslyParsed;
                const showMonthSeparator = batch.source_type === "bbva_account_xls" && (index === 0 || importLinePeriod(reviewLines[index - 1]) !== importLinePeriod(line));
                const showHolderSeparator = batch.source_type !== "bbva_account_xls" && (index === 0 || cardholderKey(reviewLines[index - 1]) !== cardholderKey(line));
                const showCurrencySeparator = batch.source_type !== "bbva_account_xls" && (index === 0 || reviewLines[index - 1].currency !== line.currency || cardholderKey(reviewLines[index - 1]) !== cardholderKey(line));
                const holderLines = batch.lines.filter((item) => cardholderKey(item) === cardholderKey(line));
                const holderTotals = importTotals(holderLines, selected, batch.source_type);
                const holderSelectedCount = holderLines.filter((item) => selected.includes(item.id) && !isIgnoredImportLine(item)).length;
                const holderKey = cardholderKey(line);
                return (
                  <Fragment key={line.id}>
                    {showHolderSeparator && (
                      <tr className="person-separator">
                        <td colSpan={11}>
                          <div className="person-separator-content">
                            <div>
                              <strong>{cardholderLabel(line)}</strong>
                              <div className="import-totals month-totals">
                                <span>Total ARS <strong>{money(Math.abs(holderTotals.total.ARS ?? 0), "ARS")}</strong></span>
                                <span>Total USD <strong>{money(Math.abs(holderTotals.total.USD ?? 0), "USD")}</strong></span>
                              </div>
                            </div>
                            <div className="row-actions">
                              <select
                                className="person-action-control"
                                value={paidByByHolder[holderKey] ?? paidByUserId}
                                onChange={(event) => setPaidByByHolder((current) => ({ ...current, [holderKey]: event.target.value }))}
                                aria-label={`Pagador ${cardholderLabel(line)}`}
                              >
                                {users.map((u) => <option value={u.id} key={u.id}>{u.display_name}</option>)}
                              </select>
                              <button
                                className="person-action-control"
                                title="Copiar consumos"
                                aria-label={`Copiar consumos ${cardholderLabel(line)}`}
                                disabled={!holderSelectedCount}
                                onClick={async () => {
                                  await copyTextToClipboard(importShareText(holderLines, selected, batch.source_type));
                                  setCopiedHolder(holderKey);
                                  window.setTimeout(() => setCopiedHolder((current) => current === holderKey ? null : current), 1800);
                                }}
                                type="button"
                              >
                                <Copy size={16} />
                                Copiar
                              </button>
                              {copiedHolder === holderKey && <span className="copy-feedback">Copiado</span>}
                              <button
                                className="person-action-control"
                                onClick={() => setSelected((current) => Array.from(new Set([...current, ...holderLines.filter((item) => item.status === "pending" && !isIgnoredImportLine(item)).map((item) => item.id)])))}
                                type="button"
                              >
                                Seleccionar persona
                              </button>
                              <button
                                className="person-action-control danger"
                                onClick={() => setSelected((current) => current.filter((id) => !holderLines.some((item) => item.id === id)))}
                                type="button"
                              >
                                Omitir persona
                              </button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                    {showMonthSeparator && (
                      <tr className="month-separator">
                        <td colSpan={11}>
                          <strong>{monthLabel(importLinePeriod(line))}</strong>
                          <ImportMonthTotals lines={batch.lines} selected={selected} period={importLinePeriod(line)} reimbursementByLine={reimbursementByLine} />
                        </td>
                      </tr>
                    )}
                    {showCurrencySeparator && (
                      <tr className={`currency-separator ${line.currency.toLowerCase()}`}>
                        <td colSpan={11}>Consumos en {line.currency}</td>
                      </tr>
                    )}
                    <tr
                      key={line.id}
                      data-testid={`import-line-${line.id}`}
                      className={isLineDisabled ? "ignored-row" : !categoryByLine[line.id] ? "needs-review-row" : undefined}
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={selected.includes(line.id)}
                          disabled={isLineDisabled}
                          title={isLineDisabled ? ignoredImportReason(line) : undefined}
                          onChange={(event) => {
                            setSelected((current) =>
                              event.target.checked ? [...current, line.id] : current.filter((id) => id !== line.id)
                            );
                          }}
                        />
                      </td>
                      <td>{line.date}</td>
                      <td>{line.description}</td>
                      <td>{kindLabel(line.kind)}</td>
                      <td>
                        {batch.source_type === "bbva_account_xls" && line.kind === "income" ? (
                          <input
                            type="checkbox"
                            checked={!!reimbursementByLine[line.id]}
                            disabled={isLineDisabled}
                            onChange={(event) => setReimbursementByLine((current) => ({ ...current, [line.id]: event.target.checked }))}
                            aria-label={`Marcar reintegro ${line.description}`}
                          />
                        ) : (
                          <span className="muted">-</span>
                        )}
                      </td>
                      <td>
                        <select
                          value={categoryByLine[line.id] ?? ""}
                          disabled={isLineDisabled}
                          onChange={(event) => {
                            const nextCategoryId = event.target.value ? Number(event.target.value) : null;
                            setCategoryByLine((current) => ({
                              ...current,
                              [line.id]: nextCategoryId
                            }));
                            setSubcategoryByLine((current) => ({
                              ...current,
                              [line.id]: null
                            }));
                            const nextCategory = categories.find((category) => category.id === nextCategoryId);
                            if (nextCategory?.name === "Suscripciones" || nextCategory?.name === "Servicios") {
                              setRecurringByLine((current) => ({ ...current, [line.id]: true }));
                            }
                          }}
                          aria-label={`Categoria ${line.description}`}
                        >
                          <option value="">Revisar</option>
                          {categories.map((category) => <option value={category.id} key={category.id}>{category.name}</option>)}
                        </select>
                      </td>
                      <td>
                        <select
                          value={subcategoryByLine[line.id] ?? ""}
                          disabled={isLineDisabled || !(selectedCategory?.subcategories?.length)}
                          onChange={(event) =>
                            setSubcategoryByLine((current) => ({
                              ...current,
                              [line.id]: event.target.value ? Number(event.target.value) : null
                            }))
                          }
                          aria-label={`Subcategoria ${line.description}`}
                        >
                          <option value="">Sin subcategoria</option>
                          {(selectedCategory?.subcategories ?? []).map((subcategory) => <option value={subcategory.id} key={subcategory.id}>{subcategory.name}</option>)}
                        </select>
                      </td>
                      <td>
                        <input
                          type="checkbox"
                          checked={!!recurringByLine[line.id]}
                          disabled={isLineDisabled}
                          onChange={(event) => setRecurringByLine((current) => ({ ...current, [line.id]: event.target.checked }))}
                          aria-label={`Recurrente ${line.description}`}
                        />
                      </td>
                      <td>
                        <input
                          className="table-input"
                          value={notesByLine[line.id] ?? ""}
                          maxLength={500}
                          disabled={isLineDisabled}
                          placeholder="Nota"
                          onChange={(event) => setNotesByLine((current) => ({ ...current, [line.id]: event.target.value }))}
                          aria-label={`Nota ${line.description}`}
                        />
                      </td>
                      <td>{money(line.original_amount, line.currency)}</td>
                      <td>
                        <span className={isLineDisabled || showDuplicateWarning || !categoryByLine[line.id] ? "status warning-status" : "status"}>
                          {!isLineDisabled && !categoryByLine[line.id] ? <AlertTriangle size={14} /> : null}
                          {!isLineDisabled && !categoryByLine[line.id] ? "Revisar categoria" : isLineDisabled ? ignoredImportReason(line) : hidePreviouslyParsed ? "Lista" : duplicateLabel(line.duplicate_status)}
                        </span>
                      </td>
                    </tr>
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function CashWallet({ users, homeId }: { users: User[]; homeId: number }) {
  const cash = useQuery({ queryKey: ["cash", homeId], queryFn: () => api.cashWallet(homeId) });
  const [adjustUserId, setAdjustUserId] = useState(String(users[0]?.id ?? 1));
  const [adjustCurrency, setAdjustCurrency] = useState<Currency>("ARS");
  const [targetBalance, setTargetBalance] = useState("");
  const queryClient = useQueryClient();
  const adjust = useMutation({
    mutationFn: () => api.adjustCashWallet(homeId, {
      user_id: Number(adjustUserId),
      currency: adjustCurrency,
      target_balance: targetBalance,
      description: "Ajuste manual de efectivo"
    }),
    onSuccess: () => {
      setTargetBalance("");
      queryClient.invalidateQueries({ queryKey: ["cash", homeId] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    }
  });
  return (
    <section className="grid two">
      <div className="metric">
        <span>Efectivo sin asignar</span>
        <strong>{money(cash.data?.balances.reduce((sum, item) => sum + Number(item.balance), 0) ?? 0)}</strong>
        <small>Retiros menos gastos manuales en efectivo</small>
      </div>
      <form
        className="panel form-panel"
        onSubmit={(event) => {
          event.preventDefault();
          if (targetBalance.trim()) adjust.mutate();
        }}
      >
        <h2>Ajustar efectivo</h2>
        <select value={adjustUserId} onChange={(event) => setAdjustUserId(event.target.value)} aria-label="Usuario efectivo">
          {users.map((user) => <option value={user.id} key={user.id}>{user.display_name}</option>)}
        </select>
        <select value={adjustCurrency} onChange={(event) => setAdjustCurrency(event.target.value as Currency)} aria-label="Moneda efectivo">
          <option value="ARS">ARS</option>
          <option value="USD">USD</option>
        </select>
        <input value={targetBalance} onChange={(event) => setTargetBalance(event.target.value)} placeholder="Saldo correcto" aria-label="Saldo correcto" inputMode="decimal" />
        <button className="primary" disabled={!targetBalance.trim() || adjust.isPending}>Guardar ajuste</button>
      </form>
      <div className="panel">
        <h2>Ultimos movimientos</h2>
        <div className="stack">
          {(cash.data?.entries ?? []).map((entry) => (
            <div className="list-row" key={entry.id}>
              <span>{entry.description} - {users.find((u) => u.id === entry.user_id)?.display_name ?? "Usuario"}</span>
              <strong>{money(entry.amount, entry.currency)}</strong>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function HistoryPanel({ users, homeId }: { users: User[]; homeId: number }) {
  const [tab, setTab] = useState<"log" | "imports">("log");
  const history = useQuery({ queryKey: ["history", homeId], queryFn: () => api.history(homeId) });
  const imports = useQuery({ queryKey: ["imports", homeId, "all"], queryFn: () => api.imports(homeId) });
  const importSummary = useMemo(() => buildImportCoverage(imports.data ?? [], users), [imports.data, users]);
  return (
    <section className="panel table-panel">
      <div className="tabs">
        <button className={tab === "log" ? "active" : undefined} onClick={() => setTab("log")}>Log</button>
        <button className={tab === "imports" ? "active" : undefined} onClick={() => setTab("imports")}>Resumen de importaciones</button>
      </div>
      {tab === "log" ? (
        <>
          <h2>Actividad reciente</h2>
          <table>
            <thead><tr><th>Fecha</th><th>Usuario</th><th>Operacion</th><th>Detalle</th><th>Monto</th></tr></thead>
            <tbody>
              {(history.data ?? []).map((item) => (
                <tr key={item.id}>
                  <td>{new Date(item.created_at).toLocaleString("es-AR")}</td>
                  <td>{users.find((user) => user.id === item.actor_user_id)?.display_name ?? "Sistema"}</td>
                  <td>{actionLabel(item.action)}</td>
                  <td>{item.description}</td>
                  <td>{item.amount ? money(item.amount, item.currency ?? "ARS") : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <div className="stack">
          {importSummary.years.map((year) => (
            <div className="import-coverage" key={year}>
              <h2>Cargas {year}</h2>
              <table>
                <thead>
                  <tr>
                    <th>Tipo</th>
                    <th>Subio</th>
                    <th>Pago</th>
                    {Array.from({ length: 12 }, (_, index) => <th key={index}>{axisMonthLabel(`${year}-${String(index + 1).padStart(2, "0")}`)}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {importSummary.rows.map((row) => (
                    <tr key={row.key}>
                      <td>{row.source}</td>
                      <td>{users.find((user) => user.id === row.uploadedByUserId)?.display_name ?? "Usuario"}</td>
                      <td>{row.paidByUserId ? users.find((user) => user.id === row.paidByUserId)?.display_name ?? "Usuario" : "Sin procesar"}</td>
                      {Array.from({ length: 12 }, (_, index) => {
                        const period = `${year}-${String(index + 1).padStart(2, "0")}`;
                        const value = row.months[period];
                        return (
                          <td key={period}>
                            {value ? (
                              <div className="import-coverage-cell">
                                <span className={value.status === "Procesado" ? "status" : "status warning-status"}>{value.status}</span>
                                {value.fxRate ? <small className="muted">Blue {money(value.fxRate, "ARS")}</small> : null}
                              </div>
                            ) : <span className="muted">-</span>}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          {!importSummary.years.length && <p className="muted">Todavia no hay importaciones cargadas.</p>}
        </div>
      )}
    </section>
  );
}

function ReceiptsLab({ categories, expenses, homeId }: { categories: Category[]; expenses: Expense[]; homeId: number }) {
  const [receiptTab, setReceiptTab] = useState<"review" | "associate">("review");
  const [expenseId, setExpenseId] = useState("");
  const [activeReceiptId, setActiveReceiptId] = useState<number | null>(null);
  const [pendingUpload, setPendingUpload] = useState<{ filename: string; status: "processing" | "cancelled" | "timeout" | "error" } | null>(null);
  const [editableItems, setEditableItems] = useState<Array<ReceiptItem & { accepted: boolean }>>([]);
  const [receiptCategoryId, setReceiptCategoryId] = useState<number | null>(null);
  const [associationExpenseIds, setAssociationExpenseIds] = useState<Record<number, string>>({});
  const [associationCategoryIds, setAssociationCategoryIds] = useState<Record<number, string>>({});
  const [reviewSaved, setReviewSaved] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const cancelledRef = useRef(false);
  const queryClient = useQueryClient();
  const receipts = useQuery({ queryKey: ["receipts", homeId], queryFn: () => api.receipts(homeId) });
  const receiptRows = receipts.data ?? [];
  const reviewReceipts = receiptRows.filter((receipt) => !["reviewed", "associated"].includes(receipt.status));
  const associationReceipts = receiptRows.filter((receipt) => receipt.status === "reviewed" && !receipt.expense_id);
  const pendingAssociationCount = associationReceipts.length;
  const deleteReceipt = useMutation({
    mutationFn: (receiptId: number) => api.deleteReceipt(homeId, receiptId),
    onSuccess: (_, receiptId) => {
      if (activeReceiptId === receiptId) setActiveReceiptId(null);
      queryClient.invalidateQueries({ queryKey: ["receipts", homeId] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    }
  });
  const saveReview = useMutation({
    mutationFn: () => api.updateReceiptItems(homeId, activeReceipt!.id, receiptCategoryId, editableItems.map((item) => ({
      id: item.id,
      description: item.description,
      subcategory_id: item.subcategory_id,
      suggested_subcategory_name: item.suggested_subcategory_name,
      quantity: item.quantity,
      unit_price: item.unit_price,
      total_amount: item.total_amount,
      accepted: item.accepted
    }))),
    onSuccess: (updatedReceipt) => {
      setReviewSaved(true);
      setReceiptTab("associate");
      setActiveReceiptId(null);
      queryClient.setQueryData<ReceiptImport[]>(["receipts", homeId], (current) =>
        current?.map((receipt) => receipt.id === updatedReceipt.id ? updatedReceipt : receipt) ?? [updatedReceipt]
      );
      queryClient.invalidateQueries({ queryKey: ["receipts", homeId] });
      queryClient.invalidateQueries({ queryKey: ["categories", homeId] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    }
  });
  const associateReceipt = useMutation({
    mutationFn: ({ receiptId, nextExpenseId, categoryId }: { receiptId: number; nextExpenseId: number; categoryId: number | null }) =>
      api.associateReceipt(homeId, receiptId, { expense_id: nextExpenseId, category_id: categoryId }),
    onSuccess: (updatedReceipt) => {
      queryClient.setQueryData<ReceiptImport[]>(["receipts", homeId], (current) =>
        current?.map((receipt) => receipt.id === updatedReceipt.id ? updatedReceipt : receipt) ?? [updatedReceipt]
      );
      queryClient.invalidateQueries({ queryKey: ["receipts", homeId] });
      queryClient.invalidateQueries({ queryKey: ["expenses", homeId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", homeId] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    }
  });
  const activeReceipt = reviewReceipts.find((receipt) => receipt.id === activeReceiptId) ?? reviewReceipts[0] ?? null;
  const isUploading = pendingUpload?.status === "processing";
  const selectedCategory = categories.find((category) => category.id === receiptCategoryId) ?? null;
  useEffect(() => {
    if (!activeReceipt) {
      setEditableItems([]);
      setReceiptCategoryId(null);
      setReviewSaved(false);
      return;
    }
    setEditableItems(activeReceipt.items.map((item) => ({ ...item, accepted: item.status !== "rejected" })));
    setReceiptCategoryId(activeReceipt.category_id ?? categories[0]?.id ?? null);
    setReviewSaved(activeReceipt.status === "reviewed");
  }, [activeReceipt?.id, activeReceipt?.items.length, activeReceipt?.status, activeReceipt?.category_id, categories.length]);
  const clearUploadTimers = () => {
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
    timeoutRef.current = null;
  };
  const cancelUpload = () => {
    cancelledRef.current = true;
    abortRef.current?.abort();
    clearUploadTimers();
    abortRef.current = null;
    setPendingUpload((current) => current ? { ...current, status: "cancelled" } : null);
  };
  const uploadFiles = async (files: File[]) => {
    if (!files.length) return;
    cancelledRef.current = false;
    const controller = new AbortController();
    abortRef.current = controller;
    const filename = files.length === 1 ? files[0].name : `${files.length} archivos`;
    setPendingUpload({ filename, status: "processing" });
    timeoutRef.current = window.setTimeout(() => {
      controller.abort();
      setPendingUpload({ filename, status: "timeout" });
    }, 120000);
    try {
      const receipt = await api.uploadReceipt(homeId, files, expenseId ? Number(expenseId) : undefined, controller.signal);
      clearUploadTimers();
      abortRef.current = null;
      setPendingUpload(null);
      setActiveReceiptId(receipt.id);
      queryClient.invalidateQueries({ queryKey: ["receipts", homeId] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    } catch {
      clearUploadTimers();
      abortRef.current = null;
      setPendingUpload((current) => current ? { ...current, status: cancelledRef.current ? "cancelled" : current.status === "timeout" ? "timeout" : "error" } : null);
    }
  };
  const updateItem = (id: number, patch: Partial<ReceiptItem & { accepted: boolean }>) => {
    setReviewSaved(false);
    setEditableItems((items) => items.map((item) => item.id === id ? { ...item, ...patch } : item));
  };
  const acceptedTotal = editableItems.filter((item) => item.accepted).reduce((sum, item) => sum + Number(item.total_amount || 0), 0);
  const subcategoryOptions = selectedCategory?.subcategories ?? [];
  const setItemSubcategory = (item: ReceiptItem & { accepted: boolean }, value: string) => {
    if (!value) {
      updateItem(item.id, { subcategory_id: null, suggested_subcategory_name: null });
    } else if (value.startsWith("id:")) {
      updateItem(item.id, { subcategory_id: Number(value.slice(3)), suggested_subcategory_name: null });
    } else if (value.startsWith("new:")) {
      updateItem(item.id, { subcategory_id: null, suggested_subcategory_name: value.slice(4) });
    }
  };
  const subcategoryValue = (item: ReceiptItem) => {
    if (item.subcategory_id) return `id:${item.subcategory_id}`;
    if (item.suggested_subcategory_name) return `new:${item.suggested_subcategory_name}`;
    return "";
  };
  return (
    <section className="stack">
      <div className="tabs receipt-tabs">
        <button className={receiptTab === "review" ? "active" : ""} onClick={() => setReceiptTab("review")}>Carga y revision</button>
        <button className={receiptTab === "associate" ? "active" : ""} onClick={() => setReceiptTab("associate")}>
          Asociacion
          {pendingAssociationCount > 0 && <span className="badge warning-badge"><AlertTriangle size={14} /> {pendingAssociationCount}</span>}
        </button>
      </div>
      {receiptTab === "review" && (
      <>
      <div className="panel receipt-upload-panel">
        <div>
          <h2>Ticket experimental</h2>
          <p className="muted">Subi una foto, video o texto OCR. El ticket se revisa primero y despues se asocia a un gasto existente.</p>
        </div>
        <div className="receipt-upload-controls">
          <select value={expenseId} onChange={(event) => setExpenseId(event.target.value)} aria-label="Gasto asociado al ticket" disabled={isUploading}>
            <option value="">Sin asociar todavia</option>
            {expenses.slice(0, 80).map((expense) => (
              <option value={expense.id} key={expense.id}>{expense.date} - {expense.description} - {money(expense.original_amount, expense.currency)}</option>
            ))}
          </select>
          <label className={isUploading ? "primary file-button disabled" : "primary file-button"}>
            <Upload size={16} /> Subir ticket
            <input
              type="file"
              accept="image/*,video/*,.txt"
              aria-label="Subir ticket"
              disabled={isUploading}
              multiple
              onChange={(event) => {
                const files = Array.from(event.currentTarget.files ?? []);
                if (files.length) void uploadFiles(files);
                event.currentTarget.value = "";
              }}
            />
          </label>
          {isUploading && <button className="icon-button danger" title="Cancelar carga" onClick={cancelUpload}><X size={16} /></button>}
        </div>
        <div className="receipt-loads">
          {pendingUpload && (
            <div className="receipt-load-row pending">
              {pendingUpload.status === "processing" ? <i className="spinner" /> : <AlertTriangle size={16} />}
              <span>{pendingUpload.filename} - {receiptUploadStatusLabel(pendingUpload.status)}</span>
              {pendingUpload.status === "processing" ? <button className="text-button" onClick={cancelUpload}>Cancelar</button> : <button className="text-button" onClick={() => setPendingUpload(null)}>Ocultar</button>}
            </div>
          )}
          {reviewReceipts.map((receipt) => (
            <div className={activeReceipt?.id === receipt.id ? "receipt-load-row active" : "receipt-load-row"} key={receipt.id}>
              <button className="text-button" onClick={() => setActiveReceiptId(receipt.id)}>{receipt.filename}</button>
              <span>{receiptStatusLabel(receipt.status)} - {receipt.items.length} items</span>
              <strong>{receipt.parsed_total ? money(receipt.parsed_total) : receipt.created_at ? new Date(receipt.created_at).toLocaleDateString("es-AR") : ""}</strong>
              <button
                className="icon-button danger"
                title="Borrar ticket"
                aria-label={`Borrar ticket ${receipt.filename}`}
                disabled={deleteReceipt.isPending}
                onClick={() => {
                  if (window.confirm(`Borrar el ticket "${receipt.filename}"?`)) deleteReceipt.mutate(receipt.id);
                }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
          {!reviewReceipts.length && !pendingUpload && <p className="muted">No hay tickets pendientes de revision.</p>}
        </div>
      </div>
      <div className="panel table-panel receipt-review-panel">
        <div className="table-heading">
          <div>
            <h2>Items del ticket</h2>
            <p className="muted">{activeReceipt ? `${activeReceipt.filename} - ${editableItems.length} items detectados` : "Selecciona o carga un ticket para revisar sus items."}</p>
          </div>
          {activeReceipt && (
            <div className="toolbar compact">
              {reviewSaved && <span className="status">Revision guardada</span>}
              <label className="inline-label">
                <span>Categoria del ticket</span>
                <select
                  value={receiptCategoryId ?? ""}
                  aria-label="Categoria del ticket"
                  onChange={(event) => {
                    setReviewSaved(false);
                    setReceiptCategoryId(event.target.value ? Number(event.target.value) : null);
                    setEditableItems((items) => items.map((item) => ({ ...item, subcategory_id: null })));
                  }}
                >
                  <option value="">Sin categoria</option>
                  {categories.map((category) => <option value={category.id} key={category.id}>{category.name}</option>)}
                </select>
              </label>
              <span className="status">Total seleccionado {money(acceptedTotal)}</span>
              <button className="primary" disabled={!editableItems.length || saveReview.isPending} onClick={() => saveReview.mutate()}>
                <Save size={16} /> Guardar revision
              </button>
            </div>
          )}
        </div>
        {isUploading ? (
          <div className="receipt-processing-large" role="status" aria-label="Procesando ticket">
            <i className="spinner large" />
            <strong>Analizando ticket</strong>
            <span>{pendingUpload?.filename ?? "Ticket"} puede usar IA o OCR local y tardar hasta 2 minutos.</span>
            <button className="text-button" onClick={cancelUpload}>Cancelar</button>
          </div>
        ) : activeReceipt && editableItems.length ? (
          <table>
            <thead>
              <tr><th></th><th>Descripcion</th><th>Subcategoria</th><th>Cantidad</th><th>Precio unitario</th><th>Total</th><th>Estado</th></tr>
            </thead>
            <tbody>
              {editableItems.map((item) => (
                <tr key={item.id} className={!item.accepted ? "ignored-row" : undefined}>
                  <td>
                    <input
                      type="checkbox"
                      checked={item.accepted}
                      aria-label={`Aceptar item ${item.description}`}
                      onChange={(event) => updateItem(item.id, { accepted: event.target.checked })}
                    />
                  </td>
                  <td>
                    <input value={item.description} onChange={(event) => updateItem(item.id, { description: event.target.value })} aria-label={`Descripcion item ${item.id}`} />
                  </td>
                  <td>
                    <select value={subcategoryValue(item)} onChange={(event) => setItemSubcategory(item, event.target.value)} aria-label={`Subcategoria item ${item.id}`}>
                      <option value="">Sin subcategoria</option>
                      {subcategoryOptions.map((subcategory) => <option value={`id:${subcategory.id}`} key={subcategory.id}>{subcategory.name}</option>)}
                      {item.suggested_subcategory_name && !subcategoryOptions.some((subcategory) => subcategory.name === item.suggested_subcategory_name) && (
                        <option value={`new:${item.suggested_subcategory_name}`}>{item.suggested_subcategory_name} (nueva)</option>
                      )}
                    </select>
                  </td>
                  <td>
                    <input value={item.quantity ?? ""} onChange={(event) => updateItem(item.id, { quantity: event.target.value || null })} aria-label={`Cantidad item ${item.id}`} inputMode="decimal" />
                  </td>
                  <td>
                    <input value={item.unit_price ?? ""} onChange={(event) => updateItem(item.id, { unit_price: event.target.value || null })} aria-label={`Precio item ${item.id}`} inputMode="decimal" />
                  </td>
                  <td>
                    <input value={item.total_amount} onChange={(event) => updateItem(item.id, { total_amount: event.target.value })} aria-label={`Total item ${item.id}`} inputMode="decimal" />
                  </td>
                  <td><span className={item.accepted ? "status" : "status warning-status"}>{item.accepted ? "Aceptado" : "Ignorado"}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : activeReceipt ? (
          <div className="warning">Este ticket no tiene items detectados. Podés borrarlo y volver a cargar una foto/video con mejor foco o luz.</div>
        ) : null}
      </div>
      </>
      )}
      {receiptTab === "associate" && (
        <div className="panel table-panel receipt-review-panel">
          <div className="table-heading">
            <div>
              <h2>Asociacion de tickets a gastos</h2>
              <p className="muted">Los tickets revisados quedan aca hasta asociarlos al gasto de tarjeta, debito o efectivo correspondiente.</p>
            </div>
            {pendingAssociationCount > 0 && <span className="status warning-status"><AlertTriangle size={14} /> {pendingAssociationCount} pendientes</span>}
          </div>
          {associationReceipts.length ? (
            <table>
              <thead>
                <tr><th>Ticket</th><th>Total</th><th>Categoria</th><th>Gasto asociado</th><th>Acciones</th></tr>
              </thead>
              <tbody>
                {associationReceipts.map((receipt) => {
                  const selectedExpenseId = associationExpenseIds[receipt.id] ?? "";
                  const selectedCategoryId = associationCategoryIds[receipt.id] ?? String(receipt.category_id ?? "");
                  return (
                    <tr key={receipt.id}>
                      <td>
                        <strong>{receipt.filename}</strong>
                        <div className="muted">{receipt.items.filter((item) => item.status !== "rejected").length} items aceptados</div>
                      </td>
                      <td>{receipt.parsed_total ? money(receipt.parsed_total) : "-"}</td>
                      <td>
                        <select
                          value={selectedCategoryId}
                          aria-label={`Categoria para ticket ${receipt.filename}`}
                          onChange={(event) => setAssociationCategoryIds((current) => ({ ...current, [receipt.id]: event.target.value }))}
                        >
                          <option value="">Sin categoria</option>
                          {categories.map((category) => <option value={category.id} key={category.id}>{category.name}</option>)}
                        </select>
                      </td>
                      <td>
                        <select
                          value={selectedExpenseId}
                          aria-label={`Gasto para ticket ${receipt.filename}`}
                          onChange={(event) => setAssociationExpenseIds((current) => ({ ...current, [receipt.id]: event.target.value }))}
                        >
                          <option value="">Seleccionar gasto</option>
                          {expenses.slice(0, 160).map((expense) => (
                            <option value={expense.id} key={expense.id}>{expense.date} - {expense.description} - {money(expense.original_amount, expense.currency)}</option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <div className="row-actions">
                          <button
                            className="primary"
                            disabled={!selectedExpenseId || associateReceipt.isPending}
                            onClick={() => associateReceipt.mutate({ receiptId: receipt.id, nextExpenseId: Number(selectedExpenseId), categoryId: selectedCategoryId ? Number(selectedCategoryId) : null })}
                          >
                            Asociar
                          </button>
                          <button
                            className="icon-button danger"
                            title="Borrar ticket"
                            aria-label={`Borrar ticket ${receipt.filename}`}
                            disabled={deleteReceipt.isPending}
                            onClick={() => {
                              if (window.confirm(`Borrar el ticket "${receipt.filename}"?`)) deleteReceipt.mutate(receipt.id);
                            }}
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <p className="muted">No hay tickets pendientes de asociacion.</p>
          )}
        </div>
      )}
    </section>
  );
}

function SettingsPanel({ categories, users, homeId }: { categories: Category[]; users: User[]; homeId: number }) {
  const [name, setName] = useState("");
  const [color, setColor] = useState("#38bdf8");
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [editUserName, setEditUserName] = useState("");
  const [editUserEmail, setEditUserEmail] = useState("");
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editColor, setEditColor] = useState("#38bdf8");
  const [selectedSubcategoryCategoryId, setSelectedSubcategoryCategoryId] = useState<number | null>(categories[0]?.id ?? null);
  const [subcategoryName, setSubcategoryName] = useState("");
  const [editingSubcategoryId, setEditingSubcategoryId] = useState<number | null>(null);
  const [editSubcategoryName, setEditSubcategoryName] = useState("");
  const queryClient = useQueryClient();
  const selectedSubcategoryCategory = categories.find((category) => category.id === selectedSubcategoryCategoryId) ?? categories[0];
  const updateMember = useMutation({
    mutationFn: ({ id, nextName, nextEmail }: { id: number; nextName: string; nextEmail: string }) =>
      api.updateMember(homeId, id, { display_name: nextName, email: nextEmail }),
    onSuccess: () => {
      setEditingUserId(null);
      setEditUserName("");
      setEditUserEmail("");
      queryClient.invalidateQueries({ queryKey: ["members", homeId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", homeId] });
      queryClient.invalidateQueries({ queryKey: ["expenses", homeId] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    }
  });
  const deleteMember = useMutation({
    mutationFn: (id: number) => api.deleteMember(homeId, id),
    onSuccess: (_, deletedId) => {
      if (editingUserId === deletedId) {
        setEditingUserId(null);
        setEditUserName("");
        setEditUserEmail("");
      }
      queryClient.invalidateQueries({ queryKey: ["members", homeId] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    }
  });
  const createCategory = useMutation({
    mutationFn: () => api.createCategory(homeId, { name, color, icon: "tag" }),
    onSuccess: () => {
      setName("");
      queryClient.invalidateQueries({ queryKey: ["categories", homeId] });
    }
  });
  const updateCategory = useMutation({
    mutationFn: ({ id, nextName, nextColor }: { id: number; nextName: string; nextColor: string }) =>
      api.updateCategory(homeId, id, { name: nextName, color: nextColor, icon: "tag" }),
    onSuccess: () => {
      setEditingCategoryId(null);
      queryClient.invalidateQueries({ queryKey: ["categories", homeId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", homeId] });
      queryClient.invalidateQueries({ queryKey: ["expenses", homeId] });
    }
  });
  const loadDefaultCategories = useMutation({
    mutationFn: () => api.loadDefaultCategories(homeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["categories", homeId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", homeId] });
      queryClient.invalidateQueries({ queryKey: ["expenses", homeId] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    }
  });
  const createSubcategory = useMutation({
    mutationFn: () => api.createSubcategory(homeId, { category_id: selectedSubcategoryCategory!.id, name: subcategoryName.trim() }),
    onSuccess: () => {
      setSubcategoryName("");
      queryClient.invalidateQueries({ queryKey: ["categories", homeId] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    }
  });
  const updateSubcategory = useMutation({
    mutationFn: ({ id, nextName }: { id: number; nextName: string }) => api.updateSubcategory(homeId, id, { name: nextName }),
    onSuccess: () => {
      setEditingSubcategoryId(null);
      setEditSubcategoryName("");
      queryClient.invalidateQueries({ queryKey: ["categories", homeId] });
      queryClient.invalidateQueries({ queryKey: ["expenses", homeId] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    }
  });
  const deleteSubcategory = useMutation({
    mutationFn: (id: number) => api.deleteSubcategory(homeId, id),
    onSuccess: (_, deletedId) => {
      if (editingSubcategoryId === deletedId) {
        setEditingSubcategoryId(null);
        setEditSubcategoryName("");
      }
      queryClient.invalidateQueries({ queryKey: ["categories", homeId] });
      queryClient.invalidateQueries({ queryKey: ["expenses", homeId] });
      queryClient.invalidateQueries({ queryKey: ["imports", homeId] });
      queryClient.invalidateQueries({ queryKey: ["receipts", homeId] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    }
  });
  return (
    <section className="grid two">
      <div className="panel">
        <h2>Miembros</h2>
        <div className="member-list">
          <div className="member-row member-header">
            <span>Nombre</span>
            <span>Mail</span>
            <span>Consumos</span>
            <span>Acciones</span>
          </div>
          {users.map((user) => {
            const isEditing = editingUserId === user.id;
            return (
              <div className="member-row" key={user.id}>
                {isEditing ? (
                  <>
                    <input value={editUserName} onChange={(event) => setEditUserName(event.target.value)} aria-label={`Nombre usuario ${user.display_name}`} />
                    <input value={editUserEmail} onChange={(event) => setEditUserEmail(event.target.value)} aria-label={`Mail usuario ${user.display_name}`} />
                    <strong>{numberFormat(user.consumption_count ?? 0)}</strong>
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        title="Guardar usuario"
                        aria-label={`Guardar usuario ${user.display_name}`}
                        disabled={!editUserName.trim() || !editUserEmail.trim() || updateMember.isPending}
                        onClick={() => updateMember.mutate({ id: user.id, nextName: editUserName.trim(), nextEmail: editUserEmail.trim() })}
                      >
                        <Save size={16} />
                      </button>
                      <button className="icon-button" title="Cancelar" aria-label="Cancelar edicion de usuario" onClick={() => setEditingUserId(null)}>
                        <X size={16} />
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="member-name">
                      <strong>{user.display_name}</strong>
                      <small>{user.role ?? "member"}</small>
                    </div>
                    <span>{user.email}</span>
                    <strong>{numberFormat(user.consumption_count ?? 0)}</strong>
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        title="Editar usuario"
                        aria-label={`Editar usuario ${user.display_name}`}
                        onClick={() => {
                          setEditingUserId(user.id);
                          setEditUserName(user.display_name);
                          setEditUserEmail(user.email);
                        }}
                      >
                        <Settings size={16} />
                      </button>
                      <button
                        className="icon-button danger"
                        title={user.consumption_count ? "No se puede eliminar con consumos asociados" : "Eliminar usuario"}
                        aria-label={`Eliminar usuario ${user.display_name}`}
                        disabled={deleteMember.isPending || Boolean(user.consumption_count)}
                        onClick={() => {
                          if (window.confirm(`Eliminar a "${user.display_name}" de la casa? Solo se permite si no tiene consumos asociados.`)) {
                            deleteMember.mutate(user.id);
                          }
                        }}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
        {updateMember.isError && <p className="form-error settings-error">No se pudo editar el usuario. Revisá que el mail no este repetido.</p>}
        {deleteMember.isError && <p className="form-error settings-error">No se pudo eliminar el usuario. Solo se pueden borrar usuarios sin consumos asociados.</p>}
      </div>
      <div className="panel">
        <h2>Categorias</h2>
        <button
          className="primary settings-default-button"
          type="button"
          disabled={loadDefaultCategories.isPending}
          onClick={() => loadDefaultCategories.mutate()}
        >
          <Copy size={16} /> Cargar configuracion por defecto
        </button>
        <form
          className="category-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (name.trim()) createCategory.mutate();
          }}
        >
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Nueva categoria" aria-label="Nueva categoria" />
          <label className="color-input" title="Color">
            <SwatchBook size={16} />
            <input type="color" value={color} onChange={(event) => setColor(event.target.value)} aria-label="Color" />
          </label>
          <button className="primary" type="submit" disabled={!name.trim() || createCategory.isPending}>Agregar</button>
        </form>
        <div className="stack">
          {categories.map((category) => {
            const isEditing = editingCategoryId === category.id;
            return (
              <div className="list-row category-row" key={category.id}>
                {isEditing ? (
                  <>
                    <input value={editName} onChange={(event) => setEditName(event.target.value)} aria-label={`Nombre categoria ${category.name}`} />
                    <label className="color-input compact-color" title="Color">
                      <SwatchBook size={16} />
                      <input type="color" value={editColor} onChange={(event) => setEditColor(event.target.value)} aria-label={`Color categoria ${category.name}`} />
                    </label>
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        title="Guardar categoria"
                        disabled={!editName.trim() || updateCategory.isPending}
                        onClick={() => updateCategory.mutate({ id: category.id, nextName: editName.trim(), nextColor: editColor })}
                      >
                        <Save size={16} />
                      </button>
                      <button className="icon-button" title="Cancelar" onClick={() => setEditingCategoryId(null)}>
                        <X size={16} />
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <span>{category.name}</span>
                    <div className="row-actions">
                      <i style={{ background: category.color }} />
                      <button
                        className="icon-button"
                        title="Editar categoria"
                        onClick={() => {
                          setEditingCategoryId(category.id);
                          setEditName(category.name);
                          setEditColor(category.color);
                        }}
                      >
                        <Settings size={16} />
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="panel wide">
        <h2>Subcategorias</h2>
        <form
          className="category-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (selectedSubcategoryCategory && subcategoryName.trim()) createSubcategory.mutate();
          }}
        >
          <select
            value={selectedSubcategoryCategory?.id ?? ""}
            aria-label="Categoria para subcategorias"
            onChange={(event) => setSelectedSubcategoryCategoryId(event.target.value ? Number(event.target.value) : null)}
          >
            {categories.map((category) => <option value={category.id} key={category.id}>{category.name}</option>)}
          </select>
          <input value={subcategoryName} onChange={(event) => setSubcategoryName(event.target.value)} placeholder="Nueva subcategoria" aria-label="Nueva subcategoria" />
          <button className="primary" type="submit" disabled={!selectedSubcategoryCategory || !subcategoryName.trim() || createSubcategory.isPending}>Agregar</button>
        </form>
        <div className="stack">
          {(selectedSubcategoryCategory?.subcategories ?? []).map((subcategory) => {
            const isEditing = editingSubcategoryId === subcategory.id;
            return (
              <div className="list-row category-row" key={subcategory.id}>
                {isEditing ? (
                  <>
                    <input value={editSubcategoryName} onChange={(event) => setEditSubcategoryName(event.target.value)} aria-label={`Nombre subcategoria ${subcategory.name}`} />
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        title="Guardar subcategoria"
                        disabled={!editSubcategoryName.trim() || updateSubcategory.isPending}
                        onClick={() => updateSubcategory.mutate({ id: subcategory.id, nextName: editSubcategoryName.trim() })}
                      >
                        <Save size={16} />
                      </button>
                      <button className="icon-button" title="Cancelar" onClick={() => setEditingSubcategoryId(null)}>
                        <X size={16} />
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <span>{subcategory.name}</span>
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        title="Editar subcategoria"
                        aria-label={`Editar subcategoria ${subcategory.name}`}
                        onClick={() => {
                          setEditingSubcategoryId(subcategory.id);
                          setEditSubcategoryName(subcategory.name);
                        }}
                      >
                        <Settings size={16} />
                      </button>
                      {!subcategory.is_system && (
                        <button
                          className="icon-button danger"
                          title="Eliminar subcategoria"
                          aria-label={`Eliminar subcategoria ${subcategory.name}`}
                          disabled={deleteSubcategory.isPending}
                          onClick={() => {
                            if (window.confirm(`Eliminar la subcategoria "${subcategory.name}"? Los gastos asociados se conservan sin subcategoria.`)) {
                              deleteSubcategory.mutate(subcategory.id);
                            }
                          }}
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
            );
          })}
          {selectedSubcategoryCategory && !(selectedSubcategoryCategory.subcategories ?? []).length && <p className="muted">Esta categoria todavia no tiene subcategorias.</p>}
        </div>
      </div>
    </section>
  );
}

function sourceLabel(source: ExpenseSource) {
  return { manual: "Manual", import_pdf: "Credito", bank_import: "Cuenta", cash: "Efectivo", transfer: "Transferencia", other: "Otro" }[source];
}

function kindLabel(kind: string) {
  return {
    purchase: "Compra",
    refund: "Reintegro",
    payment: "Pago",
    tax: "Impuesto",
    fee: "Comision",
    adjustment: "Ajuste",
    debit_purchase: "Debito",
    cash_withdrawal: "Extraccion efectivo",
    card_payment: "Pago tarjeta ignorado",
    transfer: "Transferencia",
    income: "Ingreso",
    reimbursement: "Reintegro",
    previous_payment: "Pago anterior"
  }[kind] ?? kind;
}

function duplicateLabel(status: string) {
  return { new: "Nueva", previously_parsed: "Parseada antes", already_committed: "Ya convertida" }[status] ?? status;
}

function isIgnoredImportKind(kind: string) {
  return kind === "card_payment" || kind === "previous_payment";
}

function isIgnoredImportLine(line: { kind: string; description: string }) {
  return isIgnoredImportKind(line.kind) || line.description.toUpperCase().includes("TITULOS");
}

function ignoredImportReason(line: { kind: string; description: string }) {
  if (line.kind === "previous_payment") return "Pago anterior";
  if (line.description.toUpperCase().includes("TITULOS")) return "Operacion MEP ignorada";
  return "Ignorado";
}

function actionLabel(action: string) {
  return {
    expense_create: "Gasto creado",
    expense_update: "Gasto editado",
    expense_delete: "Gasto eliminado",
    member_update: "Usuario editado",
    member_delete: "Usuario eliminado",
    import_upload: "Statement cargado",
    import_commit: "Importacion procesada",
    import_delete: "Importacion borrada",
    cash_create: "Efectivo creado",
    cash_adjust: "Efectivo ajustado",
    category_create: "Categoria creada",
    category_update: "Categoria editada",
    subcategory_create: "Subcategoria creada",
    subcategory_update: "Subcategoria editada",
    receipt_upload: "Ticket cargado",
    receipt_review: "Ticket revisado",
    receipt_associate: "Ticket asociado",
    receipt_delete: "Ticket borrado"
  }[action] ?? action;
}

function receiptStatusLabel(status: ReceiptImport["status"]) {
  return {
    parsed: "Parseado",
    parsed_llm: "Parseado con IA",
    reviewed: "Revisado",
    associated: "Asociado",
    ocr_no_items: "OCR sin items",
    uploaded_pending_ocr: "Pendiente OCR",
    uploaded_unsupported: "Formato pendiente"
  }[status] ?? status;
}

function receiptUploadStatusLabel(status: "processing" | "cancelled" | "timeout" | "error") {
  return {
    processing: "Analizando ticket",
    cancelled: "Cancelado",
    timeout: "Tiempo agotado",
    error: "Error de carga"
  }[status];
}
