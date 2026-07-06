import { Fragment, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bell,
  CalendarClock,
  ChevronDown,
  ChevronRight,
  CircleDollarSign,
  ClipboardList,
  FlaskConical,
  History as HistoryIcon,
  Home,
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
  WalletCards,
  Wrench,
  X
} from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "./api";
import { categories as fallbackCategories, users as fallbackUsers } from "./mockData";
import type { Category, Currency, Expense, ExpenseSource, ImportBatch, ImportLine, User } from "./types";

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

const chartColors = ["#334155", "#475569", "#64748b", "#71717a", "#94a3b8", "#0ea5e9", "#2563eb", "#60a5fa", "#38bdf8", "#ef4444"];

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

function sortKeysByPeriodAmount(rows: Array<Record<string, string | number>>, period: string, keys: string[], descending = true) {
  const row = rows.find((item) => item.period === period);
  return [...keys].sort((a, b) => {
    const diff = Number(row?.[b] ?? 0) - Number(row?.[a] ?? 0);
    return descending ? diff : -diff;
  });
}

function sortKeysByFinalAmount(rows: Array<Record<string, string | number>>, keys: string[]) {
  const row = [...rows].reverse().find((item) => rowTotal(item, keys) !== 0);
  return [...keys].sort((a, b) => Number(row?.[b] ?? 0) - Number(row?.[a] ?? 0));
}

function categoryNames(categories: Array<Pick<Category, "name">>) {
  return categories.map((category) => category.name);
}

function monthPeriods(year: number) {
  return Array.from({ length: 12 }, (_, index) => `${year}-${String(index + 1).padStart(2, "0")}`);
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

function categoryDeltaRows(rows: Array<Record<string, string | number>>, keys: string[]) {
  return rows.map((row, index) => {
    const previous = rows[index - 1];
    return {
      period: String(row.period),
      values: keys.map((key) => {
        const current = Number(row[key] ?? 0);
        const prior = previous ? Number(previous[key] ?? 0) : 0;
        const percent = prior === 0 ? (current === 0 ? 0 : null) : ((current - prior) / Math.abs(prior)) * 100;
        return { key, current, prior, percent };
      })
    };
  });
}

function importTotals(lines: ImportLine[], selected: number[], sourceType?: string) {
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
      if (line.kind === "income") totals.income[line.currency] = (totals.income[line.currency] ?? 0) + Math.abs(amount);
      else totals.expense[line.currency] = (totals.expense[line.currency] ?? 0) + Math.abs(amount);
    }
  }
  return totals;
}

function orderedImportLines(lines: ImportLine[]) {
  const currencyOrder: Record<Currency, number> = { USD: 0, ARS: 1 };
  return [...lines].sort((a, b) => {
    const currencyDiff = currencyOrder[a.currency] - currencyOrder[b.currency];
    if (currencyDiff) return currencyDiff;
    return a.id - b.id;
  });
}

function categoryColor(name: string, categories: Array<Pick<Category, "name" | "color">>, keys: string[]) {
  return categories.find((category) => category.name === name)?.color ?? chartColors[Math.max(keys.indexOf(name), 0) % chartColors.length];
}

