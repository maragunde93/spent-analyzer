import type { ImportBatch, User } from "./types";

export const importCoverageSources = ["Visa", "Mastercard", "Cuenta"] as const;
export type ImportCoverageSource = typeof importCoverageSources[number];
export type ImportCoverageMonth = Partial<Record<ImportCoverageSource, ImportBatch[]>>;
type ImportCoverageRow = {
  paidByUserId: number;
  months: Record<string, ImportCoverageMonth>;
};

function importSource(batch: ImportBatch): ImportCoverageSource {
  if (batch.source_type === "bbva_account_xls") return "Cuenta";
  if (batch.card_network?.toLowerCase() === "mastercard") return "Mastercard";
  if (batch.card_network?.toLowerCase() === "visa") return "Visa";
  return batch.filename.toLowerCase().includes("master") ? "Mastercard" : "Visa";
}

export function buildImportCoverage(imports: ImportBatch[], users: User[]) {
  // Account numbers and uploaders are metadata, never part of a payer's row key.
  const rows = new Map<number, ImportCoverageRow>(
    users.map((user) => [user.id, { paidByUserId: user.id, months: {} }])
  );
  const years = new Set<number>();
  const orderedImports = [...imports].sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? "") || a.id - b.id);
  for (const batch of orderedImports) {
    if (!batch.paid_by_user_ids.length) continue;
    const source = importSource(batch);
    const periods = new Set(
      batch.source_type === "bbva_account_xls"
        ? batch.lines.length ? batch.lines.map((line) => line.date.slice(0, 7)) : batch.created_at ? [batch.created_at.slice(0, 7)] : []
        : batch.statement_period ? [batch.statement_period] : batch.created_at ? [batch.created_at.slice(0, 7)] : []
    );
    for (const paidByUserId of new Set(batch.paid_by_user_ids)) {
      if (!rows.has(paidByUserId)) rows.set(paidByUserId, { paidByUserId, months: {} });
      const row = rows.get(paidByUserId)!;
      for (const period of periods) {
        if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(period)) continue;
        years.add(Number(period.slice(0, 4)));
        const month = row.months[period] ?? (row.months[period] = {});
        const batches = month[source] ?? (month[source] = []);
        batches.push(batch);
      }
    }
  }
  return {
    years: Array.from(years).sort((a, b) => b - a),
    rows: Array.from(rows.values())
  };
}
