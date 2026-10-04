import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";

const apiBase = "http://127.0.0.1:8000/households/1";
const mauroHeaders = { "X-Test-User-Email": "mauro@example.test" };
const micaHeaders = { "X-Test-User-Email": "mica@example.test" };

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8000/test/reset");
});

async function seedFund(request: APIRequestContext, period = "2026-06") {
  const opening = await request.put(`${apiBase}/fund/opening-balance`, {
    headers: mauroHeaders,
    data: { start_date: `${period}-01`, amount: "0" }
  });
  expect(opening.ok()).toBeTruthy();
  const config = await request.put(`${apiBase}/fund/config/${period}`, {
    headers: mauroHeaders,
    data: { monthly_amount: "4000000", shares: [{ user_id: 1, percentage: "76" }, { user_id: 2, percentage: "24" }] }
  });
  expect(config.ok()).toBeTruthy();
}

async function addSharedExpense(request: APIRequestContext, amount: string, period = "2026-06") {
  const response = await request.post(`${apiBase}/expenses`, {
    headers: mauroHeaders,
    data: {
      date: `${period}-10`, description: `Gasto compartido ${amount}`, category_id: null,
      paid_by_user_id: 1, currency: "ARS", original_amount: amount,
      source: "manual", is_shared: true
    }
  });
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<{ id: number }>;
}

async function fundSummary(request: APIRequestContext, period: string) {
  const response = await request.get(`${apiBase}/fund/summary?period=${period}`, { headers: mauroHeaders });
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<{
    status: string;
    config: { source_period: string; monthly_amount: string; shares: Array<{ user_id: number; percentage: string }> };
    totals: { agreed_opening_balance: string; agreed_balance: string; verified_balance: string; difference: string };
    plan: Array<{ from_name: string; to_name: string; amount: string }>;
  }>;
}

async function openFund(page: Page, period: string) {
  await page.goto("/");
  await page.getByRole("button", { name: "Fondo común" }).click();
  await page.getByLabel("Mes del fondo").fill(period);
  await page.getByLabel("Mes del fondo").blur();
  await expect(page.locator(".fund-metrics")).toBeVisible();
}

async function clickInViewport(locator: Locator) {
  // Mobile Chromium can expose a layout viewport taller than its visual one.
  await locator.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    window.scrollTo(0, window.scrollY + rect.top - (window.visualViewport?.height ?? window.innerHeight) / 2);
  });
  await locator.click();
}

test("configuration is inherited until a later month overrides it", async ({ page, request }) => {
  await seedFund(request);
  const august = await request.put(`${apiBase}/fund/config/2026-08`, {
    headers: mauroHeaders,
    data: { monthly_amount: "5000000", shares: [{ user_id: 1, percentage: "60" }, { user_id: 2, percentage: "40" }] }
  });
  expect(august.ok()).toBeTruthy();

  await openFund(page, "2026-07");
  await expect(page.getByLabel("Fondo mensual", { exact: true })).toHaveValue("4.000.000");
  await expect(page.getByLabel("Mauro (%)")).toHaveValue("76");
  await page.getByLabel("Mes del fondo").fill("2026-09");
  await expect(page.getByLabel("Fondo mensual", { exact: true })).toHaveValue("5.000.000");
  await expect(page.getByLabel("Mauro (%)")).toHaveValue("60");
  expect((await fundSummary(request, "2026-06")).config.monthly_amount).toBe("4000000.00");
});

test("a fully paid 4m expense only asks Mica to reimburse Mauro", async ({ page, request }) => {
  await seedFund(request);
  await addSharedExpense(request, "4000000");
  await openFund(page, "2026-06");

  const summary = await fundSummary(request, "2026-06");
  expect(summary.plan).toEqual([{ from_name: "Mica", to_name: "Mauro", amount: "960000.00", from_user_id: 2, to_user_id: 1, to_kind: "person" }]);
  expect(summary.totals.agreed_balance).toBe("0.00");
  await expect(page.locator(".fund-plan-list")).toContainText("960.000");
  await expect(page.locator(".fund-metric").filter({ hasText: "Saldo acordado" })).toContainText(/\b0\b/);
});

test("excess spending raises the financing base and shows a red warning", async ({ page, request }) => {
  await seedFund(request);
  await addSharedExpense(request, "5000000");
  await openFund(page, "2026-06");

  await expect(page.locator(".fund-alert.danger-alert")).toContainText("1.000.000");
  await expect(page.locator(".fund-metric.danger").filter({ hasText: "Exceso" })).toContainText("1.000.000");
  const summary = await fundSummary(request, "2026-06");
  expect(summary.plan).toHaveLength(1);
  expect(summary.plan[0]).toMatchObject({ from_name: "Mica", to_name: "Mauro", amount: "1200000.00" });
  expect(summary.totals.agreed_balance).toBe("0.00");
});

