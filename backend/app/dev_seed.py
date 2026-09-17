from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.api.households import apply_default_categories, purge_obsolete_default_categories
from app.config import get_settings
from app.domain import Currency, ExpenseSource, ImportLineKind
from app.models import CashWalletEntry, Category, Expense, FxRate, HomeGroup, ImportBatch, ImportLine, Membership, Merchant, RecurringRule, Subcategory, User


def seed_development_data(db: Session) -> None:
    settings = get_settings()
    mauro = _get_or_create_user(db, "mauro@example.test", "Mauro")
    mica = _get_or_create_user(db, "mica@example.test", "Mica")
    group = db.scalar(select(HomeGroup).where(HomeGroup.name == "Casa Adrogue"))
    if group is None:
        group = HomeGroup(name="Casa Adrogue")
        db.add(group)
        db.flush()

    for user, role in [(mauro, "owner"), (mica, "member")]:
        exists = db.scalar(select(Membership.id).where(Membership.user_id == user.id, Membership.home_group_id == group.id))
        if exists is None:
            db.add(Membership(user_id=user.id, home_group_id=group.id, role=role))

    purge_obsolete_default_categories(group.id, db)
    if db.scalar(select(Category.id).where(Category.home_group_id == group.id)) is None and settings.seed_demo_data:
        apply_default_categories(group.id, db)

    category_by_name = {
        category.name: category
        for category in db.scalars(select(Category).where(Category.home_group_id == group.id))
    }

    _merge_category(db, group.id, "Operacion MEP", "Servicios")
    _merge_category(db, group.id, "Mantenimiento cuenta", "Servicios")
    services = category_by_name.get("Servicios")
    subscriptions = category_by_name.get("Suscripciones")
    if services is not None:
        db.execute(
            update(Expense)
            .where(Expense.home_group_id == group.id, Expense.description.ilike("%MANTENIMIENTO DE CUENTA%"))
            .values(category_id=services.id)
        )
        db.execute(
            update(Expense)
            .where(Expense.home_group_id == group.id, Expense.description.ilike("%COMISION CTA PWORLD%"))
            .values(category_id=services.id)
        )
    if subscriptions is not None:
        db.execute(
            update(Expense)
            .where(Expense.home_group_id == group.id, Expense.category_id == subscriptions.id)
            .values(is_recurring=True)
        )

    if not settings.seed_demo_data:
        db.commit()
        return

    if db.scalar(select(FxRate.id).where(FxRate.date == date(2026, 5, 1), FxRate.source == "blue_average")) is None:
        db.add(FxRate(date=date(2026, 5, 1), source="blue_average", rate=Decimal("1000.00")))

    _card_expense(db, group.id, mauro.id, mauro.id, "visa-mauro-demo", "2026-03", date(2026, 3, 10), "PEDIDOSYA*PIZZA CLUB", "Delivery", Decimal("31800.00"), category_by_name)
    _card_expense(db, group.id, mauro.id, mauro.id, "visa-mauro-demo", "2026-03", date(2026, 3, 12), "OPENAI *CHATGPT SUBSCR", "Suscripciones", Decimal("20.00"), category_by_name, currency=Currency.USD, amount_ars=Decimal("20000.00"), is_recurring=True)
    _card_expense(db, group.id, mauro.id, mauro.id, "visa-mauro-demo", "2026-03", date(2026, 3, 16), "EDESUR", "Servicios", Decimal("127135.77"), category_by_name, subcategory_name="Electricidad", is_recurring=True)
    _card_expense(db, group.id, mica.id, mica.id, "visa-mica-demo", "2026-03", date(2026, 3, 20), "FARMACITY MICA", "Salud", Decimal("18450.00"), category_by_name)
    _expense(db, group.id, mica.id, mica.id, date(2026, 3, 25), "SUBE RECARGA", "Transporte", Decimal("12000.00"), category_by_name, source=ExpenseSource.manual)

    _card_expense(db, group.id, mauro.id, mauro.id, "visa-mauro-demo", "2026-04", date(2026, 4, 8), "CARREFOUR MARKET", "Sin categoria", Decimal("108320.45"), category_by_name)
    _card_expense(db, group.id, mauro.id, mauro.id, "visa-mauro-demo", "2026-04", date(2026, 4, 12), "OPENAI *CHATGPT SUBSCR", "Suscripciones", Decimal("20.00"), category_by_name, currency=Currency.USD, amount_ars=Decimal("22000.00"), is_recurring=True)
    _card_expense(db, group.id, mauro.id, mauro.id, "visa-mauro-demo", "2026-04", date(2026, 4, 18), "MOVISTAR HOGAR", "Servicios", Decimal("47759.99"), category_by_name, subcategory_name="Internet", is_recurring=True)
    _card_expense(db, group.id, mica.id, mica.id, "visa-mica-demo", "2026-04", date(2026, 4, 19), "STEAM GAMES", "Ocio / gasto personal", Decimal("14900.00"), category_by_name)
    _expense(db, group.id, mica.id, mica.id, date(2026, 4, 26), "NAFTA SHELL", "Auto", Decimal("45200.00"), category_by_name, source=ExpenseSource.manual, subcategory_name="Combustible")

    _card_expense(db, group.id, mauro.id, mauro.id, "visa-mauro-demo", "2026-05", date(2026, 5, 30), "PEDIDOSYA*THOUSAND BURG", "Delivery", Decimal("39380.00"), category_by_name)
    _card_expense(db, group.id, mauro.id, mauro.id, "visa-mauro-demo", "2026-05", date(2026, 5, 14), "DISCO SM 037", "Sin categoria", Decimal("163472.90"), category_by_name)
    _card_expense(
        db,
        group.id,
        mauro.id,
        mauro.id,
        "visa-mauro-demo",
        "2026-05",
        date(2026, 5, 12),
        "OPENAI *CHATGPT SUBSCR",
        "Suscripciones",
        Decimal("20.00"),
        category_by_name,
        currency=Currency.USD,
        amount_ars=Decimal("20000.00"),
        is_recurring=True,
    )
    _card_expense(db, group.id, mica.id, mica.id, "visa-mica-demo", "2026-05", date(2026, 5, 9), "FARMACITY MICA", "Salud", Decimal("18500.00"), category_by_name)
    _expense(db, group.id, mica.id, mica.id, date(2026, 5, 16), "CARREFOUR EXPRESS", "Sin categoria", Decimal("62240.50"), category_by_name, source=ExpenseSource.manual)
    _expense(db, group.id, mica.id, mica.id, date(2026, 5, 22), "CABIFY VIAJE", "Transporte", Decimal("7400.00"), category_by_name, source=ExpenseSource.manual)

    if db.scalar(select(CashWalletEntry.id).where(CashWalletEntry.home_group_id == group.id)) is None:
        db.add_all(
            [
                CashWalletEntry(
                    home_group_id=group.id,
                    user_id=mauro.id,
                    date=date(2026, 5, 20),
                    description="Extraccion cajero",
                    currency=Currency.ARS,
                    amount=Decimal("100000.00"),
                ),
                CashWalletEntry(
                    home_group_id=group.id,
                    user_id=mica.id,
                    date=date(2026, 5, 21),
                    description="Efectivo inicial",
                    currency=Currency.ARS,
                    amount=Decimal("50000.00"),
                ),
            ]
        )

    if db.scalar(select(RecurringRule.id).where(RecurringRule.home_group_id == group.id)) is None:
        db.add_all(
            [
                RecurringRule(home_group_id=group.id, description_pattern="Movistar Hogar", expected_amount=Decimal("47759.99")),
                RecurringRule(home_group_id=group.id, description_pattern="OSDE", expected_amount=Decimal("202741.53")),
            ]
        )

    db.commit()


