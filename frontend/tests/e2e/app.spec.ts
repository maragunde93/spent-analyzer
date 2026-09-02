import { expect, test } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8000/test/reset");
});

test("dashboard renders category consumption chart by payer", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Resumen de consumos" })).toBeVisible();
  const monthlyChart = page.getByTestId("monthly-chart-panel");
  await expect(monthlyChart.getByTestId("monthly-total-label").first()).toBeVisible();
  const monthlyTotalLabels = await monthlyChart.getByTestId("monthly-total-label").count();
  expect(monthlyTotalLabels).toBeGreaterThan(0);
  expect(monthlyTotalLabels).toBeLessThan(12);
  await expect(page.locator(".dashboard-grid h2").nth(2)).toHaveText("Consumos por categoria");
  await expect(page.locator(".dashboard-grid h2").nth(3)).toHaveText("Proyeccion recurrente");

  const categoryConsumptionChart = page.getByTestId("category-consumption-chart-panel");
  await expect(categoryConsumptionChart.getByLabel(/Mes /).last()).toBeChecked();
  await expect(categoryConsumptionChart.getByText(/\$\s*[0-9]/).first()).toBeVisible();
  await expect(categoryConsumptionChart.getByLabel("Leyenda de pagadores")).toBeVisible();

  await categoryConsumptionChart.locator("[data-testid='category-consumption-bar']").first().hover({ force: true });
  await expect(page.getByRole("tooltip")).toContainText("%");

  const secondarySections = [
    ["cumulative-section", /Consumo acumulado/],
    ["category-average-section", "Promedio mensual por categoria"],
    ["category-variation-section", /Variacion mensual por categoria/]
  ] as const;
  for (const [testId, title] of secondarySections) {
    const section = page.getByTestId(testId);
    await expect(section.getByRole("heading", { name: title })).toBeVisible();
    await expect(section.getByRole("button", { name: /Expandir/ })).toHaveAttribute("aria-expanded", "false");
  }

  const cumulativeSection = page.getByTestId("cumulative-section");
  await cumulativeSection.getByRole("button", { name: /Expandir Consumo acumulado/ }).click();
  await expect(cumulativeSection.getByRole("button", { name: /Colapsar Consumo acumulado/ })).toHaveAttribute("aria-expanded", "true");
  await cumulativeSection.getByRole("button", { name: /Colapsar Consumo acumulado/ }).click();
  await expect(cumulativeSection.getByRole("button", { name: /Expandir Consumo acumulado/ })).toHaveAttribute("aria-expanded", "false");
});