export function App() {
  const [section, setSection] = useState("dashboard");
  const [query, setQuery] = useState("");
  const [paidBy, setPaidBy] = useState("all");
  const queryClient = useQueryClient();
  const households = useQuery({ queryKey: ["households"], queryFn: api.households });
  const homeId = households.data?.[0]?.id ?? 1;
  const members = useQuery({ queryKey: ["members", homeId], queryFn: () => api.members(homeId) });
  const dashboard = useQuery({ queryKey: ["dashboard", homeId, paidBy], queryFn: () => api.dashboard(homeId, paidBy) });
  const expenses = useQuery({ queryKey: ["expenses", homeId], queryFn: () => api.expenses(homeId) });
  const categoryQuery = useQuery({ queryKey: ["categories", homeId], queryFn: () => api.categories(homeId) });
  const cats = categoryQuery.data ?? fallbackCategories;
  const people = members.data?.length ? members.data : fallbackUsers;
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

  const filteredExpenses = useMemo(() => {
    return (expenses.data ?? []).filter((expense) => {
      const category = cats.find((cat) => cat.id === expense.category_id);
      const subcategory = category?.subcategories?.find((item) => item.id === expense.subcategory_id);
      const haystack = `${expense.description} ${category?.name ?? ""} ${subcategory?.name ?? ""}`.toLowerCase();
      const matchesText = haystack.includes(query.toLowerCase());
      const matchesUser = paidBy === "all" || String(expense.paid_by_user_id) === paidBy;
      return matchesText && matchesUser;
    });
  }, [expenses.data, cats, query, paidBy]);

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
          <NavButton active={section === "expenses"} icon={<ReceiptText />} label="Gastos" onClick={() => setSection("expenses")} />
          <NavButton active={section === "imports"} icon={<Upload />} label="Importaciones" onClick={() => setSection("imports")} />
          <NavButton active={section === "cash"} icon={<WalletCards />} label="Efectivo" onClick={() => setSection("cash")} />
          <NavButton active={section === "history"} icon={<HistoryIcon />} label="Historial" onClick={() => setSection("history")} />
          <NavButton active={section === "receipts"} icon={<FlaskConical />} label="Tickets" onClick={() => setSection("receipts")} />
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
            <button className="icon-button" title="Alertas"><Bell size={18} /></button>
            <button className="primary" onClick={() => setSection("expenses")}><Plus size={18} /> Nuevo gasto</button>
          </div>
        </header>
        {section === "dashboard" && <Dashboard categories={cats} data={dashboard.data} users={people} paidBy={paidBy} setPaidBy={setPaidBy} />}
        {section === "expenses" && (
          <Expenses
            categories={cats}
            expenses={filteredExpenses}
            users={people}
            onAdd={(payload) => addExpense.mutate(payload)}
            onUpdate={(id, payload) => updateExpense.mutate({ id, payload })}
            onDelete={(id) => deleteExpense.mutate(id)}
            paidBy={paidBy}
            query={query}
            setPaidBy={setPaidBy}
            setQuery={setQuery}
          />
        )}
        {section === "imports" && <Imports categories={cats} users={people} homeId={homeId} />}
        {section === "cash" && <CashWallet users={people} homeId={homeId} />}
        {section === "history" && <HistoryPanel users={people} homeId={homeId} />}
        {section === "receipts" && <ReceiptsLab expenses={expenses.data ?? []} homeId={homeId} />}
        {section === "settings" && <SettingsPanel categories={cats} users={people} homeId={homeId} />}
      </main>
    </div>
  );
}

function NavButton(props: { active: boolean; icon: ReactNode; label: string; onClick: () => void }) {
  return (
    <button className={props.active ? "nav active" : "nav"} onClick={props.onClick}>
      {props.icon}
      {props.label}
    </button>
  );
}

function titleFor(section: string) {
  return {
    dashboard: "Resumen de consumos",
    expenses: "Gastos del hogar",
    imports: "Importar resumen",
    cash: "Billetera de efectivo",
    history: "Historial",
    receipts: "Tickets de supermercado",
    settings: "Configuracion de casa"
  }[section];
}

