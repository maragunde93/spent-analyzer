from dataclasses import dataclass


DEFAULT_RULES = {
    "CR IVA $ 21": "Impuestos",
    "DB IVA $ 21": "Impuestos",
    "IIBB PERCEP-CABA": "Impuestos",
    "IVA RG": "Impuestos",
    "DB.RG": "Impuestos",
    "CR.RG": "Impuestos",
    "COMISION CTA PWORLD": "Servicios",
    "DEV COMISION CTA PWORLD": "Servicios",
    "CAJA SEG": "Auto",
    "PEDIDOSYA": "Delivery",
    "DLO*PEDIDOSYA": "Delivery",
    "MOVISTAR": "Servicios",
    "CLARO": "Servicios",
    "EDESUR": "Servicios",
    "EDENOR": "Servicios",
    "METROGAS": "Servicios",
    "PAGO DE SERVICIOS TARJETA": "Servicios",
    "OSDE": "Salud",
    "STEAM": "Ocio / gasto personal",
    "OPENAI": "Suscripciones",
    "AMAZON PRIME": "Suscripciones",
    "HOTEL": "Vacaciones",
    "ACA ": "Transporte",
}

SHARED_DESCRIPTION_TOKENS = (
    "SUPERMERC",
    "CARREFOUR",
    "COTO",
    "JUMBO",
    "DISCO",
    "CHANGOMAS",
    "CHANGO MAS",
    "VEA ",
    "DIA %",
    "DIA ONLINE",
    "CARNICER",
    "FRIGORIFICO",
    "VERDULER",
)

PERSONAL_SERVICE_TOKENS = (
    "OPENAI",
    "CHATGPT",
    "TELEFONIA MOVIL",
    "TELEFONO MOVIL",
    "LINEA MOVIL",
    "MOVISTAR MOVIL",
    "CLARO MOVIL",
    "PERSONAL FLOW MOVIL",
    "TUENTI",
)

MOBILE_PROVIDER_TOKENS = ("MOVISTAR", "CLARO", "PERSONAL", "TUENTI")
HOME_SERVICE_TOKENS = ("HOGAR", "FIBRA", "INTERNET", "BANDA ANCHA", "FLOW")


@dataclass(frozen=True)
class CategorySuggestion:
    name: str
    confidence: float
    reason: str


def suggest_category(description: str) -> CategorySuggestion | None:
    normalized = description.upper()
    for token, category in DEFAULT_RULES.items():
        if token in normalized:
            return CategorySuggestion(category, 0.9, f"Regla local: {token}")
    return None


def suggest_shared(description: str, category_name: str | None = None) -> bool:
    """Return the initial household/personal suggestion for a new expense."""
    normalized = description.upper()
    if any(token in normalized for token in PERSONAL_SERVICE_TOKENS):
        return False
    if any(token in normalized for token in MOBILE_PROVIDER_TOKENS) and not any(token in normalized for token in HOME_SERVICE_TOKENS):
        return False
    if category_name == "Servicios":
        return True
    return any(token in normalized for token in SHARED_DESCRIPTION_TOKENS)
