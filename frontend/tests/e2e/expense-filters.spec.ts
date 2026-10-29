import { expect, test } from "@playwright/test";
import { categories, demoDashboard, users } from "../../src/mockData";
import type { Expense } from "../../src/types";

function expense(id: number, overrides: Partial<Expense> = {}): Expense {
  return {
    id, date: "2026-09-10", description: `Consumo ${id}`, category_id: 3,
    paid_by_user_id: 1, uploaded_by_user_id: 1, source: "bank_import",
    currency: "ARS", original_amount: "12345.67", amount_ars: "12345.67",
    notes: "Factura familiar", is_recurring: true, is_shared: true, ...overrides
  };
}

const expenses = [
  expense(1, { date: "2026-09-01", description: "Internet hogar" }),
  expense(2, { date: "2026-09-30", description: "Agua hogar" }),
  expense(3, { category_id: 1 }),
  expense(4, {
    source: "mercadopago",
    description: "Compra Mercado Pago con una descripcion larga para revisar el ajuste de texto en la tabla",
    notes: "Nota extensa para verificar que el contenido se ajuste al ancho de su columna sin tapar el importe ni los botones de acciones."
  }),
  expense(5, { is_recurring: false }),
  expense(6, { date: "2026-08-31" }),
  expense(7, { date: "2026-10-01" }),
  expense(8, { paid_by_user_id: 2 }),
  expense(9, { currency: "USD", original_amount: "25.50", amount_ars: "38250.00", notes: null }),
  expense(10, { is_shared: false }),
  expense(11, { category_id: null, is_recurring: undefined, notes: "Reparacion especial" }),
  expense(12, { category_id: 6, is_recurring: false, notes: null })
];

test.beforeEach(async ({ page }) => {
  await page.route(/\/(?:auth\/me|households)(?:[/?]|$)/, async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = [];
    if (path.endsWith("/auth/me")) data = users[0];
    else if (path.endsWith("/households")) data = [{ id: 1, name: "Casa" }];
    else if (path.endsWith("/members")) data = users;
    else if (path.endsWith("/dashboard")) data = demoDashboard;
    else if (path.endsWith("/categories")) data = categories;
    else if (path.endsWith("/expenses")) data = expenses;
    await route.fulfill({ json: data });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Consumos", exact: true }).click();
});

test("sidebar filters combine with existing filters, include date boundaries and filter XLS", async ({ page }, testInfo) => {
  await page.getByLabel("Filtrar por categoria", { exact: true }).selectOption("3");
  await page.getByLabel("Filtrar por origen").selectOption("bank_import");
  await page.getByLabel("Filtrar por recurrente").selectOption("yes");
  await page.getByLabel("Filtrar fecha desde").fill("2026-09-01");
  await page.getByLabel("Filtrar fecha hasta").fill("2026-09-30");
  await page.getByLabel("Filtrar por usuario").selectOption("1");
  await page.getByLabel("Filtrar por moneda").selectOption("ARS");
  await page.getByLabel("Filtrar gastos por alcance").selectOption("shared");
  await page.getByLabel("Buscar gasto").fill(" FACTURA FAMILIAR ");
  await expect(page.locator(".expense-table tbody .description-cell")).toHaveText(["Agua hogar", "Internet hogar"]);
  await expect(page.locator(".table-heading .import-totals")).toContainText("24.691");
  await expect(page.getByRole("button", { name: /Descargar XLS \(2\)/ })).toBeEnabled();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /Descargar XLS/ }).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  let contents = "";
  for await (const chunk of stream) contents += chunk.toString();
  expect(contents.match(/<Row>/g)).toHaveLength(3);
  expect(contents).toContain("Internet hogar");
  expect(contents).toContain("Agua hogar");
  expect(contents).not.toContain("Consumo 3");
  await page.screenshot({ path: testInfo.outputPath("expense-sidebar-filters.png"), fullPage: true });

  await page.getByRole("button", { name: "Resumen", exact: true }).click();
  await page.getByRole("button", { name: "Consumos", exact: true }).click();
  await expect(page.getByLabel("Filtrar por categoria", { exact: true })).toHaveValue("3");
  await expect(page.getByRole("button", { name: /Descargar XLS \(2\)/ })).toBeEnabled();
  await page.getByRole("button", { name: "Limpiar filtros", exact: true }).click();
  await expect(page.getByRole("button", { name: /Descargar XLS \(12\)/ })).toBeEnabled();
  await expect(page.getByLabel("Filtrar fecha desde")).toHaveValue("");
  await expect(page.getByLabel("Filtrar fecha hasta")).toHaveValue("");
  await expect(page.getByLabel("Filtrar por origen")).toHaveValue("all");
  await expect(page.getByLabel("Filtrar por recurrente")).toHaveValue("all");
  await expect(page.getByLabel("Buscar gasto")).toHaveValue("");
});

