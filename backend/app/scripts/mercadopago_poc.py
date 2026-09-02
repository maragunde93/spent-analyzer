import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.services.mercadopago import MercadoPagoClient, parse_report_csv, validate_required_columns


async def main() -> None:
    parser = argparse.ArgumentParser(description="POC manual para Account Money Report de Mercado Pago.")
    parser.add_argument("--access-token", required=True)
    parser.add_argument("--begin", required=True, help="Inicio ISO, por ejemplo 2026-08-01T00:00:00Z")
    parser.add_argument("--end", required=True, help="Fin ISO, por ejemplo 2026-08-03T23:59:59Z")
    parser.add_argument("--out", default="mercadopago-report.csv")
    args = parser.parse_args()

    settings = get_settings()
    client = MercadoPagoClient(
        args.access_token,
        api_base_url=settings.mercadopago_api_base_url,
        identity_base_url=settings.mercadopago_identity_base_url,
    )
    account = await client.validate_token()
    print(f"Token OK. Cuenta: id={account.mp_user_id} nickname={account.nickname} site={account.site_id}")

    begin = _parse_iso(args.begin)
    end = _parse_iso(args.end)
    created = await client.create_report(begin, end)
    print(f"Reporte solicitado: {created}")
    report = await client.wait_for_report(begin, end, created)
    print(f"Reporte listo: {report.file_name}")

    content = await client.download_report(report.file_name)
    output = Path(args.out)
    output.write_bytes(content)
    print(f"Archivo descargado en {output.resolve()}")

    missing = validate_required_columns(content)
    if missing:
        print(f"Columnas requeridas ausentes: {', '.join(sorted(missing))}")
    movements = parse_report_csv(content)
    print(f"Movimientos parseados: {len(movements)}")
    for movement in movements[:20]:
        print(
            f"{movement.date} | {movement.kind.value} | {movement.currency.value} {movement.amount} | "
            f"{movement.description} | ignorado={movement.ignored_reason or '-'}"
        )


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


if __name__ == "__main__":
    asyncio.run(main())