def _merge_category(db: Session, home_group_id: int, source_name: str, target_name: str) -> None:
    source = db.scalar(select(Category).where(Category.home_group_id == home_group_id, Category.name == source_name))
    target = db.scalar(select(Category).where(Category.home_group_id == home_group_id, Category.name == target_name))
    if source is None or target is None or source.id == target.id:
        return
    db.execute(update(Expense).where(Expense.category_id == source.id).values(category_id=target.id))
    db.execute(update(ImportLine).where(ImportLine.suggested_category_id == source.id).values(suggested_category_id=target.id))
    db.execute(update(RecurringRule).where(RecurringRule.category_id == source.id).values(category_id=target.id))
    db.execute(update(Merchant).where(Merchant.category_id == source.id).values(category_id=target.id))
    db.execute(delete(Subcategory).where(Subcategory.category_id == source.id))
    db.delete(source)


def _get_or_create_user(db: Session, email: str, display_name: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        return user
    user = User(email=email, display_name=display_name)
    db.add(user)
    db.flush()
    return user


def _expense(
    db: Session,
    home_group_id: int,
    paid_by_user_id: int,
    uploaded_by_user_id: int,
    expense_date: date,
    description: str,
    category_name: str,
    amount: Decimal,
    categories: dict[str, Category],
    currency: Currency = Currency.ARS,
    amount_ars: Decimal | None = None,
    source: ExpenseSource = ExpenseSource.import_pdf,
    subcategory_name: str | None = None,
    import_line_id: int | None = None,
    is_recurring: bool | None = None,
) -> None:
    category = categories.get(category_name)
    if category is None:
        return
    subcategory_id = _subcategory_id(db, home_group_id, category.id, subcategory_name) if subcategory_name else None
    exists = db.scalar(
        select(Expense.id).where(
            Expense.home_group_id == home_group_id,
            Expense.date == expense_date,
            Expense.description == description,
            Expense.paid_by_user_id == paid_by_user_id,
        )
    )
    if exists is not None:
        return
    db.add(
        Expense(
            home_group_id=home_group_id,
            date=expense_date,
            description=description,
            category_id=category.id,
            subcategory_id=subcategory_id,
            paid_by_user_id=paid_by_user_id,
            uploaded_by_user_id=uploaded_by_user_id,
            source=source,
            currency=currency,
            original_amount=amount,
            amount_ars=amount_ars or amount,
            import_line_id=import_line_id,
            is_recurring=(category_name == "Suscripciones") if is_recurring is None else is_recurring,
        )
    )


def _card_expense(
    db: Session,
    home_group_id: int,
    paid_by_user_id: int,
    uploaded_by_user_id: int,
    statement_account: str,
    statement_period: str,
    expense_date: date,
    description: str,
    category_name: str,
    amount: Decimal,
    categories: dict[str, Category],
    currency: Currency = Currency.ARS,
    amount_ars: Decimal | None = None,
    subcategory_name: str | None = None,
    is_recurring: bool | None = None,
) -> None:
    category = categories.get(category_name)
    if category is None:
        return
    batch = _get_or_create_card_batch(db, home_group_id, uploaded_by_user_id, statement_account, statement_period)
    fingerprint = f"demo:{home_group_id}:{statement_account}:{statement_period}:{paid_by_user_id}:{expense_date.isoformat()}:{description}:{currency.value}:{amount}"
    line = db.scalar(select(ImportLine).where(ImportLine.home_group_id == home_group_id, ImportLine.fingerprint == fingerprint))
    if line is None:
        paid_by_user = db.get(User, paid_by_user_id)
        line = ImportLine(
            import_batch_id=batch.id,
            home_group_id=home_group_id,
            date=expense_date,
            description=description,
            cardholder_name=paid_by_user.display_name if paid_by_user else None,
            kind=ImportLineKind.purchase,
            currency=currency,
            original_amount=amount,
            suggested_category_id=category.id,
            suggested_subcategory_id=_subcategory_id(db, home_group_id, category.id, subcategory_name) if subcategory_name else None,
            suggested_recurring=(category_name == "Suscripciones") if is_recurring is None else is_recurring,
            status="committed",
            fingerprint=fingerprint,
            raw_text=description,
        )
        db.add(line)
        db.flush()
    _expense(
        db,
        home_group_id,
        paid_by_user_id,
        uploaded_by_user_id,
        expense_date,
        description,
        category_name,
        amount,
        categories,
        currency=currency,
        amount_ars=amount_ars,
        source=ExpenseSource.import_pdf,
        subcategory_name=subcategory_name,
        import_line_id=line.id,
        is_recurring=is_recurring,
    )


def _get_or_create_card_batch(
    db: Session,
    home_group_id: int,
    uploaded_by_user_id: int,
    statement_account: str,
    statement_period: str,
) -> ImportBatch:
    filename = f"demo-{statement_account}-{statement_period}.pdf"
    batch = db.scalar(
        select(ImportBatch).where(
            ImportBatch.home_group_id == home_group_id,
            ImportBatch.filename == filename,
            ImportBatch.statement_account == statement_account,
        )
    )
    if batch is not None:
        return batch
    batch = ImportBatch(
        home_group_id=home_group_id,
        uploaded_by_user_id=uploaded_by_user_id,
        filename=filename,
        source_type="bbva_visa_pdf",
        statement_account=statement_account,
        period_label=statement_period,
        statement_period=statement_period,
        fx_rate_ars_per_usd=Decimal("1000.0000"),
        status="committed",
    )
    db.add(batch)
    db.flush()
    return batch


def _subcategory_id(db: Session, home_group_id: int, category_id: int, name: str | None) -> int | None:
    if not name:
        return None
    return db.scalar(
        select(Subcategory.id).where(
            Subcategory.home_group_id == home_group_id,
            Subcategory.category_id == category_id,
            Subcategory.name == name,
        )
    )
