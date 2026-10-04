import { expect, test } from "@playwright/test";
import { buildImportCoverage } from "../../src/importCoverage";
import { demoDashboard, users } from "../../src/mockData";
import type { ImportBatch } from "../../src/types";

function batch(overrides: Partial<ImportBatch>): ImportBatch {
  return {
    id: 1, filename: "visa.pdf", source_type: "bbva_visa_pdf", uploaded_by_user_id: 1,
    statement_account: "1111", period_label: "2026-01", statement_period: "2026-01",
    card_network: "visa", fx_rate_ars_per_usd: "1500", status: "committed",
    created_at: "2026-02-01T12:00:00", paid_by_user_ids: [1], lines: [],
    ...overrides
  };
}

const imports = [
  batch({}),
  batch({ id: 2, statement_account: "2222", uploaded_by_user_id: 2, statement_period: "2026-09" }),
  batch({ id: 3, uploaded_by_user_id: 2 }),
  // The parsed network must win over a misleading filename.
  batch({ id: 4, filename: "visa-nombre-antiguo.pdf", card_network: "mastercard", paid_by_user_ids: [1, 2], fx_rate_ars_per_usd: "1515" }),
  batch({ id: 5, source_type: "bbva_account_xls", card_network: null, statement_period: null, lines: [
    { id: 50, date: "2026-02-01", status: "committed", duplicate_status: "new" },
    { id: 51, date: "2026-03-01", status: "committed", duplicate_status: "new" }
  ] as ImportBatch["lines"] }),
  batch({ id: 6, status: "parsed", uploaded_by_user_id: 2, paid_by_user_ids: [], statement_period: "2026-04" }),
  batch({ id: 7, status: "parsed", paid_by_user_ids: [], statement_period: "2026-05" }),
  batch({ id: 8, statement_period: "2025-12" }),
  batch({ id: 9, status: "parsed", paid_by_user_ids: [2], statement_period: "2026-06" })
];

test("coverage groups only by payer and keeps uploads, networks, periods and FX metadata", () => {
  const members = [...users, { ...users[0], id: 3, display_name: "Sofi" }];
  const summary = buildImportCoverage(imports, members);
  expect(summary.years).toEqual([2026, 2025]);
  expect(summary.rows.map((row) => row.paidByUserId)).toEqual([1, 2, 3]);
  const mauro = summary.rows[0];
  expect(mauro.months["2026-01"].Visa?.map((item) => item.id)).toEqual([1, 3]);
  expect(mauro.months["2026-09"].Visa?.[0].statement_account).toBe("2222");
  expect(mauro.months["2026-01"].Mastercard?.[0].fx_rate_ars_per_usd).toBe("1515");
  expect(summary.rows[1].months["2026-01"].Mastercard?.[0].id).toBe(4);
  expect(mauro.months["2026-02"].Cuenta).toHaveLength(1);
  expect(mauro.months["2026-03"].Cuenta).toHaveLength(1);
  expect(summary.rows[2].months).toEqual({});
  expect(mauro.months["2026-05"]).toBeUndefined();
  expect(summary.rows[1].months["2026-04"]).toBeUndefined();
  expect(summary.rows[1].months["2026-06"].Visa?.[0].status).toBe("parsed");
});

test("coverage retains uploaded statements even when their lines match a later upload", () => {
  const summary = buildImportCoverage([batch({ lines: [
    { id: 100, date: "2025-12-01", status: "committed", duplicate_status: "already_committed" }
  ] as ImportBatch["lines"] })], users);
  expect(summary.rows[0].months["2026-01"].Visa).toHaveLength(1);
  expect(buildImportCoverage([], users).years).toEqual([]);
  expect(buildImportCoverage([batch({ paid_by_user_ids: [] })], users).years).toEqual([]);
});

test("history shows one payer row with green uploaded badges, red missing badges and upload details", async ({ page }, testInfo) => {
  await page.route(/\/(?:auth\/me|households)(?:[/?]|$)/, async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = [];
    if (path.endsWith("/auth/me")) data = users[0];
    else if (path.endsWith("/households")) data = [{ id: 1, name: "Casa" }];
    else if (path.endsWith("/members")) data = users;
    else if (path.endsWith("/dashboard")) data = demoDashboard;
    else if (path.endsWith("/imports")) data = imports;
    await route.fulfill({ json: data });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Historial", exact: true }).click();
  await page.getByRole("button", { name: "Resumen de importaciones" }).click();
  const table = page.getByRole("table", { name: "Resumen de importaciones 2026" });
  await expect(table.locator("tbody tr")).toHaveCount(2);
  await expect(table.getByRole("columnheader")).toHaveCount(13);
  const mauro = table.getByRole("row").filter({ has: page.getByRole("rowheader", { name: "Mauro", exact: true }) });
  const january = mauro.locator('[data-period="2026-01"]');
  await expect(january.getByRole("img", { name: /^Visa: subido/ })).toHaveClass(/uploaded/);
  await expect(january.getByRole("img", { name: /^Visa: subido/ })).toHaveAttribute("title", /Subió Mica/);
  await expect(january.getByRole("img", { name: /^Mastercard: subido/ })).toHaveClass(/uploaded/);
  await expect(january.getByRole("img", { name: /^Cuenta: falta subir/ })).toHaveClass(/missing/);
  await expect(january).toContainText(/Blue \$\s*1\.500/);
  await expect(january).toContainText(/Blue \$\s*1\.515/);
  await expect(mauro.locator('[data-period="2026-09"] .uploaded')).toHaveCount(1);
  await expect(mauro.locator('[data-period="2026-12"] .missing')).toHaveCount(3);
  await expect(table.getByRole("rowheader", { name: "Sin pagador asignado" })).toHaveCount(0);
  await expect(mauro.locator('[data-period="2026-05"] .uploaded')).toHaveCount(0);
  const mica = table.getByRole("row").filter({ has: page.getByRole("rowheader", { name: "Mica", exact: true }) });
  await expect(mica.locator('[data-period="2026-04"] .uploaded')).toHaveCount(0);
  await expect(mica.locator('[data-period="2026-06"] .uploaded')).toHaveCount(1);
  await expect(mica.locator('[data-period="2026-06"] .uploaded')).toHaveAttribute("title", /Pendiente de procesamiento/);
  await expect(page.getByRole("table", { name: "Resumen de importaciones 2025" })).toBeVisible();
  if (testInfo.project.name === "chromium-desktop") await page.setViewportSize({ width: 1920, height: 960 });
  await page.screenshot({ path: testInfo.outputPath("history-summary.png"), fullPage: true });
});
