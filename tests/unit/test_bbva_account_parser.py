import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.domain import ImportLineKind
from app.services.bbva_account_parser import _classify
from app.services.bbva_account_parser import parse_bbva_account_xls


class BbvaAccountParserTests(unittest.TestCase):
    def test_local_account_statement_classifies_key_movements(self):
        statement = ROOT / "Detalle_mov_cuenta_03_07_2026.xls"
        if not statement.exists():
            self.skipTest("Local sensitive account statement is not present")

        parsed = parse_bbva_account_xls(str(statement))
        self.assertGreaterEqual(len(parsed.lines), 6)

        kinds = {line.kind for line in parsed.lines}
        self.assertIn(ImportLineKind.debit_purchase, kinds)
        self.assertIn(ImportLineKind.transfer, kinds)
        self.assertIn(ImportLineKind.income, kinds)

        service_payments = [line for line in parsed.lines if "PAGO DE SERVICIOS TARJETA" in line.description.upper()]
        self.assertTrue(service_payments)
        self.assertTrue(all(line.kind == ImportLineKind.debit_purchase for line in service_payments))

    def test_only_explicit_card_payments_are_ignored(self):
        self.assertEqual(_classify("PAGO DE TARJETA VISA", 0), ImportLineKind.card_payment)
        self.assertEqual(_classify("CUENTA VISA NRO. 79083843369699", 0), ImportLineKind.card_payment)
        self.assertEqual(_classify("CUENTA MASTER NRO. 1234567890", 0), ImportLineKind.card_payment)
        self.assertEqual(_classify("PAGO DE SERVICIOS TARJETA 18073039 OP3802", 0), ImportLineKind.debit_purchase)


if __name__ == "__main__":
    unittest.main()