test("core bills workflow renders and supports import review", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Resumen de consumos" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Consumo mes actual" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Consumo mensual/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Consumo acumulado/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Ocio / gasto personal" }).first()).toBeVisible();
  const dashboardFilters = page.locator(".dashboard-filters");
  await dashboardFilters.getByRole("button", { name: "Limpiar" }).click({ force: true });
  await expect(page.getByLabel("Categoria Transporte")).not.toBeChecked();
  await page.getByLabel("Categoria Transporte").check();
  await expect(page.getByLabel("Categoria Transporte")).toBeChecked();
  await dashboardFilters.getByRole("button", { name: "Todas" }).click({ force: true });
  await expect(page.getByLabel("Categoria Transporte")).toBeChecked();
  const supermarketLegend = page.getByRole("button", { name: "Sin categoria" }).first();
  await supermarketLegend.click();
  await expect(supermarketLegend).toHaveAttribute("aria-pressed", "true");
  await supermarketLegend.click();
  await expect(supermarketLegend).toHaveAttribute("aria-pressed", "false");
  await page.getByTestId("monthly-chart-panel").locator("[data-testid='monthly-segment']").first().hover({ force: true });
  await expect(page.getByRole("tooltip")).toBeVisible();
  await expect(page.getByRole("tooltip")).toContainText("$");

  await page.getByRole("button", { name: "Consumos" }).click();
  await expect(page.getByRole("heading", { name: "Consumos del hogar" })).toBeVisible();
  await page.getByRole("button", { name: "Importe" }).click();
  await expect(page.getByRole("button", { name: "Importe ↓" })).toBeVisible();
  await page.getByLabel("Descripcion").fill("Cafe de prueba");
  await page.getByLabel("Importe").fill("4500");
  await page.getByRole("button", { name: "Agregar" }).click();
  await page.getByPlaceholder("Buscar gasto").fill("Cafe");
  await expect(page.getByText("Cafe de prueba")).toBeVisible();
  await page.getByRole("button", { name: "Editar gasto Cafe de prueba" }).click();
  await page.getByLabel("Editar importe Cafe de prueba").fill("5000");
  await page.getByLabel("Editar categoria Cafe de prueba").selectOption({ label: "Salud" });
  await page.getByRole("button", { name: "Guardar gasto Cafe de prueba" }).click();
  await page.getByPlaceholder("Buscar gasto").fill("Salud");
  await expect(page.getByText("Cafe de prueba")).toBeVisible();
  page.once("dialog", async (dialog) => {
    await dialog.accept();
  });
  await page.getByRole("button", { name: "Eliminar gasto Cafe de prueba" }).click();
  await expect(page.getByText("Cafe de prueba")).toHaveCount(0);
  await request.post("http://127.0.0.1:8000/households/1/expenses", {
    headers: { "X-Test-User-Email": "mauro@example.test" },
    data: {
      date: "2026-07-06",
      description: "Gasto sin categoria prueba",
      category_id: null,
      paid_by_user_id: 1,
      currency: "ARS",
      original_amount: "1500.00",
      source: "manual"
    }
  });
  await page.reload();
  await page.getByRole("button", { name: "Consumos" }).click();
  await page.getByPlaceholder("Buscar gasto").fill("Sin categoria");
  await expect(page.getByText("Gasto sin categoria prueba")).toBeVisible();
  await page.getByPlaceholder("Buscar gasto").fill("openai");
  await expect(page.getByText("OPENAI *CHATGPT SUBSCR")).toBeVisible();

  await page.getByRole("button", { name: "Carga de Resumenes" }).click();
  await expect(page.getByRole("heading", { name: "Carga de Resumenes", exact: true })).toBeVisible();
  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../tests/fixtures/bbva_visa_sanitized.pdf");
  await expect(page.getByText("Lineas detectadas")).toBeVisible();
  await expect(page.getByText("OPENAI *CHATGPT SUBSCR")).toBeVisible();
  await expect(page.getByLabel("Recurrente OPENAI *CHATGPT SUBSCR")).toBeChecked();
  await expect(page.getByText("Total ARS").first()).toBeVisible();
  await expect(page.getByText("Total USD").first()).toBeVisible();
  await expect(page.getByText("Consumos en USD").first()).toBeVisible();
  await expect(page.getByText("Consumos en ARS").first()).toBeVisible();
  const usdSeparator = await page.getByText("Consumos en USD").first().boundingBox();
  const arsSeparator = await page.getByText("Consumos en ARS").first().boundingBox();
  expect(usdSeparator?.y).toBeLessThan(arsSeparator?.y ?? 0);
  await expect(page.getByRole("button", { name: /Procesar/ })).toBeVisible();
});

