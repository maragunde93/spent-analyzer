from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.api.households import apply_default_categories, purge_obsolete_default_categories
from app.config import get_settings
from app.domain import Currency, ExpenseSource
from app.models import CashWalletEntry, Category, Expense, FxRate, HomeGroup, ImportLine, Membership, Merchant, RecurringRule, Subcategory, User


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

    _expense(db, group.id, mauro.id, mauro.id, date(2026, 5, 30), "PEDIDOSYA*THOUSAND BURG", "Delivery", Decimal("39380.00"), category_by_name)
    _expense(db, group.id, mauro.id, mauro.id, date(2026, 5, 14), "DISCO SM 037", "Sin categoria", Decimal("163472.90"), category_by_name)
    _expense(
        db,
        group.id,
        mauro.id,
        mauro.id,
        date(2026, 5, 12),
        "OPENAI *CHATGPT SUBSCR",
        "Suscripciones",
        Decimal("20.00"),
        category_by_name,
        currency=Currency.USD,
        amount_ars=Decimal("20000.00"),
    )
    _expense(db, group.id, mica.id, mica.id, date(2026, 5, 9), "FARMACITY MICA", "Salud", Decimal("18500.00"), category_by_name)
    _expense(db, group.id, mica.id, mica.id, date(2026, 5, 16), "CARREFOUR EXPRESS", "Sin categoria", Decimal("62240.50"), category_by_name)
    _expense(db, group.id, mica.id, mica.id, date(2026, 5, 22), "CABIFY VIAJE", "Transporte", Decimal("7400.00"), category_by_name)

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
) -> None:
    category = categories.get(category_name)
    if category is None:
        return
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
            paid_by_user_id=paid_by_user_id,
            uploaded_by_user_id=uploaded_by_user_id,
            source=ExpenseSource.import_pdf,
            currency=currency,
            original_amount=amount,
            amount_ars=amount_ars or amount,
            is_recurring=category_name == "Suscripciones",
        )
    )
