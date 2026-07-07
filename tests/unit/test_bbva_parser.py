import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.domain import Currency, ImportLineKind
from app.services.bbva_parser import parse_argentine_decimal, parse_bbva_visa_pdf, parse_bbva_visa_text, parse_spanish_date


class BbvaParserTests(unittest.TestCase):
    def test_argentine_decimal(self):
        self.assertEqual(parse_argentine_decimal("1.396.208,91"), Decimal("1396208.91"))
        self.assertEqual(parse_argentine_decimal("-2.300,00"), Decimal("-2300.00"))

    def test_spanish_date(self):
        self.assertEqual(parse_spanish_date("03-Dic-25").isoformat(), "2025-12-03")
        self.assertEqual(parse_spanish_date("28-May-26").isoformat(), "2026-05-28")

    def test_sanitized_statement_parses_relevant_lines(self):
        text = (ROOT / "tests" / "fixtures" / "bbva_visa_sanitized.txt").read_text(encoding="utf-8")
        parsed = parse_bbva_visa_text(text)

        self.assertEqual(parsed.account, "0000000000")
        descriptions = [line.description for line in parsed.lines]
        self.assertIn("MERPAGO*MERCADOLIBRE C.06/06", descriptions)
        self.assertIn("OPENAI *CHATGPT SUBSCR", descriptions)
        self.assertNotIn("ESTA LINEA LEGAL NO DEBE PARSEARSE", descriptions)

    def test_usd_refunds_taxes_and_fees_are_classified(self):
        text = (ROOT / "tests" / "fixtures" / "bbva_visa_sanitized.txt").read_text(encoding="utf-8")
        parsed = parse_bbva_visa_text(text)
        by_description = {line.description: line for line in parsed.lines}

        openai = by_description["OPENAI *CHATGPT SUBSCR"]
        self.assertEqual(openai.currency, Currency.USD)
        self.assertEqual(openai.amount, Decimal("20.00"))
        self.assertEqual(openai.kind, ImportLineKind.purchase)

        refund = by_description["PEDIDOSYA*DIA DEMO"]
        self.assertEqual(refund.amount, Decimal("-2300.00"))
        self.assertEqual(refund.kind, ImportLineKind.refund)

        tax_lines = [line for line in parsed.lines if line.kind == ImportLineKind.tax]
        self.assertGreaterEqual(len(tax_lines), 6)

    def test_previous_payments_and_installments_are_classified(self):
        text = (ROOT / "tests" / "fixtures" / "bbva_visa_sanitized.txt").read_text(encoding="utf-8")
        parsed = parse_bbva_visa_text(text)
        by_description = {line.description: line for line in parsed.lines}

        self.assertEqual(by_description["SU PAGO EN PESOS"].kind, ImportLineKind.previous_payment)
        self.assertEqual(by_description["SU PAGO EN USD"].kind, ImportLineKind.previous_payment)
        self.assertEqual(by_description["MERPAGO*MERCADOLIBRE C.06/06"].date.isoformat(), "2026-05-28")
        self.assertEqual(by_description["COMPRA EN CUOTAS DEMO C.04/06"].date.isoformat(), "2026-05-28")

    def test_card_specific_rules_classify_taxes_and_fees_before_refunds(self):
        text = (ROOT / "tests" / "fixtures" / "bbva_visa_sanitized.txt").read_text(encoding="utf-8")
        parsed = parse_bbva_visa_text(text)
        by_description = {line.description: line for line in parsed.lines}

        self.assertEqual(by_description["CR IVA $ 21 %"].kind, ImportLineKind.tax)
        self.assertEqual(by_description["CR.RG 5617 30% M"].kind, ImportLineKind.tax)
        self.assertEqual(by_description["DEV COMISION CTA PWORLD"].kind, ImportLineKind.fee)

    def test_total_consumptions_line_is_not_merged_into_previous_usd_purchase(self):
        text = (ROOT / "tests" / "fixtures" / "bbva_visa_sanitized.txt").read_text(encoding="utf-8")
        parsed = parse_bbva_visa_text(text)
        by_description = {line.description: line for line in parsed.lines}

        steam = by_description["STEAMGAMES.COM 4259522985"]
        self.assertEqual(steam.currency, Currency.USD)
        self.assertEqual(steam.amount, Decimal("5.62"))
        self.assertFalse(any("TOTAL CONSUMOS" in line.description for line in parsed.lines))

    def test_usd_marker_without_space_is_parsed_as_usd(self):
        text = (ROOT / "tests" / "fixtures" / "bbva_visa_sanitized.txt").read_text(encoding="utf-8")
        parsed = parse_bbva_visa_text(text)
        by_description = {line.description: line for line in parsed.lines}

        amazon = by_description["AMAZON PRIME*TT9 f9vrF5l8d"]
        steam = by_description["STEAMGAMES.COM 4 425952298"]
        self.assertEqual(amazon.currency, Currency.USD)
        self.assertEqual(amazon.amount, Decimal("14.99"))
        self.assertEqual(steam.currency, Currency.USD)
        self.assertEqual(steam.amount, Decimal("8.99"))

    def test_sanitized_pdf_fixture_is_parseable(self):
        parsed = parse_bbva_visa_pdf(ROOT / "tests" / "fixtures" / "bbva_visa_sanitized.pdf")

        descriptions = {line.description for line in parsed.lines}
        self.assertIn("OPENAI *CHATGPT SUBSCR", descriptions)
        self.assertIn("AMAZON PRIME*DEMO", descriptions)

    def test_cardholder_name_is_preserved_for_additional_card_sections(self):
        parsed = parse_bbva_visa_text(
            """
            cuenta 123
            CIERRE ACTUAL VENCIMIENTO ACTUAL
            31-May-26
            Consumos Micaela Carolina
            FECHA DESCRIP
            18-May-26 SPOTIFY USD 4,02 123456 4,02
            Consumos Mauro
            FECHA DESCRIP
            19-May-26 SUPERMERCADO 8.000,00
            Consumos Micaela Carolina
            FECHA DESCRIP
            20-May-26 FARMACIA 2.000,00
            """
        )

        by_description = {line.description: line for line in parsed.lines}
        self.assertEqual(by_description["SPOTIFY"].cardholder_name, "Micaela Carolina")
        self.assertEqual(by_description["SUPERMERCADO"].cardholder_name, "Mauro")
        self.assertEqual(by_description["FARMACIA"].cardholder_name, "Micaela Carolina")


if __name__ == "__main__":
    unittest.main()