test("expenses can be filtered by original currency", async ({ page, request }) => {
  await request.post("http://127.0.0.1:8000/households/1/expenses", {
    headers: { "X-Test-User-Email": "mauro@example.test" },
    data: {
      date: "2026-07-06",
      description: "Gasto ARS para filtro moneda",
      category_id: null,
      paid_by_user_id: 1,
      currency: "ARS",
      original_amount: "1500.00",
      source: "manual"
    }
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Consumos" }).click();
  await expect(page.getByRole("heading", { name: "Consumos del hogar" })).toBeVisible();
  await expect(page.getByLabel("Filtrar por usuario")).toHaveValue("all");

  await page.getByLabel("Filtrar por moneda").selectOption("USD");
  await expect(page.getByText("OPENAI *CHATGPT SUBSCR")).toBeVisible();
  await expect(page.getByText("Gasto ARS para filtro moneda")).toHaveCount(0);

  await page.getByLabel("Filtrar por moneda").selectOption("ARS");
  await expect(page.getByText("Gasto ARS para filtro moneda")).toBeVisible();
  await expect(page.getByText("OPENAI *CHATGPT SUBSCR")).toHaveCount(0);
});

test("expense month groups can be collapsed while searching and after clearing search", async ({ page, request }) => {
  await request.post("http://127.0.0.1:8000/households/1/expenses", {
    headers: { "X-Test-User-Email": "mauro@example.test" },
    data: {
      date: "2026-06-15",
      description: "Filtro colapso junio",
      category_id: null,
      paid_by_user_id: 1,
      currency: "ARS",
      original_amount: "2300.00",
      source: "manual"
    }
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Consumos" }).click();
  await expect(page.getByRole("heading", { name: "Consumos del hogar" })).toBeVisible();

  await page.getByPlaceholder("Buscar gasto").fill("Filtro colapso");
  await expect(page.getByText("Filtro colapso junio")).toBeVisible();

  await page.getByRole("button", { name: /Colapsar todos/ }).click();
  await expect(page.getByText("Filtro colapso junio")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Expandir todos/ })).toBeVisible();

  await page.getByRole("button", { name: /Expandir todos/ }).click();
  await expect(page.getByText("Filtro colapso junio")).toBeVisible();

  await page.getByRole("button", { name: /Colapsar junio de 2026/i }).click();
  await expect(page.getByText("Filtro colapso junio")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Expandir junio de 2026/i })).toBeVisible();

  await page.getByPlaceholder("Buscar gasto").fill("");
  await expect(page.getByText("Filtro colapso junio")).toHaveCount(0);

  await page.getByRole("button", { name: /Expandir junio de 2026/i }).click();
  await expect(page.getByText("Filtro colapso junio")).toBeVisible();
  await page.getByRole("button", { name: /Expandir todos/ }).click();
  await page.getByRole("button", { name: /Colapsar todos/ }).click();
  await expect(page.getByText("Filtro colapso junio")).toHaveCount(0);
});

test("dashboard category average table shows current month and final columns", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Carga de Resumenes" }).click();
  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../tests/fixtures/bbva_visa_sanitized.pdf");
  await expect(page.getByText("Lineas detectadas")).toBeVisible();
  await page.getByRole("button", { name: /Procesar/ }).click();
  await expect(page.locator("[data-testid^='active-import-']")).toHaveCount(0);

  const categoriesResponse = await request.get("http://127.0.0.1:8000/households/1/categories", {
    headers: { "X-Test-User-Email": "mauro@example.test" }
  });
  expect(categoriesResponse.ok()).toBeTruthy();
  const categories = await categoriesResponse.json() as Array<{ id: number; name: string }>;
  const services = categories.find((category) => category.name === "Servicios");
  expect(services).toBeTruthy();
  const currentDate = new Date();
  const currentMonthDate = `${currentDate.getFullYear()}-${String(currentDate.getMonth() + 1).padStart(2, "0")}-06`;
  await request.post("http://127.0.0.1:8000/households/1/expenses", {
    headers: { "X-Test-User-Email": "mauro@example.test" },
    data: {
      date: currentMonthDate,
      description: "Gasto mes en curso promedio",
      category_id: services!.id,
      paid_by_user_id: 1,
      currency: "ARS",
      original_amount: "12345.00",
      source: "manual"
    }
  });

  await page.getByRole("button", { name: "Resumen", exact: true }).click();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Resumen de consumos" })).toBeVisible();
  const averageSection = page.getByTestId("category-average-section");
  await averageSection.getByRole("button", { name: /Expandir Promedio mensual por categoria/ }).click();
  await expect(averageSection.getByRole("button", { name: "Mes en curso" })).toBeVisible();
  await expect(averageSection.getByText("(3 meses)")).toHaveCount(0);
  await expect(averageSection.getByText("Promedio anual")).toHaveCount(0);
  const servicesAverageRow = averageSection.locator("tbody tr").filter({ hasText: "Servicios" });
  await expect(servicesAverageRow).toContainText("$ 12.345");
  await averageSection.getByRole("button", { name: "Mes en curso" }).click();
  await expect(averageSection.getByRole("button", { name: "Mes en curso ↓" })).toBeVisible();
});