test("an over-budget month projects zero agreed balance but keeps the verified money", async ({ page, request }) => {
  const opening = await request.put(`${apiBase}/fund/opening-balance`, {
    headers: mauroHeaders, data: { start_date: "2026-06-01", amount: "3900000" }
  });
  expect(opening.ok()).toBeTruthy();
  const config = await request.put(`${apiBase}/fund/config/2026-06`, {
    headers: mauroHeaders,
    data: { monthly_amount: "4000000", shares: [{ user_id: 1, percentage: "76" }, { user_id: 2, percentage: "24" }] }
  });
  expect(config.ok()).toBeTruthy();
  await addSharedExpense(request, "4100000");
  await openFund(page, "2026-06");

  const summary = await fundSummary(request, "2026-06");
  expect(summary.totals.agreed_opening_balance).toBe("3900000.00");
  expect(summary.totals.agreed_balance).toBe("0.00");
  expect(summary.totals.verified_balance).toBe("3900000.00");
  const seriesResponse = await request.get(`${apiBase}/fund/series`, { headers: mauroHeaders });
  expect(seriesResponse.ok()).toBeTruthy();
  const series = await seriesResponse.json();
  expect(series.find((row: { period: string }) => row.period === "2026-06")).toMatchObject({
    agreed_balance: "0.00", verified_balance: "3900000.00"
  });
  await expect(page.locator(".fund-metric").filter({ hasText: "Saldo acordado" })).toContainText(/\b0\b/);
  await expect(page.locator(".fund-metric").filter({ hasText: "Saldo verificado" })).toContainText("3.900.000");
});

test("closing needs Mica's approval and carries the agreed balance without a real transfer", async ({ page, request }) => {
  await seedFund(request);
  await addSharedExpense(request, "3500000");
  await openFund(page, "2026-06");
  await clickInViewport(page.getByRole("button", { name: /Calcular cierre/ }));
  await expect(page.locator(".fund-status")).toContainText("Pendiente de aprobación");
  await expect(page.getByText("Mica: pendiente")).toBeVisible();

  const approved = await request.post(`${apiBase}/fund/months/2026-06/approve`, { headers: micaHeaders });
  expect(approved.ok()).toBeTruthy();
  await page.getByLabel("Mes del fondo").fill("2026-07");
  await expect(page.locator(".fund-metric").filter({ hasText: "Saldo acordado" })).toContainText("4.500.000");
  const july = await fundSummary(request, "2026-07");
  expect(july.totals.agreed_opening_balance).toBe("500000.00");
  expect(july.totals.verified_balance).toBe("0.00");
  expect(july.totals.difference).toBe("-4500000.00");
});

test("changed expenses mark a closure stale until it is reopened and recalculated", async ({ page, request }) => {
  await seedFund(request);
  const expense = await addSharedExpense(request, "3500000");
  const close = await request.post(`${apiBase}/fund/months/2026-06/close`, { headers: mauroHeaders });
  expect(close.ok()).toBeTruthy();
  const changed = await request.put(`${apiBase}/expenses/${expense.id}`, { headers: mauroHeaders, data: { original_amount: "3600000" } });
  expect(changed.ok()).toBeTruthy();

  await openFund(page, "2026-06");
  await expect(page.locator(".fund-status")).toContainText("Cierre desactualizado");
  const prematureClose = await request.post(`${apiBase}/fund/months/2026-06/close`, { headers: mauroHeaders });
  expect(prematureClose.status()).toBe(409);
  await clickInViewport(page.getByRole("button", { name: "Reabrir y recalcular" }));
  await expect(page.locator(".fund-status")).toContainText("Abierto");
  await expect(page.locator(".fund-plan-list")).toContainText("400.000");
  await clickInViewport(page.getByRole("button", { name: /Calcular cierre/ }));
  await expect(page.locator(".fund-status")).toContainText("Pendiente de aprobación");
});

