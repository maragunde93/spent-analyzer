from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_home_member
from app.database import get_db
from app.models import Category, HomeGroup, Membership, Subcategory, User
from app.schemas import CategoryCreate, CategoryRead, CategoryUpdate, HomeGroupRead, MemberRead, SubcategoryCreate, SubcategoryUpdate
from app.services.audit import log_action

router = APIRouter(prefix="/households", tags=["households"])


DEFAULT_CATEGORIES = [
    ("Auto", "#607d8b", "car-front"),
    ("Compras del hogar", "#2171b5", "shopping-cart"),
    ("Delivery", "#41b6e6", "utensils"),
    ("Herramientas", "#3af8c8", "tag"),
    ("Impuestos", "#795548", "landmark"),
    ("Mascotas", "#20d556", "tag"),
    ("Ocio / gasto personal", "#7c4dff", "gamepad"),
    ("Regalos", "#ff5722", "gift"),
    ("Salud", "#009688", "heart-pulse"),
    ("Servicios", "#ff9800", "receipt"),
    ("Sin categoria", "#f44336", "tag"),
    ("Suscripciones", "#ffc107", "repeat"),
    ("Transporte", "#9c27b0", "car"),
    ("Vacaciones", "#4caf50", "plane"),
    ("Vestimenta", "#e91e63", "shirt"),
]

DEFAULT_SUBCATEGORIES = {
    "Auto": ["Combustible", "Mantenimiento", "Patente", "Seguro"],
    "Compras del hogar": [
        "Almacén",
        "Bazar y Hogar",
        "Bebida alcholica",
        "Carnicería",
        "Descuentos",
        "Electrodomestico",
        "Farmacia y Perfumería",
        "Frutas y Verduras",
        "Limpieza",
        "Panadería",
        "Perfumería y Cuidado Personal",
        "Pileta",
        "Repuestos",
        "Verdulería",
    ],
    "Mascotas": ["Alimento", "Juguetes", "Otros", "Piedras", "Veterinaria"],
    "Servicios": ["Agua", "Auto", "Banco", "Electricidad", "Gas", "Internet", "Seguro"],
}


class HomeGroupCreate(BaseModel):
    name: str


@router.get("", response_model=list[HomeGroupRead])
def list_households(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[HomeGroup]:
    return list(
        db.scalars(
            select(HomeGroup)
            .join(Membership)
            .where(Membership.user_id == user.id)
            .order_by(HomeGroup.name)
        )
    )


@router.post("", response_model=HomeGroupRead)
def create_household(payload: HomeGroupCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> HomeGroup:
    group = HomeGroup(name=payload.name)
    db.add(group)
    db.flush()
    db.add(Membership(user_id=user.id, home_group_id=group.id, role="owner"))
    for name, color, icon in DEFAULT_CATEGORIES:
        category = Category(home_group_id=group.id, name=name, color=color, icon=icon, is_system=True)
        db.add(category)
        db.flush()
        for subcategory_name in DEFAULT_SUBCATEGORIES.get(name, []):
            db.add(Subcategory(home_group_id=group.id, category_id=category.id, name=subcategory_name, is_system=True))
    db.commit()
    db.refresh(group)
    return group


@router.get("/{home_group_id}/categories", response_model=list[CategoryRead])
def list_categories(home_group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Category]:
    require_home_member(home_group_id, user, db)
    categories = list(db.scalars(select(Category).where(Category.home_group_id == home_group_id).order_by(Category.name)))
    subcategories = list(db.scalars(select(Subcategory).where(Subcategory.home_group_id == home_group_id).order_by(Subcategory.name)))
    by_category: dict[int, list[Subcategory]] = {}
    for subcategory in subcategories:
        by_category.setdefault(subcategory.category_id, []).append(subcategory)
    for category in categories:
        category.subcategories = by_category.get(category.id, [])
    return categories


@router.get("/{home_group_id}/members", response_model=list[MemberRead])
def list_members(home_group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[MemberRead]:
    memberships = list(
        db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.home_group_id == home_group_id)
            .order_by(User.display_name)
        )
    )
    if not any(member.user_id == user.id for member, _ in memberships):
        return []
    return [
        MemberRead(id=member_user.id, email=member_user.email, display_name=member_user.display_name, role=member.role)
        for member, member_user in memberships
    ]


@router.post("/{home_group_id}/categories", response_model=CategoryRead)
def create_category(home_group_id: int, payload: CategoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Category:
    require_home_member(home_group_id, user, db)
    category = Category(home_group_id=home_group_id, name=payload.name, color=payload.color, icon=payload.icon)
    db.add(category)
    db.flush()
    log_action(db, home_group_id, user.id, "category_create", "category", category.name, category.id)
    db.commit()
    db.refresh(category)
    return category


@router.put("/{home_group_id}/categories/{category_id}", response_model=CategoryRead)
def update_category(home_group_id: int, category_id: int, payload: CategoryUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Category:
    require_home_member(home_group_id, user, db)
    category = db.get(Category, category_id)
    if category is None or category.home_group_id != home_group_id:
        raise HTTPException(status_code=404, detail="Categoria no encontrada")
    category.name = payload.name
    category.color = payload.color
    category.icon = payload.icon
    log_action(db, home_group_id, user.id, "category_update", "category", category.name, category.id)
    db.commit()
    db.refresh(category)
    category.subcategories = list(db.scalars(select(Subcategory).where(Subcategory.category_id == category.id).order_by(Subcategory.name)))
    return category


@router.post("/{home_group_id}/subcategories", response_model=CategoryRead)
def create_subcategory(home_group_id: int, payload: SubcategoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Category:
    require_home_member(home_group_id, user, db)
    category = db.get(Category, payload.category_id)
    if category is None or category.home_group_id != home_group_id:
        raise HTTPException(status_code=404, detail="Categoria no encontrada")
    subcategory_name = payload.name.strip()
    existing = db.scalar(
        select(Subcategory).where(
            Subcategory.home_group_id == home_group_id,
            Subcategory.category_id == category.id,
            Subcategory.name == subcategory_name,
        )
    )
    if existing is not None:
        category.subcategories = list(db.scalars(select(Subcategory).where(Subcategory.category_id == category.id).order_by(Subcategory.name)))
        return category
    subcategory = Subcategory(home_group_id=home_group_id, category_id=category.id, name=subcategory_name, is_system=False)
    db.add(subcategory)
    db.flush()
    log_action(db, home_group_id, user.id, "subcategory_create", "subcategory", subcategory.name, subcategory.id)
    db.commit()
    db.refresh(category)
    category.subcategories = list(db.scalars(select(Subcategory).where(Subcategory.category_id == category.id).order_by(Subcategory.name)))
    return category


@router.put("/{home_group_id}/subcategories/{subcategory_id}", response_model=CategoryRead)
def update_subcategory(home_group_id: int, subcategory_id: int, payload: SubcategoryUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Category:
    require_home_member(home_group_id, user, db)
    subcategory = db.get(Subcategory, subcategory_id)
    if subcategory is None or subcategory.home_group_id != home_group_id:
        raise HTTPException(status_code=404, detail="Subcategoria no encontrada")
    category = db.get(Category, subcategory.category_id)
    if category is None or category.home_group_id != home_group_id:
        raise HTTPException(status_code=404, detail="Categoria no encontrada")
    subcategory.name = payload.name.strip()
    log_action(db, home_group_id, user.id, "subcategory_update", "subcategory", subcategory.name, subcategory.id)
    db.commit()
    db.refresh(category)
    category.subcategories = list(db.scalars(select(Subcategory).where(Subcategory.category_id == category.id).order_by(Subcategory.name)))
    return category
