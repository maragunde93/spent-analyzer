import sys
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.receipt_ai_parser import extract_gemini_output_text, parse_gemini_receipt_json, parse_receipt_files


class ReceiptAiParserTests(unittest.TestCase):
    def test_gemini_json_is_normalized_to_receipt_items(self):
        parsed = parse_gemini_receipt_json(
            """
            ```json
            {
              "comercio": "Jumbo",
              "subtotal": 220555.81,
              "descuentos_total": -47508.60,
              "total": 173047.21,
              "productos": [
                {
                  "descripcion": "Papas chips crema y cebolla 140gr C&Co",
                  "cantidad": 2,
                  "precio_unitario": 5620,
                  "total": 11240,
                  "subcategoria_sugerida": "Comida",
                  "es_descuento": false
                },
                {
                  "descripcion": "2do al 70% CUISINE",
                  "cantidad": null,
                  "precio_unitario": null,
                  "total": -3934,
                  "categoria_sugerida": "Supermercado",
                  "es_descuento": true
                }
              ]
            }
            ```
            """
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.merchant, "Jumbo")
        self.assertEqual(parsed.total, Decimal("173047.21"))
        self.assertEqual(parsed.items[0].quantity, Decimal("2.000"))
        self.assertEqual(parsed.items[0].unit_price, Decimal("5620.00"))
        self.assertEqual(parsed.items[0].total_amount, Decimal("11240.00"))
        self.assertEqual(parsed.items[0].suggested_subcategory, "Comida")
        self.assertTrue(parsed.items[1].is_discount)

    def test_gemini_response_text_is_extracted_from_nested_payloads(self):
        payload = {
            "steps": [
                {
                    "output": [
                        {"text": "{\"comercio\":\"Jumbo\",\"productos\":[]}"}
                    ]
                }
            ]
        }

        self.assertEqual(extract_gemini_output_text(payload), "{\"comercio\":\"Jumbo\",\"productos\":[]}")

    def test_missing_gemini_key_falls_back_to_local_text_parser(self):
        with TemporaryDirectory() as tmp_dir:
            ticket = Path(tmp_dir) / "ticket.txt"
            ticket.write_text(
                "\n".join(
                    [
                        "JUMBO RETAIL ARGENTINA S.A.",
                        "Papas chips crema y cebolla 140gr C&Co (21,00)",
                        "2x5,620.00 / 7792052177368 11,240.00",
                        "TOTAL 11,240.00",
                    ]
                ),
                encoding="utf-8",
            )

            with patch("app.services.receipt_ai_parser.parse_receipt_with_gemini", return_value=None):
                parsed, raw_text, source = parse_receipt_files([(ticket, "text/plain")])

        self.assertEqual(source, "local_ocr")
        self.assertIn("Papas chips", raw_text)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.items[0].total_amount, Decimal("11240.00"))


if __name__ == "__main__":
    unittest.main()