function Dashboard({
  categories,
  data,
  users,
  paidBy,
  setPaidBy
}: {
  categories: Array<Pick<Category, "name" | "color">>;
  data?: Awaited<ReturnType<typeof api.dashboard>>;
  users: User[];
  paidBy: string;
  setPaidBy: (value: string) => void;
}) {
  const [activeMonthlyCategory, setActiveMonthlyCategory] = useState<string | null>(null);
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().toISOString().slice(0, 7);
  const periods = monthPeriods(currentYear);
  const rawMonthlyData = toChartRows(data?.monthly_by_category ?? []);
  const baseMonthlyKeys = Array.from(new Set([...categoryNames(categories), ...chartKeys(rawMonthlyData)]));
  const legendKeys = categoryNames(categories).filter((name) => baseMonthlyKeys.includes(name));
  const monthlyData = fillMonthlyRows(rawMonthlyData, periods, baseMonthlyKeys);
  const monthlyStackData = buildSortedStackRows(rawMonthlyData, periods, baseMonthlyKeys);
  const rawCumulativeData = toChartRows(data?.cumulative_by_category ?? []);
  const cumulativeKeys = sortKeysByFinalAmount(rawCumulativeData, orderedKeysByFirstValue(rawCumulativeData, categories));
  const cumulativeData = fillCumulativeRows(rawCumulativeData, periods, cumulativeKeys);
  const deltaRows = categoryDeltaRows(monthlyData, legendKeys);
  const currentMonthRow = monthlyData.find((item) => item.period === currentMonth);
  const currentMonthKeys = sortKeysByPeriodAmount(monthlyData, currentMonth, legendKeys, true);
  const chartData = currentMonthKeys.map((name) => ({ name, amount_ars: Number(currentMonthRow?.[name] ?? 0) }));
  const currentMonthTotal = chartData.reduce((sum, item) => sum + item.amount_ars, 0);
  return (
    <section className="grid dashboard-grid">
      <div className="dashboard-filter">
        <select value={paidBy} onChange={(event) => setPaidBy(event.target.value)} aria-label="Filtrar resumen por usuario">
          <option value="all">Todo el hogar</option>
          {users.map((user) => <option value={user.id} key={user.id}>{user.display_name}</option>)}
        </select>
      </div>
      <div className="metric">
        <span>Consumo del mes actual</span>
        <strong>{money(currentMonthTotal)}</strong>
        <small>ARS con USD convertido por dolar blue promedio</small>
      </div>
      <div className="panel">
        <h2>Proyeccion recurrente</h2>
        <div className="stack">
          {(data?.recurring_preview ?? []).map((item) => (
            <div className="list-row" key={item.description}>
              <span>{item.description}</span>
              <strong>{money(item.expected_amount, item.currency)}</strong>
            </div>
          ))}
        </div>
      </div>
      <div className="panel chart-panel wide">
        <h2>Consumo mes actual</h2>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} margin={{ left: 8, right: 24 }}>
            <CartesianGrid stroke="#223047" vertical={false} />
            <XAxis dataKey="name" interval={0} tick={{ fill: "#94a3b8", fontSize: 11 }} />
            <YAxis tickFormatter={(value) => numberFormat(value)} tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <Tooltip
              formatter={(value) => [money(Number(value)), "Consumo"]}
              contentStyle={{ background: "#0f172a", border: "1px solid #263449", color: "#e2e8f0" }}
              itemStyle={{ color: "#e2e8f0" }}
              labelStyle={{ color: "#e2e8f0" }}
            />
            <Bar dataKey="amount_ars" name="Consumo" radius={[4, 4, 0, 0]}>
              {chartData.map((item) => <Cell key={item.name} fill={categoryColor(item.name, categories, currentMonthKeys)} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <CategoryLegend categories={categories} names={legendKeys} />
      </div>
      <div className="panel chart-panel wide">
        <h2>Consumo mensual {currentYear}</h2>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={monthlyStackData} onMouseLeave={() => setActiveMonthlyCategory(null)}>
            <CartesianGrid stroke="#223047" vertical={false} />
            <XAxis dataKey="period_label" tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <YAxis tickFormatter={(value) => numberFormat(value)} tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <Tooltip
              shared={false}
              content={<MonthlySegmentTooltip />}
              contentStyle={{ background: "#0f172a", border: "1px solid #263449", color: "#e2e8f0" }}
              itemStyle={{ color: "#e2e8f0" }}
              labelStyle={{ color: "#e2e8f0" }}
            />
            {baseMonthlyKeys.map((_, slotIndex) => (
              <Bar key={slotIndex} dataKey={`slot_${slotIndex}`} stackId="month">
                {monthlyStackData.map((row) => {
                  const category = String(row[`slot_${slotIndex}_category`] ?? "");
                  return (
                    <Cell
                      key={`${row.period}-${slotIndex}`}
                      fill={categoryColor(category, categories, legendKeys)}
                      fillOpacity={activeMonthlyCategory && activeMonthlyCategory !== category ? 0.24 : 1}
                      onMouseEnter={() => setActiveMonthlyCategory(category)}
                    />
                  );
                })}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
        <CategoryLegend categories={categories} names={legendKeys} active={activeMonthlyCategory} />
      </div>
      <div className="panel chart-panel wide">
        <h2>Consumo acumulado {currentYear}</h2>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={cumulativeData}>
            <CartesianGrid stroke="#223047" vertical={false} />
            <XAxis dataKey="period" tickFormatter={(value) => axisMonthLabel(String(value))} tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <YAxis tickFormatter={(value) => numberFormat(value)} tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <Tooltip
              formatter={(value, name) => [money(Number(value)), String(name)]}
              contentStyle={{ background: "#0f172a", border: "1px solid #263449", color: "#e2e8f0" }}
              itemStyle={{ color: "#e2e8f0" }}
              labelStyle={{ color: "#e2e8f0" }}
            />
            {cumulativeKeys.map((key) => (
              <Area key={key} type="monotone" dataKey={key} stackId="year" stroke={categoryColor(key, categories, cumulativeKeys)} fill={categoryColor(key, categories, cumulativeKeys)} fillOpacity={0.78} />
            ))}
          </AreaChart>
        </ResponsiveContainer>
        <CategoryLegend categories={categories} names={legendKeys.filter((name) => cumulativeKeys.includes(name))} />
      </div>
      <div className="panel chart-panel wide">
        <h2>Variacion mensual por categoria {currentYear}</h2>
        <div className="delta-table-wrap">
          <table className="delta-table">
            <thead>
              <tr>
                <th>Categoria</th>
                {periods.map((period) => <th key={period}>{axisMonthLabel(period)}</th>)}
              </tr>
            </thead>
            <tbody>
              {legendKeys.map((key) => (
                <tr key={key}>
                  <td>{key}</td>
                  {periods.map((period) => {
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

function MonthlySegmentTooltip({ active, payload }: { active?: boolean; payload?: Array<{ value?: number; payload?: Record<string, string | number>; dataKey?: string }> }) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  const slot = String(item.dataKey ?? "");
  const category = item.payload?.[`${slot}_category`];
  if (!category || !Number(item.value ?? 0)) return null;
  return (
    <div className="chart-tooltip">
      <strong>{String(category)}</strong>
      <span>{money(Number(item.value))}</span>
    </div>
  );
}

function CategoryLegend({ categories, names, active }: { categories: Array<Pick<Category, "name" | "color">>; names: string[]; active?: string | null }) {
  if (!names.length) return null;
  return (
    <div className="chart-legend" aria-label="Leyenda de categorias">
      {names.map((name) => (
        <span key={name} className={active && active !== name ? "dimmed" : undefined}>
          <i style={{ background: categoryColor(name, categories, names) }} />
          {name}
        </span>
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
  setQuery: (value: string) => void;
  setPaidBy: (value: string) => void;
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
  const [editingExpenseId, setEditingExpenseId] = useState<number | null>(null);
  const [editAmount, setEditAmount] = useState("");
  const [editCategoryId, setEditCategoryId] = useState("");
  const [editSubcategoryId, setEditSubcategoryId] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [openNoteId, setOpenNoteId] = useState<number | null>(null);
  const [expandedMonths, setExpandedMonths] = useState<Record<string, boolean>>({});
  const selectedCategory = props.categories.find((category) => String(category.id) === categoryId);
  const editingCategory = props.categories.find((category) => String(category.id) === editCategoryId);
  const currentMonth = new Date().toISOString().slice(0, 7);
  const groupedExpenses = groupExpensesByMonth(props.expenses);
  const periods = Object.keys(groupedExpenses).sort().reverse();
  const isMonthExpanded = (period: string) => props.query.trim() ? true : (expandedMonths[period] ?? period === currentMonth);
  const startEditing = (expense: Expense) => {
    setEditingExpenseId(expense.id);
    setEditAmount(String(expense.original_amount));
    setEditCategoryId(expense.category_id ? String(expense.category_id) : "");
    setEditSubcategoryId(expense.subcategory_id ? String(expense.subcategory_id) : "");
    setEditNotes(expense.notes ?? "");
  };
  return (
    <section className="stack">
      <div className="toolbar">
        <label className="search"><Search size={16} /><input value={props.query} onChange={(e) => props.setQuery(e.target.value)} placeholder="Buscar gasto" /></label>
        <select value={props.paidBy} onChange={(e) => props.setPaidBy(e.target.value)} aria-label="Filtrar por usuario">
          <option value="all">Todos</option>
          {props.users.map((u) => <option value={u.id} key={u.id}>{u.display_name}</option>)}
        </select>
      </div>
      <div className="expense-layout">
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
              notes: notes.trim() || null
            });
            setDescription("");
            setAmount("0");
            setNotes("");
            setSubcategoryId("");
          }}
        >
          <h2>Nuevo gasto</h2>
          <input value={description} onChange={(e) => setDescription(e.target.value)} aria-label="Descripcion" placeholder="Descripcion" />
          <input value={amount} onChange={(e) => setAmount(e.target.value)} aria-label="Importe" inputMode="decimal" />
          <select value={paidByUserId} onChange={(e) => setPaidByUserId(e.target.value)} aria-label="Pagado por">
            {props.users.map((u) => <option value={u.id} key={u.id}>{u.display_name}</option>)}
          </select>
          <select value={categoryId} onChange={(e) => { setCategoryId(e.target.value); setSubcategoryId(""); }} aria-label="Categoria">
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
          <textarea value={notes} onChange={(e) => setNotes(e.target.value.slice(0, 500))} aria-label="Nota" placeholder="Nota opcional" maxLength={500} />
          <button className="primary" type="submit"><Plus size={16} /> Agregar</button>
        </form>
        <div className="panel table-panel">
          <h2>Movimientos</h2>
          <table>
            <thead><tr><th>Fecha</th><th>Descripcion</th><th>Pago</th><th>Categoria</th><th>Origen</th><th>Importe</th><th>Nota</th><th>Acciones</th></tr></thead>
            <tbody>
              {periods.map((period) => {
                const monthExpenses = groupedExpenses[period];
                const expanded = isMonthExpanded(period);
                const monthTotal = monthExpenses.reduce((sum, expense) => sum + Number(expense.amount_ars), 0);
                return (
                  <Fragment key={period}>
                    <tr className="month-group-row">
                      <td colSpan={8}>
                        <button
                          className="month-toggle"
                          onClick={() => setExpandedMonths((current) => ({ ...current, [period]: !expanded }))}
                          aria-label={`${expanded ? "Colapsar" : "Expandir"} ${monthLabel(period)}`}
                        >
                          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                          <strong>{monthLabel(period)}</strong>
                          <span>{monthExpenses.length} gastos</span>
                          <b>{money(monthTotal)}</b>
                        </button>
                      </td>
                    </tr>
                    {expanded && monthExpenses.map((expense) => {
                      const cat = props.categories.find((c) => c.id === expense.category_id);
                      const subcat = cat?.subcategories?.find((subcategory) => subcategory.id === expense.subcategory_id);
                      const isEditing = editingExpenseId === expense.id;
                      const hasNotes = !!expense.notes?.trim();
                      return (
                        <Fragment key={expense.id}>
                          <tr className={!expense.category_id ? "needs-review-row" : undefined}>
                            <td>{expense.date}</td>
                            <td>{expense.description}</td>
                            <td>{props.users.find((u) => u.id === expense.paid_by_user_id)?.display_name ?? "Usuario"}</td>
                            <td>
                              {isEditing ? (
                                <div className="inline-edit-fields">
                                  <select
                                    value={editCategoryId}
                                    onChange={(event) => {
                                      setEditCategoryId(event.target.value);
                                      setEditSubcategoryId("");
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
                                <input className="amount-cell-input" value={editAmount} onChange={(event) => setEditAmount(event.target.value)} aria-label={`Editar importe ${expense.description}`} inputMode="decimal" />
                              ) : (
                                money(expense.original_amount, expense.currency)
                              )}
                            </td>
                            <td>
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
                            <td>
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
                                        notes: editNotes.trim() || null
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
                              <td colSpan={8}>{expense.notes}</td>
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
  const [paidByUserId, setPaidByUserId] = useState(String(users[0]?.id ?? 1));
  const queryClient = useQueryClient();
  const pendingImports = useQuery({ queryKey: ["imports", homeId, "parsed"], queryFn: () => api.imports(homeId, "parsed") });
  const loadBatch = (data: ImportBatch) => {
    setBatch(data);
    setSelected(data.lines.filter((line) => line.duplicate_status !== "already_committed" && !isIgnoredImportKind(line.kind)).map((line) => line.id));
    setCategoryByLine(Object.fromEntries(data.lines.map((line) => [line.id, line.suggested_category_id])));
    setSubcategoryByLine(Object.fromEntries(data.lines.map((line) => [line.id, line.suggested_subcategory_id])));
  };
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
    mutationFn: () => api.commitImport(homeId, batch!.id, selected, Number(paidByUserId), categoryByLine, subcategoryByLine),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["expenses", homeId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", homeId] });
      setBatch(null);
      setSelected([]);
      setCategoryByLine({});
      setSubcategoryByLine({});
      queryClient.invalidateQueries({ queryKey: ["imports", homeId, "parsed"] });
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
      }
      queryClient.invalidateQueries({ queryKey: ["imports", homeId, "parsed"] });
    }
  });
  const totals = importTotals(batch?.lines ?? [], selected, batch?.source_type);
  const reviewCount = (batch?.lines ?? []).filter((line) => selected.includes(line.id) && !categoryByLine[line.id] && !isIgnoredImportKind(line.kind)).length;
  const reviewLines = useMemo(() => orderedImportLines(batch?.lines ?? []), [batch]);
  const duplicateCounts = batch?.lines.reduce<Record<string, number>>((acc, line) => {
    acc[line.duplicate_status] = (acc[line.duplicate_status] ?? 0) + 1;
    return acc;
  }, {}) ?? {};
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
          {(duplicateCounts.previously_parsed || duplicateCounts.already_committed) && (
            <div className="warning">
              {duplicateCounts.previously_parsed ? `${duplicateCounts.previously_parsed} lineas ya habian sido parseadas pero no convertidas. ` : ""}
              {duplicateCounts.already_committed ? `${duplicateCounts.already_committed} lineas ya fueron convertidas a gastos y quedan desmarcadas para evitar duplicarlas.` : ""}
            </div>
          )}
          <div className="table-heading">
            <div>
              <h2>Lineas detectadas</h2>
              <div className="import-totals" aria-label="Totales importados">
                {batch.source_type === "bbva_account_xls" ? (
                  <>
                    <span>Ingresos ARS <strong>{money(totals.income.ARS ?? 0, "ARS")}</strong></span>
                    <span>Egresos ARS <strong>{money(totals.expense.ARS ?? 0, "ARS")}</strong></span>
                    <span>Ingresos USD <strong>{money(totals.income.USD ?? 0, "USD")}</strong></span>
                    <span>Egresos USD <strong>{money(totals.expense.USD ?? 0, "USD")}</strong></span>
                  </>
                ) : (
                  <>
                    <span>Total ARS <strong>{money(Math.abs(totals.total.ARS ?? 0), "ARS")}</strong></span>
                    <span>Total USD <strong>{money(Math.abs(totals.total.USD ?? 0), "USD")}</strong></span>
                  </>
                )}
              </div>
              <div className={reviewCount ? "review-counter warning-status" : "review-counter"}>
                <AlertTriangle size={16} />
                Gastos a revisar: <strong>{reviewCount}</strong>
              </div>
            </div>
            <div className="toolbar compact">
              <select value={paidByUserId} onChange={(e) => setPaidByUserId(e.target.value)} aria-label="Pagador del resumen">
                {users.map((u) => <option value={u.id} key={u.id}>{u.display_name}</option>)}
              </select>
              <button className="primary" disabled={!selected.length || commit.isPending} onClick={() => commit.mutate()}>
                Procesar {selected.length} lineas
              </button>
            </div>
          </div>
          <table>
            <thead><tr><th></th><th>Fecha</th><th>Descripcion</th><th>Tipo</th><th>Categoria</th><th>Subcategoria</th><th>Importe</th><th>Estado</th></tr></thead>
            <tbody>
              {reviewLines.map((line, index) => {
                const selectedCategory = categories.find((category) => category.id === categoryByLine[line.id]);
                const isIgnoredCardPayment = isIgnoredImportKind(line.kind);
                const showCurrencySeparator = index === 0 || reviewLines[index - 1].currency !== line.currency;
                return (
                  <Fragment key={line.id}>
                    {showCurrencySeparator && (
                      <tr className={`currency-separator ${line.currency.toLowerCase()}`}>
                        <td colSpan={8}>Consumos en {line.currency}</td>
                      </tr>
                    )}
                    <tr key={line.id} className={isIgnoredCardPayment ? "ignored-row" : !categoryByLine[line.id] ? "needs-review-row" : undefined}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selected.includes(line.id)}
                          disabled={isIgnoredCardPayment}
                          title={isIgnoredCardPayment ? ignoredImportReason(line.kind) : undefined}
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
                        <select
                          value={categoryByLine[line.id] ?? ""}
                          disabled={isIgnoredCardPayment}
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
                          disabled={isIgnoredCardPayment || !(selectedCategory?.subcategories?.length)}
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
                      <td>{money(line.original_amount, line.currency)}</td>
                      <td>
                        <span className={isIgnoredCardPayment || line.duplicate_status !== "new" || !categoryByLine[line.id] ? "status warning-status" : "status"}>
                          {!isIgnoredCardPayment && !categoryByLine[line.id] ? <AlertTriangle size={14} /> : null}
                          {!isIgnoredCardPayment && !categoryByLine[line.id] ? "Revisar categoria" : isIgnoredCardPayment ? ignoredImportReason(line.kind) : duplicateLabel(line.duplicate_status)}
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
  const history = useQuery({ queryKey: ["history", homeId], queryFn: () => api.history(homeId) });
  return (
    <section className="panel table-panel">
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
    </section>
  );
}

function ReceiptsLab({ expenses, homeId }: { expenses: Expense[]; homeId: number }) {
  const [expenseId, setExpenseId] = useState("");
  const queryClient = useQueryClient();
  const receipts = useQuery({ queryKey: ["receipts", homeId], queryFn: () => api.receipts(homeId) });
  const uploadReceipt = useMutation({
    mutationFn: (file: File) => api.uploadReceipt(homeId, file, expenseId ? Number(expenseId) : undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["receipts", homeId] });
      queryClient.invalidateQueries({ queryKey: ["history", homeId] });
    }
  });
  return (
    <section className="grid two">
      <div className="panel form-panel">
        <h2>Ticket experimental</h2>
        <p className="muted">La foto queda asociada a un gasto existente y no crea otro consumo. El OCR queda marcado como pendiente para iterarlo con tickets reales.</p>
        <select value={expenseId} onChange={(event) => setExpenseId(event.target.value)} aria-label="Gasto asociado al ticket">
          <option value="">Sin asociar todavia</option>
          {expenses.slice(0, 80).map((expense) => (
            <option value={expense.id} key={expense.id}>{expense.date} - {expense.description} - {money(expense.original_amount, expense.currency)}</option>
          ))}
        </select>
        <label className="primary file-button">
          <Upload size={16} /> Subir foto
          <input
            type="file"
            accept="image/*"
            aria-label="Subir foto de ticket"
            onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              if (file) uploadReceipt.mutate(file);
              event.currentTarget.value = "";
            }}
          />
        </label>
      </div>
      <div className="panel">
        <h2>Tickets cargados</h2>
        <div className="stack">
          {(receipts.data ?? []).map((receipt) => (
            <div className="list-row" key={receipt.id}>
              <span>{receipt.filename} - {receipt.status}</span>
              <strong>{receipt.created_at ? new Date(receipt.created_at).toLocaleDateString("es-AR") : ""}</strong>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function SettingsPanel({ categories, users, homeId }: { categories: Category[]; users: User[]; homeId: number }) {
  const [name, setName] = useState("");
  const [color, setColor] = useState("#38bdf8");
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editColor, setEditColor] = useState("#38bdf8");
  const queryClient = useQueryClient();
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
  return (
    <section className="grid two">
      <div className="panel">
        <h2>Miembros</h2>
        {users.map((user) => <div className="list-row" key={user.id}><span>{user.display_name}</span><strong>{user.role ?? "member"}</strong></div>)}
      </div>
      <div className="panel">
        <h2>Categorias</h2>
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
    </section>
  );
}

function sourceLabel(source: ExpenseSource) {
  return { manual: "Manual", import_pdf: "PDF", bank_import: "Cuenta", cash: "Efectivo", transfer: "Transferencia", other: "Otro" }[source];
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
    previous_payment: "Pago anterior"
  }[kind] ?? kind;
}

function duplicateLabel(status: string) {
  return { new: "Nueva", previously_parsed: "Parseada antes", already_committed: "Ya convertida" }[status] ?? status;
}

function isIgnoredImportKind(kind: string) {
  return kind === "card_payment" || kind === "previous_payment";
}

function ignoredImportReason(kind: string) {
  return kind === "previous_payment" ? "Pago anterior" : "Ignorado";
}

function actionLabel(action: string) {
  return {
    expense_create: "Gasto creado",
    expense_update: "Gasto editado",
    expense_delete: "Gasto eliminado",
    import_upload: "Statement cargado",
    import_commit: "Importacion procesada",
    import_delete: "Importacion borrada",
    cash_create: "Efectivo creado",
    cash_adjust: "Efectivo ajustado",
    category_create: "Categoria creada",
    category_update: "Categoria editada",
    receipt_upload: "Ticket cargado"
  }[action] ?? action;
}
