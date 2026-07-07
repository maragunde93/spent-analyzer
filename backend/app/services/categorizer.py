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