test("processing all selected card lines clears that import from pending imports", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Carga de Resumenes" }).click();
  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../tests/fixtures/bbva_visa_sanitized.pdf");
  await expect(page.getByText("Lineas detectadas")).toBeVisible();
      await expect(page.getByLabel("Categoria COMISION CTA PWORLD", { exact: true })).toHaveValue(/./);
      await expect(page.getByLabel("Categoria DEV COMISION CTA PWORLD", { exact: true })).toHaveValue(/./);

  const activeImport = page.locator("[data-testid^='active-import-']");
  const activeImportTestId = await activeImport.getAttribute("data-testid");
  expect(activeImportTestId).toBeTruthy();
  const batchId = activeImportTestId!.replace("active-import-", "");
  await page.getByRole("button", { name: /Procesar/ }).click();
  await expect(page.getByTestId(`active-import-${batchId}`)).toHaveCount(0);
  await expect(page.getByTestId(`pending-import-${batchId}`)).toHaveCount(0);
  await page.getByRole("button", { name: "Resumen" }).click();
  await expect(page.getByRole("heading", { name: "Proyeccion recurrente" })).toBeVisible();
  await expect(page.getByText("OPENAI *CHATGPT SUBSCR")).toBeVisible();

  const expensesResponse = await request.get("http://127.0.0.1:8000/households/1/expenses", {
    headers: { "X-Test-User-Email": "mauro@example.test" }
  });
  expect(expensesResponse.ok()).toBeTruthy();
  const expenses = await expensesResponse.json();
  const maintenanceLines = expenses.filter((expense: { description: string }) =>
    expense.description.includes("COMISION CTA PWORLD")
  );
  expect(maintenanceLines).toHaveLength(2);
  expect(new Set(maintenanceLines.map((expense: { category_id: number | null }) => expense.category_id)).size).toBe(1);
  const net = maintenanceLines.reduce((sum: number, expense: { original_amount: string | number }) => sum + Number(expense.original_amount), 0);
  expect(net).toBe(0);
});

test("re-uploading a parsed but uncommitted statement keeps lines visible with a warning", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Carga de Resumenes" }).click();
  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../tests/fixtures/bbva_visa_sanitized.pdf");
  await expect(page.getByText("OPENAI *CHATGPT SUBSCR")).toBeVisible();
  await expect(page.getByText("Importaciones no finalizadas")).toBeVisible();

  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../tests/fixtures/bbva_visa_sanitized.pdf");
  await expect(page.getByText("OPENAI *CHATGPT SUBSCR")).toBeVisible();
  await expect(page.getByText(/parseadas pero no convertidas/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /Procesar/ })).toBeVisible();
});

test("pending parsed imports can be deleted after confirmation", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Carga de Resumenes" }).click();
  const pendingRows = page.locator(".pending-import-row");

  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../tests/fixtures/bbva_visa_sanitized.pdf");
  await expect(page.getByText("Importaciones no finalizadas")).toBeVisible();
  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../tests/fixtures/bbva_visa_sanitized.pdf");
  await expect(page.getByText(/parseadas pero no convertidas/i)).toBeVisible();
  await expect(pendingRows.first()).toBeVisible();
  const deletedRowTestId = await pendingRows.first().getAttribute("data-testid");
  expect(deletedRowTestId).toBeTruthy();

  page.once("dialog", async (dialog) => {
    expect(dialog.message()).toContain("Borrar la importacion");
    await dialog.accept();
  });
  await pendingRows.first().getByRole("button", { name: "Borrar importacion" }).click();
  await expect(page.getByTestId(deletedRowTestId!)).toHaveCount(0);

  await pendingRows.first().getByRole("button", { name: "Continuar" }).click();
  await expect(page.getByText("Lineas detectadas")).toBeVisible();
});

