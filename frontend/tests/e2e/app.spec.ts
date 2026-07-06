import { expect, test } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8000/test/reset");
});

test("core bills workflow renders and supports import review", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Resumen de consumos" })).toBeVisible();
  await expect(page.getByText("Consumo del mes actual")).toBeVisible();
  await expect(page.getByRole("heading", { name: /Consumo mensual/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Consumo acumulado/ })).toBeVisible();

  await page.getByRole("button", { name: "Gastos" }).click();
  await expect(page.getByRole("heading", { name: "Gastos del hogar" })).toBeVisible();
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
  await page.getByPlaceholder("Buscar gasto").fill("openai");
  await expect(page.getByText("OPENAI *CHATGPT SUBSCR")).toBeVisible();

  await page.getByRole("button", { name: "Importaciones" }).click();
  await expect(page.getByRole("heading", { name: "Importar resumen", exact: true })).toBeVisible();
  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../Statements.pdf");
  await expect(page.getByText("Lineas detectadas")).toBeVisible();
  await expect(page.getByText("OPENAI *CHATGPT SUBSCR")).toBeVisible();
  await expect(page.getByText("Total ARS")).toBeVisible();
  await expect(page.getByText("Total USD")).toBeVisible();
  await expect(page.getByText("Consumos en USD")).toBeVisible();
  await expect(page.getByText("Consumos en ARS")).toBeVisible();
  const usdSeparator = await page.getByText("Consumos en USD").boundingBox();
  const arsSeparator = await page.getByText("Consumos en ARS").boundingBox();
  expect(usdSeparator?.y).toBeLessThan(arsSeparator?.y ?? 0);
  await expect(page.getByRole("button", { name: /Procesar/ })).toBeVisible();
});

test("processing all selected card lines clears that import from pending imports", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Importaciones" }).click();
  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../Statements.pdf");
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
  await page.getByRole("button", { name: "Importaciones" }).click();
  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../Statements.pdf");
  await expect(page.getByText("OPENAI *CHATGPT SUBSCR")).toBeVisible();
  await expect(page.getByText("Importaciones no finalizadas")).toBeVisible();

  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../Statements.pdf");
  await expect(page.getByText("OPENAI *CHATGPT SUBSCR")).toBeVisible();
  await expect(page.getByText(/parseadas pero no convertidas/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /Procesar/ })).toBeVisible();
});

test("pending parsed imports can be deleted after confirmation", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Importaciones" }).click();
  const pendingRows = page.locator(".pending-import-row");

  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../Statements.pdf");
  await expect(page.getByText("Importaciones no finalizadas")).toBeVisible();
  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../Statements.pdf");
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
  await page.getByRole("button", { name: "Importaciones" }).click();
  const pendingRows = page.locator(".pending-import-row");

  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../Statements.pdf");
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

test("account movement import classifies bank statement lines", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Importaciones" }).click();
  await page.getByLabel("Elegir movimientos de cuenta XLS").setInputFiles("../Detalle_mov_cuenta_03_07_2026.xls");
  await expect(page.getByText("Lineas detectadas")).toBeVisible();
  await expect(page.getByText("Debito").first()).toBeVisible();
  await expect(page.getByLabel(/Categoria PAGO DE SERVICIOS TARJETA/).first()).toHaveValue(/./);
  await expect(page.getByText("Ingreso").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Procesar/ })).toBeVisible();
});

test("main screens have stable visual snapshots", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Resumen de consumos" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Consumo acumulado/ })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await expect(page).toHaveScreenshot(`dashboard-${testInfo.project.name}.png`, { fullPage: true });

  await page.getByRole("button", { name: "Gastos" }).click();
  await expect(page).toHaveScreenshot(`expenses-${testInfo.project.name}.png`, { fullPage: true });

  await page.getByRole("button", { name: "Importaciones" }).click();
  await page.getByLabel("Elegir resumen de tarjeta PDF").setInputFiles("../Statements.pdf");
  await expect(page.getByText("Lineas detectadas")).toBeVisible();
  await expect(page).toHaveScreenshot(`imports-${testInfo.project.name}.png`, { fullPage: true });

  await page.getByRole("button", { name: "Efectivo" }).click();
  await expect(page).toHaveScreenshot(`cash-${testInfo.project.name}.png`, { fullPage: true });
});
