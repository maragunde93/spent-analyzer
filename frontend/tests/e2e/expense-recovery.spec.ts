import { expect, test } from "@playwright/test";
import { categories, demoDashboard, demoImport, users } from "../../src/mockData";

const apiBase = "http://127.0.0.1:8000/households/1";
const headers = { "X-Test-User-Email": "mauro@example.test" };

test.beforeEach(async ({ request }) => {
  expect((await request.post("http://127.0.0.1:8000/test/reset")).ok()).toBeTruthy();
});

test("deleted consumption survives reload in trash and is restored with the same data", async ({ page, request }, testInfo) => {
  const created = await request.post(`${apiBase}/expenses`, { headers, data: {
    date: "2026-10-15", description: "Papelera demo", paid_by_user_id: 1, currency: "ARS",
    original_amount: "2345", source: "cash", notes: "Conservar esta nota", is_shared: true
  } });
  expect(created.ok()).toBeTruthy();
  const expense = await created.json();
  await page.goto("/");
  await page.getByRole("button", { name: "Consumos", exact: true }).click();
  await page.getByLabel("Buscar gasto").fill("Papelera demo");
  await expect(page.locator(".expense-table tbody .description-cell")).toHaveText(["Papelera demo"]);
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByLabel("Eliminar gasto Papelera demo").click();
  await expect(page.locator(".expense-table tbody .description-cell")).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: "Consumos", exact: true }).click();
  await page.getByRole("button", { name: "Ver papelera" }).click();
  const trash = page.getByLabel("Papelera de consumos");
  await expect(trash).toContainText("Papelera demo");
  await trash.screenshot({ path: testInfo.outputPath("expense-trash.png") });
  expect((await (await request.get(`${apiBase}/expenses/trash`, { headers })).json()).find((row: { id: number }) => row.id === expense.id).deleted_at).toBeTruthy();
  await trash.getByRole("button", { name: "Restaurar Papelera demo" }).click();
  await expect(trash).toContainText("La papelera está vacía");
  await page.getByLabel("Buscar gasto").fill("Papelera demo");
  await expect(page.locator(".expense-table tbody .description-cell")).toHaveText(["Papelera demo"]);
  const restored = (await (await request.get(`${apiBase}/expenses`, { headers })).json()).find((row: { id: number }) => row.id === expense.id);
  expect(restored).toMatchObject({ id: expense.id, notes: "Conservar esta nota", is_shared: true, deleted_at: null });
});

for (const knownOwner of [true, false]) {
  test(`card payer defaults to ${knownOwner ? "header owner for every extension" : "uploader when owner is unavailable"}`, async ({ page }) => {
    const expectedPayer = knownOwner ? "1" : "2";
    const pendingBatch = { ...demoImport, id: 888, uploaded_by_user_id: 2,
      owner_name: knownOwner ? "PEREZ MAURO" : null, default_paid_by_user_id: Number(expectedPayer),
      lines: [
        { ...demoImport.lines[0], id: 889, description: "Compra extension", cardholder_name: "Mica", duplicate_status: "new" },
        { ...demoImport.lines[0], id: 890, description: "Compra titular", cardholder_name: "Mauro", duplicate_status: "new" },
        { ...demoImport.lines[0], id: 891, description: "Compra borrada", cardholder_name: "Mica", duplicate_status: "deleted" }
      ]
    };
    let committed: Record<string, unknown> | null = null;
    await page.route(/\/(?:auth\/me|households)(?:[/?]|$)/, async (route) => {
      const path = new URL(route.request().url()).pathname;
      let data: unknown = [];
      if (path.endsWith("/auth/me")) data = users[0];
      else if (path.endsWith("/households")) data = [{ id: 1, name: "Casa" }];
      else if (path.endsWith("/members")) data = [...users].reverse();
      else if (path.endsWith("/dashboard")) data = demoDashboard;
      else if (path.endsWith("/categories")) data = categories;
      else if (path.endsWith("/imports")) data = [pendingBatch];
      else if (path.endsWith("/commit")) { committed = route.request().postDataJSON(); data = { created: 2, processed: 2 }; }
      await route.fulfill({ json: data });
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Carga de Resumenes" }).click();
    await page.getByTestId("pending-import-888").getByRole("button", { name: "Continuar" }).click();
    await expect(page.getByLabel("Pagador del resumen")).toHaveValue(expectedPayer);
    await expect(page.getByLabel("Pagador Mica", { exact: true })).toHaveValue(expectedPayer);
    await expect(page.getByLabel("Pagador Mauro", { exact: true })).toHaveValue(expectedPayer);
    const deleted = page.getByTestId("import-line-891");
    await expect(deleted).toContainText("En papelera");
    await expect(deleted.locator('input[type="checkbox"]').first()).toBeDisabled();
    await page.getByRole("button", { name: "Seleccionar persona" }).first().click();
    await expect(page.getByRole("button", { name: "Procesar 2 lineas" })).toBeEnabled();
    await page.getByLabel("Pagador del resumen").selectOption("2");
    await expect(page.getByLabel("Pagador Mauro", { exact: true })).toHaveValue("2");
    await page.getByLabel("Pagador Mauro", { exact: true }).selectOption("1");
    await page.getByRole("button", { name: "Procesar 2 lineas" }).click();
    await expect.poll(() => committed).toMatchObject({ paid_by_user_id: 2, paid_by_overrides: { "889": 2, "890": 1 } });
  });
}