test("partially processed imports can be removed from pending imports", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Carga de Resumenes" }).click();
  const pendingRows = page.locator(".pending-import-row");

  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../tests/fixtures/bbva_visa_sanitized.pdf");
  await expect(page.getByText("Lineas detectadas")).toBeVisible();

  const selectableLines = page.locator('tbody input[type="checkbox"]:enabled');
  const selectableCount = await selectableLines.count();
  expect(selectableCount).toBeGreaterThan(1);
  for (let index = 1; index < selectableCount; index += 1) {
    await selectableLines.nth(index).uncheck();
  }
  await expect(page.getByRole("button", { name: "Procesar 1 lineas" })).toBeVisible();
  await page.getByRole("button", { name: "Procesar 1 lineas" }).click();

  await expect(pendingRows.first()).toBeVisible();
  const deletedRowTestId = await pendingRows.first().getAttribute("data-testid");
  expect(deletedRowTestId).toBeTruthy();
  page.once("dialog", async (dialog) => {
    await dialog.accept();
  });
  await pendingRows.first().getByRole("button", { name: "Borrar importacion" }).click();
  await expect(page.getByTestId(deletedRowTestId!)).toHaveCount(0);
  await expect(page.getByText("No se pudo borrar la importacion")).toHaveCount(0);
});

test("deselected import lines are ignored and never created as expenses", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Carga de Resumenes" }).click();
  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../tests/fixtures/bbva_visa_sanitized.pdf");
  await expect(page.getByText("Lineas detectadas")).toBeVisible();

  const activeImport = page.locator("[data-testid^='active-import-']");
  const activeImportTestId = await activeImport.getAttribute("data-testid");
  expect(activeImportTestId).toBeTruthy();
  const batchId = activeImportTestId!.replace("active-import-", "");
  const batchResponse = await request.get(`http://127.0.0.1:8000/households/1/imports/${batchId}`, {
    headers: { "X-Test-User-Email": "mauro@example.test" }
  });
  expect(batchResponse.ok()).toBeTruthy();
  const batch = await batchResponse.json();
  const rejectedLine = batch.lines.find((line: { status: string; duplicate_status: string; kind: string }) =>
    line.status === "pending" && line.duplicate_status === "new" && line.kind === "purchase"
  );
  expect(rejectedLine).toBeTruthy();

  await page.getByTestId(`import-line-${rejectedLine.id}`).locator('td:first-child input[type="checkbox"]').uncheck();
  await page.getByRole("button", { name: /Procesar/ }).click();
  await expect(page.getByTestId(`active-import-${batchId}`)).toHaveCount(0);

  const refreshedBatch = await request.get(`http://127.0.0.1:8000/households/1/imports/${batchId}`, {
    headers: { "X-Test-User-Email": "mauro@example.test" }
  });
  expect(refreshedBatch.ok()).toBeTruthy();
  const updatedBatch = await refreshedBatch.json();
  const updatedRejectedLine = updatedBatch.lines.find((line: { id: number }) => line.id === rejectedLine.id);
  expect(updatedRejectedLine.status).toBe("ignored");

  const expensesResponse = await request.get("http://127.0.0.1:8000/households/1/expenses", {
    headers: { "X-Test-User-Email": "mauro@example.test" }
  });
  expect(expensesResponse.ok()).toBeTruthy();
  const expenses = await expensesResponse.json();
  expect(expenses.some((expense: { import_line_id: number | null }) => expense.import_line_id === rejectedLine.id)).toBe(false);
});

test("account movement import classifies bank statement lines", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Carga de Resumenes" }).click();
  await page.getByLabel("Elegir movimientos de cuenta XLS").setInputFiles("../Detalle_mov_cuenta_03_07_2026.xls");
  await expect(page.getByText("Lineas detectadas")).toBeVisible();
  await expect(page.getByText(/Ingresos ARS/).first()).toBeVisible();
  await expect(page.getByText("Debito").first()).toBeVisible();
  await expect(page.getByLabel(/Categoria PAGO DE SERVICIOS TARJETA/).first()).toHaveValue(/./);
  await expect(page.getByText("Ingreso").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Procesar/ })).toBeVisible();
});

test("history import summary shows account statement coverage by month", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Carga de Resumenes" }).click();
  await page.getByLabel("Elegir movimientos de cuenta XLS").setInputFiles("../Detalle_mov_cuenta_03_07_2026.xls");
  await expect(page.getByText("Lineas detectadas")).toBeVisible();
  await page.getByRole("button", { name: "Historial" }).click();
  await page.getByRole("button", { name: "Resumen de importaciones" }).click();
  await expect(page.getByRole("heading", { name: "Cargas 2026" })).toBeVisible();
  await expect(page.getByText("Statement cuenta")).toBeVisible();
  await expect(page.getByText("Mauro")).toBeVisible();
  await expect(page.getByText("Pendiente").first()).toBeVisible();
});