test("real reimbursements settle the plan and reconcile the verified balance", async ({ page, request }) => {
  await seedFund(request);
  await addSharedExpense(request, "3500000");
  await openFund(page, "2026-06");

  await page.getByLabel("Fecha del movimiento").fill("2026-06-20");
  await page.getByLabel("Origen del movimiento").selectOption({ label: "Mica" });
  await page.getByLabel("Destino del movimiento").selectOption({ label: "Mauro" });
  await page.getByLabel("Importe del movimiento").fill("460000");
  await page.getByRole("button", { name: "Registrar" }).evaluate((button: HTMLButtonElement) => button.click());
  await expect(page.locator(".fund-plan-list")).not.toContainText("Mauro");

  await page.getByLabel("Destino del movimiento").selectOption({ label: "Fondo común" });
  await page.getByLabel("Importe del movimiento").fill("500000");
  await page.getByRole("button", { name: "Registrar" }).evaluate((button: HTMLButtonElement) => button.click());
  await expect(page.getByText("No quedan transferencias pendientes para este cierre.")).toBeVisible();
  const summary = await fundSummary(request, "2026-06");
  expect(summary.totals.agreed_balance).toBe("500000.00");
  expect(summary.totals.verified_balance).toBe("500000.00");
  expect(summary.totals.difference).toBe("0.00");
});

test("a shared MP wallet attributes deposits to their real contributors", async ({ page, request }) => {
  await seedFund(request);
  const fixture = await request.post("http://127.0.0.1:8000/test/seed-fund-mp");
  expect(fixture.ok()).toBeTruthy();

  const personal = await request.get(`${apiBase}/fund/summary?period=2026-06`, { headers: mauroHeaders });
  expect(personal.ok()).toBeTruthy();
  const personalSummary = await personal.json();
  expect(personalSummary.mp_contributions).toHaveLength(0);
  expect(personalSummary.positions.find((row: { user_id: number }) => row.user_id === 1).direct_paid).toBe("15000.00");
  expect(personalSummary.totals.verified_balance).toBe("0.00");

  const forbidden = await request.patch(`${apiBase}/mercadopago/integrations/1/fund-role`, {
    headers: micaHeaders, data: { fund_role: "fondo_comun" }
  });
  expect(forbidden.status()).toBe(403);

  await openFund(page, "2026-06");
  await expect(page.getByLabel("Usar cuenta MP de Mica para el fondo")).toBeDisabled();
  await page.getByLabel("Usar cuenta MP de Mauro para el fondo").evaluate((input: HTMLInputElement) => input.click());
  await expect(page.getByLabel("Usar cuenta MP de Mauro para el fondo")).toBeChecked();
  await expect(page.locator(".fund-mp-row")).toHaveCount(3);
  await expect(page.locator(".fund-mp-personal-row")).toContainText("Compra personal");
  const common = await request.get(`${apiBase}/fund/summary?period=2026-06`, { headers: mauroHeaders });
  const commonSummary = await common.json();
  expect(commonSummary.positions.find((row: { user_id: number }) => row.user_id === 1).direct_paid).toBe("0.00");
  expect(commonSummary.totals.verified_balance).toBe("11000.00");
  expect(commonSummary.alerts.some((alert: string) => alert.includes("compra(s) personales"))).toBeTruthy();

  const mauroIncome = page.locator(".fund-mp-row").filter({ hasText: "Ingreso Mauro" });
  const micaIncome = page.locator(".fund-mp-row").filter({ hasText: "Ingreso Mica" });
  await expect(micaIncome).toContainText("Pagador: Mica");
  await expect(micaIncome.locator("select")).toHaveValue("2");
  await expect(micaIncome).toContainText("asignado por nombre (revisar)");
  const unknownIncome = page.locator(".fund-mp-row").filter({ hasText: "Ingreso desconocido" });
  await mauroIncome.locator("select").selectOption("1");
  await expect(mauroIncome.locator("select")).toHaveValue("1");
  await micaIncome.locator("select").selectOption("2");
  await expect(micaIncome.locator("select")).toHaveValue("2");
  await unknownIncome.locator("select").selectOption("excluded");
  await expect(unknownIncome.locator("select")).toHaveValue("excluded");
  await micaIncome.getByRole("button", { name: "Recordar origen" }).evaluate((button: HTMLButtonElement) => button.click());
  await expect(page.getByRole("status")).toContainText("Origen recordado");
  await expect(micaIncome).toContainText("asignado por origen recordado");
  await expect(micaIncome.getByRole("button", { name: "Recordar origen" })).toHaveCount(0);

  const classified = await request.get(`${apiBase}/fund/summary?period=2026-06`, { headers: mauroHeaders });
  const classifiedSummary = await classified.json();
  expect(classifiedSummary.positions.find((row: { user_id: number }) => row.user_id === 1).contributed).toBe("8000.00");
  expect(classifiedSummary.positions.find((row: { user_id: number }) => row.user_id === 1).personal_repaid).toBe("2000.00");
  expect(classifiedSummary.positions.find((row: { user_id: number }) => row.user_id === 2).contributed).toBe("15000.00");
  expect(classifiedSummary.totals.verified_balance).toBe("8000.00");

  const followup = await request.post("http://127.0.0.1:8000/test/seed-fund-mp?phase=followup");
  expect(followup.ok()).toBeTruthy();
  await page.reload();
  await page.getByRole("button", { name: "Fondo común" }).click();
  await page.getByLabel("Mes del fondo").fill("2026-06");
  await expect(page.locator(".fund-mp-row").filter({ hasText: "Segundo ingreso Mica" }).locator("select")).toHaveValue("2");
  const updated = await request.get(`${apiBase}/fund/summary?period=2026-06`, { headers: mauroHeaders });
  const updatedSummary = await updated.json();
  expect(updatedSummary.positions.find((row: { user_id: number }) => row.user_id === 2).contributed).toBe("20000.00");
  expect(updatedSummary.totals.verified_balance).toBe("13000.00");

  const later = await request.post("http://127.0.0.1:8000/test/seed-fund-mp?phase=later-month");
  expect(later.ok()).toBeTruthy();
  await page.reload();
  await page.getByRole("button", { name: "Fondo común" }).click();
  await page.getByLabel("Mes del fondo").fill("2026-06");
  await expect(page.locator(".fund-mp-row").filter({ hasText: "Ingreso siguiente mes" })).toBeVisible();
  await page.getByLabel(/Sólo junio de 2026/).evaluate((input: HTMLInputElement) => input.click());
  await expect(page.locator(".fund-mp-row").filter({ hasText: "Ingreso siguiente mes" })).toHaveCount(0);
});

