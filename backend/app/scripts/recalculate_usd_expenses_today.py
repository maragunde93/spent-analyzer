import logging

from app.config import get_settings
from app.database import SessionLocal
from app.services.fx_updater import recalculate_usd_expenses_with_latest_blue_rate, update_blue_rate


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    with SessionLocal() as db:
        rate_result = update_blue_rate(db, api_url=settings.fx_api_url)
        recalc_result = recalculate_usd_expenses_with_latest_blue_rate(db)
    print(
        "Recalculo USD completado: "
        f"{recalc_result['recalculated']} consumos, "
        f"US$ 1 = $ {recalc_result['rate']} "
        f"(fecha {recalc_result['date']}, fuente {rate_result['source']})"
    )


if __name__ == "__main__":
    main()