test("house settings allow creating, editing, and deleting subcategories without deleting associated expenses", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Casa" }).click();
  await expect(page.getByRole("button", { name: "Cargar configuracion por defecto" })).toBeVisible();
  await expect(page.getByText("Compras del hogar")).toHaveCount(0);
  await expect(page.getByText("Herramientas")).toHaveCount(0);
  await page.getByRole("button", { name: "Cargar configuracion por defecto" }).click();
  await expect(page.getByText("Compras del hogar")).toHaveCount(0);
  await expect(page.getByText("Herramientas")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Subcategorias" })).toBeVisible();
  await page.getByLabel("Categoria para subcategorias").selectOption({ label: "Servicios" });
  await expect(page.getByText("Electricidad")).toBeVisible();
  await page.getByLabel("Nueva subcategoria").fill("Limpieza patio");
  await page.getByRole("button", { name: "Agregar" }).last().click();
  await expect(page.getByText("Limpieza patio")).toBeVisible();
  const limpiezaRow = page.locator(".category-row").filter({ hasText: "Limpieza patio" });
  await limpiezaRow.getByRole("button", { name: "Editar subcategoria" }).click();
  await page.getByLabel("Nombre subcategoria Limpieza patio").fill("Limpieza patio mensual");
  await page.getByTitle("Guardar subcategoria").click();
  await expect(page.getByText("Limpieza patio mensual")).toBeVisible();

  const categoriesResponse = await request.get("http://127.0.0.1:8000/households/1/categories", {
    headers: { "X-Test-User-Email": "mauro@example.test" }
  });
  expect(categoriesResponse.ok()).toBeTruthy();
  const categories = await categoriesResponse.json() as Array<{ id: number; name: string; subcategories: Array<{ id: number; name: string }> }>;
  const homeCategory = categories.find((category) => category.name === "Servicios");
  expect(homeCategory).toBeTruthy();
  const subcategory = homeCategory!.subcategories.find((item) => item.name === "Limpieza patio mensual");
  expect(subcategory).toBeTruthy();

  await request.post("http://127.0.0.1:8000/households/1/expenses", {
    headers: { "X-Test-User-Email": "mauro@example.test" },
    data: {
      date: "2026-07-06",
      description: "Gasto con subcategoria borrable",
      category_id: homeCategory!.id,
      subcategory_id: subcategory!.id,
      paid_by_user_id: 1,
      currency: "ARS",
      original_amount: "4200.00",
      source: "manual"
    }
  });

  const editedRow = page.locator(".category-row").filter({ hasText: "Limpieza patio mensual" });
  page.once("dialog", async (dialog) => {
    await dialog.accept();
  });
  await editedRow.getByRole("button", { name: "Eliminar subcategoria Limpieza patio mensual" }).click();
  await expect(editedRow).toHaveCount(0);

  const expensesResponse = await request.get("http://127.0.0.1:8000/households/1/expenses", {
    headers: { "X-Test-User-Email": "mauro@example.test" }
  });
  expect(expensesResponse.ok()).toBeTruthy();
  const expenses = await expensesResponse.json() as Array<{ description: string; category_id: number | null; subcategory_id: number | null }>;
  const expense = expenses.find((item) => item.description === "Gasto con subcategoria borrable");
  expect(expense).toBeTruthy();
  expect(expense!.category_id).toBe(homeCategory!.id);
  expect(expense!.subcategory_id).toBeNull();
});