test("a personal MP purchase is a separate owner outflow and not a shared expense", async ({ page, request }) => {
  await seedFund(request);
  expect((await request.post("http://127.0.0.1:8000/test/seed-fund-mp")).ok()).toBeTruthy();
  await openFund(page, "2026-06");
  await page.getByLabel("Usar cuenta MP de Mauro para el fondo").evaluate((input: HTMLInputElement) => input.click());
  await expect(page.getByLabel("Usar cuenta MP de Mauro para el fondo")).toBeChecked();
  // A confirmed manual pending classification must override the payer-name suggestion.
  const ownIncome = page.locator(".fund-mp-row").filter({ hasText: "Ingreso Mauro" });
  await expect(ownIncome.locator("select")).toHaveValue("1");
  await ownIncome.locator("select").selectOption("pending");
  await expect(ownIncome.locator("select")).toHaveValue("pending");
  const initial = await fundSummary(request, "2026-06") as any;
  expect(initial.totals.shared_expenses).toBe("15000.00");
  expect(initial.totals.personal_outflows).toBe("2000.00");
  expect(initial.totals.personal_to_repay).toBe("2000.00");
  expect(initial.plan).toContainEqual(expect.objectContaining({ from_name: "Mauro", to_name: "Fondo común", amount: "2000.00", reason: "personal_mp_outflow" }));
  await expect(page.locator(".fund-plan-reason")).toContainText("Reponer compra personal");

  const movement = await request.post(`${apiBase}/fund/manual-movements`, {
    headers: mauroHeaders,
    data: { date: "2026-06-20", from_user_id: 1, to_user_id: null, amount: "2000", note: "Repone compra personal" }
  });
  expect(movement.ok()).toBeTruthy();
  const repaid = await fundSummary(request, "2026-06") as any;
  expect(repaid.totals.personal_to_repay).toBe("0.00");
  expect(repaid.positions.find((row: { user_id: number }) => row.user_id === 1).contributed).toBe("0.00");
  expect(repaid.plan.some((row: { reason?: string }) => row.reason === "personal_mp_outflow")).toBeFalsy();
  expect(repaid.totals.verified_balance).toBe("13000.00");

  await page.locator(".fund-mp-personal-row").getByRole("button", { name: "Marcar compartida" }).evaluate((button: HTMLButtonElement) => button.click());
  await expect(page.locator(".fund-mp-personal-row")).toHaveCount(0);
  const shared = await fundSummary(request, "2026-06") as any;
  expect(shared.totals.shared_expenses).toBe("17000.00");
  expect(shared.totals.personal_outflows).toBe("0.00");
  expect(shared.totals.verified_balance).toBe("13000.00");
  await expect(page.locator(".fund-config-panel")).toBeVisible();
});
