from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


@dataclass(frozen=True)
class ParsedReceiptItem:
    description: str
    quantity: Decimal | None
    unit_price: Decimal | None
    total_amount: Decimal
    is_discount: bool = False
    suggested_subcategory: str | None = None


@dataclass(frozen=True)
class ParsedReceipt:
    merchant: str
    total: Decimal | None
    subtotal: Decimal | None
    discounts_total: Decimal | None
    items: list[ParsedReceiptItem]
    raw_text: str


AMOUNT_RE = r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2})"
QTY_LINE_RE = re.compile(
    rf"^[^\d]*(?P<qty>\d+(?:[.,]\d+)?)\s*x\s*(?P<unit>{AMOUNT_RE})\s*/\s*(?P<code>\d+)?\s+(?P<total>{AMOUNT_RE})$",
    re.IGNORECASE,
)
TRAILING_AMOUNT_RE = re.compile(rf"(?P<amount>{AMOUNT_RE})\s*$")
DISCOUNT_RE = re.compile(rf"^(?P<description>.+?)\s+(?P<amount>-{AMOUNT_RE.removeprefix('-?')})$")
TOTAL_RE = re.compile(rf"^TOTAL\s+(?P<amount>{AMOUNT_RE})$", re.IGNORECASE)
SUBTOTAL_RE = re.compile(rf"^SUBTOTAL\b.*?(?P<amount>{AMOUNT_RE})$", re.IGNORECASE)


def parse_receipt_amount(value: str) -> Decimal:
    normalized = value.strip().replace(" ", "")
    if "," in normalized and "." in normalized:
        if normalized.rfind(".") > normalized.rfind(","):
            normalized = normalized.replace(",", "")
        else:
            normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        if normalized.count(",") > 1:
            head, tail = normalized.rsplit(",", 1)
            normalized = head.replace(",", "").replace(".", "") + "." + tail
        else:
            normalized = normalized.replace(".", "").replace(",", ".")
    elif normalized.count(".") > 1:
        head, tail = normalized.rsplit(".", 1)
        normalized = head.replace(".", "") + "." + tail
    try:
        return Decimal(normalized).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid receipt amount: {value}") from exc


def parse_receipt_quantity(value: str) -> Decimal:
    return Decimal(value.replace(",", "."))


def parse_ticket_money(value: str) -> Decimal:
    amount = parse_receipt_amount(value)
    if Decimal("0") < abs(amount) < Decimal("100"):
        return (amount * Decimal("1000")).quantize(Decimal("0.01"))
    return amount


def clean_product_description(line: str) -> str:
    cleaned = re.sub(r"\(\s*\d{1,2}[,.]\d{2}\s*\)", "", line)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -")


def normalize_receipt_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.replace("\r", "\n").split("\n"):
        cleaned = re.sub(r"\s+", " ", line).strip()
        if not cleaned:
            continue
        cleaned = re.sub(r"(?<=\d)[ ]+([,.])", r"\1", cleaned)
        cleaned = re.sub(r"([,.])[ ]+(?=\d)", r"\1", cleaned)
        cleaned = re.sub(r"(?<=\d)[ ]+(?=\d{2}\b(?![,.]))", ".", cleaned)
        cleaned = cleaned.replace("×", "x").replace("X", "x")
        lines.append(cleaned)
    return lines