test("house settings manage Mercado Pago integration with mocked API", async ({ page }) => {
  let connected = false;
  await page.route("**/households/1/mercadopago/integrations", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          user_id: 1,
          connected,
          enabled: connected,
          mp_user_id: connected ? "123456" : null,
          mp_nickname: connected ? "mauro-mp" : null,
          mp_site_id: connected ? "MLA" : null,
          last_sync_at: connected ? "2026-08-28T12:00:00" : null,
          last_sync_status: connected ? "ok" : null,
          last_sync_error: null,
          last_report_file_name: connected ? "settlement-report-test.csv" : null,
          updated_at: connected ? "2026-08-28T12:00:00" : null
        },
        {
          user_id: 2,
          connected: false,
          enabled: false,
          mp_user_id: null,
          mp_nickname: null,
          mp_site_id: null,
          last_sync_at: null,
          last_sync_status: null,
          last_sync_error: null,
          last_report_file_name: null,
          updated_at: null
        }
      ])
    });
  });
  await page.route("**/households/1/mercadopago/integrations/1", async (route) => {
    if (route.request().method() === "PUT") {
      connected = true;
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          user_id: 1,
          connected: true,
          enabled: true,
          mp_user_id: "123456",
          mp_nickname: "mauro-mp",
          mp_site_id: "MLA",
          last_sync_at: null,
          last_sync_status: "connected",
          last_sync_error: null,
          last_report_file_name: null,
          updated_at: "2026-08-28T12:00:00"
        })
      });
      return;
    }
    connected = false;
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true }) });
  });
  await page.route("**/households/1/mercadopago/integrations/1/sync", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ batch_id: 9, report_file_name: "settlement-report-test.csv", imported: 4, ignored: 1, duplicates: 0 })
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Casa" }).click();
  await expect(page.getByRole("heading", { name: "Mercado Pago" })).toBeVisible();
  await page.getByLabel("Access Token Mercado Pago Mauro").fill("APP_USR-valid-token");
  await page.getByRole("button", { name: "Conectar" }).first().click();
  await expect(page.getByText("mauro-mp")).toBeVisible();
  await expect(page.getByText("settlement-report-test.csv")).toBeVisible();
  await page.getByRole("button", { name: "Sincronizar ahora" }).first().click();
  page.once("dialog", async (dialog) => {
    await dialog.accept();
  });
  await page.getByLabel("Desconectar Mercado Pago Mauro").click();
  await expect(page.getByText("No conectado").first()).toBeVisible();
});

test("receipt lab parses a Jumbo OCR text ticket without creating a duplicate expense", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Tickets" }).click();
  await expect(page.getByRole("heading", { name: "Tickets de compras" })).toBeVisible();
  await page.getByLabel("Subir ticket").setInputFiles("../tests/fixtures/jumbo_receipt_sanitized.txt");
  await expect(page.getByRole("heading", { name: "Items del ticket" })).toBeVisible();
  await expect(page.locator('input[value="Papas chips crema y cebolla 140gr C&Co"]')).toBeVisible();
  await expect(page.getByText("Total seleccionado $")).toBeVisible();
  await expect(page.getByLabel("Categoria del ticket")).toBeVisible();

  await page.getByLabel(/Aceptar item Papas chips/).uncheck();
  await expect(page.getByText("Ignorado")).toBeVisible();
  await page.getByRole("button", { name: "Guardar revision" }).click();
  await expect(page.getByRole("heading", { name: "Asociacion de tickets a gastos" })).toBeVisible();
  await expect(page.getByText("jumbo_receipt_sanitized.txt")).toBeVisible();
  await page.getByLabel(/Categoria para ticket jumbo_receipt_sanitized.txt/).selectOption({ label: "Servicios" });
  await page.getByLabel(/Gasto para ticket jumbo_receipt_sanitized.txt/).selectOption({ index: 1 });
  await page.getByRole("button", { name: "Asociar" }).click();
  await expect(page.getByText("No hay tickets pendientes de asociacion.")).toBeVisible();
});

test("main screens have stable visual snapshots", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Resumen de consumos" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Consumo acumulado/ })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await expect(page).toHaveScreenshot(`dashboard-${testInfo.project.name}.png`, { fullPage: true });

  await page.getByRole("button", { name: "Consumos" }).click();
  await expect(page).toHaveScreenshot(`expenses-${testInfo.project.name}.png`, { fullPage: true });

  await page.getByRole("button", { name: "Carga de Resumenes" }).click();
  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../tests/fixtures/bbva_visa_sanitized.pdf");
  await expect(page.getByText("Lineas detectadas")).toBeVisible();
  await expect(page).toHaveScreenshot(`imports-${testInfo.project.name}.png`, { fullPage: true });

  await page.getByRole("button", { name: "Efectivo" }).click();
  await expect(page).toHaveScreenshot(`cash-${testInfo.project.name}.png`, { fullPage: true });
});
