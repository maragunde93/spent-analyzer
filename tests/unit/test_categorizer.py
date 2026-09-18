import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.categorizer import suggest_category, suggest_shared


class CategorizerTests(unittest.TestCase):
    def test_account_maintenance_charge_and_reversal_share_category(self):
        charge = suggest_category("\tCOMISION CTA PWORLD")
        reversal = suggest_category("DEV COMISION CTA PWORLD")

        self.assertIsNotNone(charge)
        self.assertIsNotNone(reversal)
        self.assertEqual(charge.name, "Servicios")
        self.assertEqual(reversal.name, "Servicios")

    def test_mep_and_travel_rules_use_current_categories(self):
        self.assertIsNone(suggest_category("TITULOS COMPRA DOLAR MEP"))
        self.assertEqual(suggest_category("HOTEL DEMO SA").name, "Vacaciones")

    def test_edesur_is_service(self):
        self.assertEqual(suggest_category("EDESUR FACTURA 123").name, "Servicios")

    def test_shared_defaults_cover_services_and_household_shopping(self):
        self.assertTrue(suggest_shared("EDESUR FACTURA 123", "Servicios"))
        self.assertTrue(suggest_shared("CARREFOUR MARKET", "Sin categoria"))
        self.assertTrue(suggest_shared("CARNICERIA DEL BARRIO"))

    def test_personal_service_exceptions_win_over_service_category(self):
        self.assertFalse(suggest_shared("OPENAI *CHATGPT SUBSCR", "Servicios"))
        self.assertFalse(suggest_shared("CLARO MOVIL LINEA 11", "Servicios"))
        self.assertFalse(suggest_shared("MOVISTAR FACTURA", "Servicios"))
        self.assertTrue(suggest_shared("MOVISTAR HOGAR INTERNET", "Servicios"))


if __name__ == "__main__":
    unittest.main()