def parse_jumbo_receipt_text(text: str) -> ParsedReceipt:
    lines = normalize_receipt_lines(text)
    items: list[ParsedReceiptItem] = []
    pending_description: str | None = None
    subtotal: Decimal | None = None
    total: Decimal | None = None
    discounts_total: Decimal | None = None
    in_discount_summary = False
    last_standalone_amount: Decimal | None = None

    for raw_line in lines:
        line = raw_line.strip()
        upper = line.upper()

        total_match = TOTAL_RE.match(line)
        if total_match:
            total = parse_ticket_money(total_match.group("amount"))
            pending_description = None
            last_standalone_amount = None
            continue
        if upper == "TOTAL" and last_standalone_amount is not None:
            total = last_standalone_amount
            pending_description = None
            last_standalone_amount = None
            continue

        subtotal_match = SUBTOTAL_RE.match(line)
        if subtotal_match:
            subtotal = parse_ticket_money(subtotal_match.group("amount"))
            pending_description = None
            last_standalone_amount = None
            continue

        if upper.startswith("DESCUENTOS"):
            in_discount_summary = True
            pending_description = None
            continue
        if upper.startswith("REGIMEN") or upper.startswith("IVA ") or upper.startswith("OTROS IMPUESTOS"):
            pending_description = None
            continue
        if in_discount_summary:
            if upper.startswith("TOTAL DESCUENTO"):
                amount_match = re.search(AMOUNT_RE, line)
                if amount_match:
                    discounts_total = parse_ticket_money(amount_match.group(0))
            continue

        qty_match = QTY_LINE_RE.match(line)
        if qty_match and pending_description:
            try:
                quantity = parse_receipt_quantity(qty_match.group("qty"))
                unit_price = parse_ticket_money(qty_match.group("unit"))
                total_amount = parse_ticket_money(qty_match.group("total"))
            except ValueError:
                pending_description = None
                last_standalone_amount = None
                continue
            expected_total = (quantity * unit_price).quantize(Decimal("0.01"))
            if expected_total and abs(total_amount) < abs(expected_total) / Decimal("100"):
                total_amount = expected_total
            elif expected_total and abs(total_amount - expected_total) <= abs(expected_total) * Decimal("0.03"):
                total_amount = expected_total
            items.append(
                ParsedReceiptItem(
                    description=pending_description,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_amount=total_amount,
                )
            )
            pending_description = None
            last_standalone_amount = None
            continue

        trailing_amount = TRAILING_AMOUNT_RE.search(line)
        if pending_description and trailing_amount and "/" in line and not upper.startswith("TOTAL"):
            try:
                total_amount = parse_ticket_money(trailing_amount.group("amount"))
            except ValueError:
                pending_description = None
                last_standalone_amount = None
                continue
            items.append(
                ParsedReceiptItem(
                    description=pending_description,
                    quantity=None,
                    unit_price=None,
                    total_amount=total_amount,
                )
            )
            pending_description = None
            last_standalone_amount = None
            continue
        if re.fullmatch(AMOUNT_RE, line):
            try:
                last_standalone_amount = parse_ticket_money(line)
            except ValueError:
                last_standalone_amount = None
            continue

        discount_match = DISCOUNT_RE.match(line)
        if discount_match and not upper.startswith("TOTAL"):
            try:
                amount = parse_ticket_money(discount_match.group("amount"))
            except ValueError:
                pending_description = None
                last_standalone_amount = None
                continue
            if amount < 0:
                items.append(
                    ParsedReceiptItem(
                        description=clean_product_description(discount_match.group("description")),
                        quantity=None,
                        unit_price=None,
                        total_amount=amount,
                        is_discount=True,
                    )
                )
                pending_description = None
                last_standalone_amount = None
                continue

        if _looks_like_product_line(line):
            pending_description = clean_product_description(line)

    merchant = "Jumbo" if any("JUMBO" in line.upper() for line in lines) else "Supermercado"
    if discounts_total is None:
        discounts = sum((item.total_amount for item in items if item.is_discount), Decimal("0.00"))
        discounts_total = discounts if discounts else None
    return ParsedReceipt(
        merchant=merchant,
        total=total,
        subtotal=subtotal,
        discounts_total=discounts_total,
        items=items,
        raw_text=text,
    )


def extract_receipt_text(path: Path, content_type: str | None = None) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".ocr"} or (content_type or "").startswith("text/"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if (content_type or "").startswith("image/") or suffix in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
        return _ocr_image(path)
    if (content_type or "").startswith("video/") or suffix in {".mp4", ".mov", ".m4v", ".webm"}:
        return _ocr_video(path)
    return ""


def _ocr_image(path: Path) -> str:
    if shutil.which("tesseract") is None:
        return ""
    with TemporaryDirectory() as tmp_dir:
        variants = _preprocess_receipt_image(path, Path(tmp_dir))
        chunks: list[str] = []
        for variant in variants:
            for psm in ("6", "4"):
                chunks.append(_run_tesseract(variant, psm))
    return _merge_ocr_chunks(chunks)


def _ocr_video(path: Path) -> str:
    if shutil.which("ffmpeg") is None or shutil.which("tesseract") is None:
        return ""
    with TemporaryDirectory() as tmp_dir:
        frame_pattern = str(Path(tmp_dir) / "frame_%03d.jpg")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(path), "-vf", "fps=1,scale=1200:-1", "-frames:v", "18", frame_pattern],
                check=False,
                capture_output=True,
                text=True,
                timeout=45,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        chunks = [_ocr_image(frame) for frame in sorted(Path(tmp_dir).glob("frame_*.jpg"))]
    return _merge_ocr_chunks(chunks)


