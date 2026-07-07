import sys
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image, ImageDraw, ImageFont

from app.services.jumbo_receipt_parser import extract_receipt_text, parse_jumbo_receipt_text, parse_receipt_amount, parse_ticket_money


class JumboReceiptParserTests(unittest.TestCase):
    def test_receipt_amount_supports_jumbo_format(self):
        self.assertEqual(parse_receipt_amount("220,555.81"), Decimal("220555.81"))
        self.assertEqual(parse_receipt_amount("1.234,56"), Decimal("1234.56"))
        self.assertEqual(parse_receipt_amount("-47,508.60"), Decimal("-47508.60"))
        self.assertEqual(parse_ticket_money("11.44"), Decimal("11440.00"))
        self.assertEqual(parse_ticket_money("-3.93"), Decimal("-3930.00"))

    def test_jumbo_receipt_parses_items_discounts_and_total(self):
        text = (ROOT / "tests" / "fixtures" / "jumbo_receipt_sanitized.txt").read_text(encoding="utf-8")
        parsed = parse_jumbo_receipt_text(text)

        self.assertEqual(parsed.merchant, "Jumbo")
        self.assertEqual(parsed.subtotal, Decimal("220555.81"))
        self.assertEqual(parsed.discounts_total, Decimal("-47508.60"))
        self.assertEqual(parsed.total, Decimal("173047.21"))

        products = [item for item in parsed.items if not item.is_discount]
        discounts = [item for item in parsed.items if item.is_discount]
        self.assertGreaterEqual(len(products), 10)
        self.assertGreaterEqual(len(discounts), 5)
        self.assertIn("Papas chips crema y cebolla 140gr C&Co", [item.description for item in products])
        self.assertEqual(sum((item.total_amount for item in parsed.items), Decimal("0.00")), parsed.total)

    def test_jumbo_receipt_expands_ocr_compacted_amounts(self):
        parsed = parse_jumbo_receipt_text(
            "\n".join(
                [
                    "JUMBO RETAIL ARGENTINA S.A.",
                    "Papas chips crema y cebolla 140gr C&Co (21,00)",
                    "2x5.62 / 7792052177368 11.44",
                    "2do al 70% CUISINE -3.93",
                ]
            )
        )

        self.assertEqual(parsed.items[0].unit_price, Decimal("5620.00"))
        self.assertEqual(parsed.items[0].total_amount, Decimal("11240.00"))
        self.assertEqual(parsed.items[1].total_amount, Decimal("-3930.00"))

    def test_ocr_image_is_preprocessed_and_parsed(self):
        with TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "ticket.png"
            image = Image.new("RGB", (900, 520), "white")
            draw = ImageDraw.Draw(image)
            font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
            font = ImageFont.truetype(str(font_path), 28) if font_path.exists() else ImageFont.load_default()
            lines = [
                "JUMBO RETAIL ARGENTINA S.A.",
                "FACTURA B",
                "Consumidor Final",
                "Papas chips crema y cebolla 140gr C&Co (21,00)",
                "2x5,620.00 / 7792052177368 11,240.00",
                "TOTAL 11,240.00",
            ]
            for index, line in enumerate(lines):
                draw.text((30, 30 + index * 64), line, fill="black", font=font)
            image.save(image_path)

            text = extract_receipt_text(image_path, "image/png")
            parsed = parse_jumbo_receipt_text(text)

            self.assertGreaterEqual(len(parsed.items), 1)
            self.assertEqual(parsed.total, Decimal("11240.00"))


if __name__ == "__main__":
    unittest.main()