test("search matches descriptions, raw and formatted amounts and notes; handles uncategorized and nonrecurring expenses", async ({ page }) => {
  const search = page.getByLabel("Buscar gasto");
  await search.fill("internet HOGAR");
  await expect(page.locator(".expense-table tbody .description-cell")).toHaveText(["Internet hogar"]);
  await page.getByRole("button", { name: "Limpiar filtros", exact: true }).click();
  await page.getByLabel("Filtrar por moneda").selectOption("USD");
  for (const query of ["25.50", "25,50", "38250", "38.250"]) {
    await search.fill(query);
    await expect(page.locator(".expense-table tbody .description-cell")).toHaveText(["Consumo 9"]);
  }
  await page.getByRole("button", { name: "Limpiar filtros", exact: true }).click();
  await search.fill("12.345,67");
  await expect(page.getByRole("button", { name: /Descargar XLS \(11\)/ })).toBeEnabled();
  await search.fill("inexistente");
  await expect(page.getByRole("button", { name: /Descargar XLS \(0\)/ })).toBeDisabled();
  await expect(page.getByText("No hay consumos que coincidan con los filtros.")).toBeVisible();
  await page.getByRole("button", { name: "Limpiar filtros", exact: true }).click();
  await page.getByLabel("Filtrar por categoria", { exact: true }).selectOption("uncategorized");
  await page.getByLabel("Filtrar por recurrente").selectOption("no");
  await expect(page.locator(".expense-table tbody .description-cell")).toHaveText(["Consumo 12", "Consumo 11"]);
  await search.fill("reparacion especial");
  await expect(page.locator(".expense-table tbody .description-cell")).toHaveText(["Consumo 11"]);
});

test("filters stay inside their panel and table scrolling does not move totals or overflow the page", async ({ page }, testInfo) => {
  const widths = testInfo.project.name === "chromium-desktop" ? [320, 768, 1024, 1440, 3361] : [393];
  await page.getByLabel("Buscar gasto").fill("Compra Mercado Pago");
  await page.getByLabel("Filtrar fecha desde").fill("2026-09-01");
  await page.getByLabel("Filtrar fecha hasta").fill("2026-09-30");
  for (const width of widths) {
    await page.setViewportSize({ width, height: 1007 });
    // Move focus out of the navigation so its expanding sidebar has settled.
    await page.getByLabel("Buscar gasto").focus();
    const filters = page.locator(".expense-filter-panel");
    const table = page.locator(".expense-table");
    await expect(filters.getByLabel("Filtrar por categoria", { exact: true })).toBeVisible();
    await expect(filters.getByLabel("Filtrar por origen")).toBeVisible();
    await expect(filters.getByLabel("Filtrar por recurrente")).toBeVisible();
    await expect(filters.getByLabel("Filtrar fecha desde")).toBeVisible();
    await expect(filters.getByLabel("Filtrar fecha hasta")).toBeVisible();
    await expect(table.locator("thead input, thead select")).toHaveCount(0);
    const headerBounds = await table.locator("thead").boundingBox();
    expect(headerBounds!.height).toBeLessThan(60);
    const panelBounds = await filters.boundingBox();
    for (const field of await filters.locator("input, select").all()) {
      const bounds = await field.boundingBox();
      expect(bounds!.x).toBeGreaterThanOrEqual(panelBounds!.x);
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(panelBounds!.x + panelBounds!.width);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    const movementsBounds = await page.locator(".expense-movements").boundingBox();
    const newFormBounds = await page.locator(".expense-new-form").boundingBox();
    if (width <= 860) {
      expect(movementsBounds!.y).toBeGreaterThanOrEqual(panelBounds!.y + panelBounds!.height);
      expect(newFormBounds!.y).toBeGreaterThanOrEqual(movementsBounds!.y + movementsBounds!.height);
    } else {
      expect(movementsBounds!.x).toBeGreaterThanOrEqual(panelBounds!.x + panelBounds!.width);
      expect(Math.abs(movementsBounds!.y - panelBounds!.y)).toBeLessThan(1);
    }
    const totals = page.locator(".expense-movements .table-heading");
    const before = await totals.boundingBox();
    const scroll = page.getByRole("region", { name: "Movimientos del hogar" });
    await scroll.evaluate((element) => { element.scrollLeft = element.scrollWidth; });
    expect(await totals.boundingBox()).toEqual(before);
    await expect(page.getByRole("button", { name: /Editar gasto Compra Mercado Pago/ })).toBeVisible();
    await scroll.evaluate((element) => { element.scrollLeft = 0; });
    await page.screenshot({ path: testInfo.outputPath(`expenses-layout-${width}.png`), fullPage: true });
  }
});