def _merge_ocr_chunks(chunks: list[str]) -> str:
    seen: set[str] = set()
    merged: list[str] = []
    for chunk in chunks:
        for line in normalize_receipt_lines(chunk):
            key = re.sub(r"\W+", "", line).upper()
            if len(key) < 4 or key in seen:
                continue
            seen.add(key)
            merged.append(line)
    return "\n".join(merged)


def _run_tesseract(path: Path, psm: str) -> str:
    try:
        result = subprocess.run(
            ["tesseract", str(path), "stdout", "-l", "spa+eng", "--psm", psm],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _preprocess_receipt_image(path: Path, output_dir: Path) -> list[Path]:
    image = Image.open(path).convert("RGB")
    receipt = _crop_receipt(image)
    crops = [receipt]
    width, height = receipt.size
    if height > 400:
        crops.append(receipt.crop((0, int(height * 0.08), width, int(height * 0.92))))

    variants: list[Path] = []
    for index, crop in enumerate(crops):
        gray = ImageOps.grayscale(crop)
        gray = ImageOps.autocontrast(gray)
        gray = ImageEnhance.Contrast(gray).enhance(2.6)
        scale = max(2, min(5, 2400 // max(gray.width, 1)))
        gray = gray.resize((gray.width * scale, gray.height * scale))
        gray = gray.filter(ImageFilter.SHARPEN)
        processed = [
            gray,
            gray.point(lambda pixel: 255 if pixel > 165 else 0),
            gray.filter(ImageFilter.UnsharpMask(radius=1.2, percent=180, threshold=3)),
        ]
        for variant_index, variant in enumerate(processed):
            output = output_dir / f"receipt_{index}_{variant_index}.png"
            variant.save(output)
            variants.append(output)
    return variants


def _crop_receipt(image: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(image)
    width, height = gray.size
    pixels = gray.load()
    threshold = 175
    y_step = max(1, height // 700)
    column_counts = [
        sum(1 for y in range(0, height, y_step) if pixels[x, y] > threshold)
        for x in range(width)
    ]
    min_column_count = max(20, int(max(column_counts, default=0) * 0.18))
    x1, x2 = _largest_density_segment(column_counts, min_column_count, width)
    x1 = max(0, x1 - 18)
    x2 = min(width, x2 + 18)

    x_step = max(1, (x2 - x1) // 500)
    row_counts = [
        sum(1 for x in range(x1, x2, x_step) if pixels[x, y] > threshold)
        for y in range(height)
    ]
    min_row_count = max(10, int(max(row_counts, default=0) * 0.10))
    y1, y2 = _largest_density_segment(row_counts, min_row_count, height)
    y1 = max(0, y1 - 18)
    y2 = min(height, y2 + 18)
    if (x2 - x1) < width * 0.25 or (y2 - y1) < height * 0.35:
        return image
    return image.crop((x1, y1, x2, y2))


def _largest_density_segment(counts: list[int], threshold: int, fallback_end: int) -> tuple[int, int]:
    best_start = 0
    best_end = fallback_end
    current_start: int | None = None
    for index, count in enumerate(counts + [0]):
        if count >= threshold and current_start is None:
            current_start = index
        if (count < threshold or index == len(counts)) and current_start is not None:
            if best_end == fallback_end and best_start == 0 or index - current_start > best_end - best_start:
                best_start, best_end = current_start, index
            current_start = None
    return best_start, best_end


def _looks_like_product_line(line: str) -> bool:
    upper = line.upper()
    line_without_tax = re.sub(r"\(\s*\d{1,2}[,.]\d{2}\s*\)", "", line)
    if len(line) < 3:
        return False
    ignored_prefixes = (
        "AV.",
        "CUIT",
        "ING.",
        "IVA",
        "RESPONSABLE",
        "INICIO",
        "FACTURA",
        "ORIGINAL",
        "CONSUMIDOR",
        "NRO.",
        "COND.",
        "SUBTOTAL",
        "TOTAL",
    )
    if upper.startswith(ignored_prefixes):
        return False
    if "/" in line_without_tax and re.search(AMOUNT_RE, line_without_tax):
        return False
    return bool(re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", line))
