import { useMemo } from "react";
import { Check, X } from "lucide-react";
import { buildImportCoverage, importCoverageSources } from "./importCoverage";
import type { ImportCoverageMonth } from "./importCoverage";
import type { ImportBatch, User } from "./types";

const monthNames = Array.from({ length: 12 }, (_, index) =>
  new Intl.DateTimeFormat("es-AR", { month: "long", timeZone: "UTC" }).format(new Date(Date.UTC(2026, index, 1)))
);
const rateFormat = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });

function CoverageCell({ month, users }: { month?: ImportCoverageMonth; users: User[] }) {
  const rates = new Map<string, string[]>();
  for (const source of importCoverageSources) {
    for (const batch of month?.[source] ?? []) {
      if (!batch.fx_rate_ars_per_usd) continue;
      const rate = rateFormat.format(Number(batch.fx_rate_ars_per_usd));
      const sources = rates.get(rate) ?? [];
      if (!sources.includes(source)) sources.push(source);
      rates.set(rate, sources);
    }
  }
  return (
    <div className="import-coverage-cell">
      {importCoverageSources.map((source) => {
        const batches = month?.[source] ?? [];
        const uploaded = batches.length > 0;
        const detail = uploaded ? batches.map((batch) => {
          const uploader = users.find((user) => user.id === batch.uploaded_by_user_id)?.display_name ?? `Usuario #${batch.uploaded_by_user_id}`;
          const processed = batch.status === "committed" ? "Procesado" : "Pendiente de procesamiento";
          return `${batch.filename} · Subió ${uploader} · ${processed}${batch.fx_rate_ars_per_usd ? ` · Blue ${rateFormat.format(Number(batch.fx_rate_ars_per_usd))}` : ""}`;
        }).join("\n") : "Falta subir el resumen";
        return (
          <span
            key={source}
            className={`status import-coverage-tag ${uploaded ? "uploaded" : "missing"}`}
            role="img"
            aria-label={`${source}: ${uploaded ? "subido" : "falta subir"}. ${detail}`}
            title={detail}
          >
            {uploaded ? <Check size={12} aria-hidden="true" /> : <X size={12} aria-hidden="true" />}
            {source}
          </span>
        );
      })}
      {Array.from(rates, ([rate, sources]) => (
        <small className="muted" key={rate} title={`Blue para ${sources.join(", ")}`}>
          {rates.size > 1 ? `${sources.join(" / ")}: ` : ""}Blue {rate}
        </small>
      ))}
    </div>
  );
}

export function ImportCoverageTable({ imports, users }: { imports: ImportBatch[]; users: User[] }) {
  const summary = useMemo(() => buildImportCoverage(imports, users), [imports, users]);
  if (!summary.years.length) return <p className="muted">No hay importaciones con pagador asignado.</p>;
  return (
    <div className="stack">
      <p className="muted import-coverage-legend">
        <span><Check size={14} className="coverage-uploaded-icon" aria-hidden="true" /> Verde: subido</span>
        <span><X size={14} className="coverage-missing-icon" aria-hidden="true" /> Rojo: falta subir</span>
        <span>Pasá sobre una etiqueta para ver quién lo subió y su estado.</span>
      </p>
      <p className="muted import-coverage-note">Solo se incluyen resúmenes con pagador asignado.</p>
      {summary.years.map((year) => (
        <div className="import-coverage" key={year}>
          <h2>Cargas {year}</h2>
          <table aria-label={`Resumen de importaciones ${year}`}>
            <thead>
              <tr>
                <th scope="col">Pagador</th>
                {monthNames.map((name) => <th scope="col" key={name}>{name}</th>)}
              </tr>
            </thead>
            <tbody>
              {summary.rows.map((row) => (
                <tr key={row.paidByUserId}>
                  <th scope="row" className="import-coverage-payer">
                    {users.find((user) => user.id === row.paidByUserId)?.display_name ?? `Usuario #${row.paidByUserId}`}
                  </th>
                  {monthNames.map((_, index) => {
                    const period = `${year}-${String(index + 1).padStart(2, "0")}`;
                    return <td key={period} data-period={period}><CoverageCell month={row.months[period]} users={users} /></td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
