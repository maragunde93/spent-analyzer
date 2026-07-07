from __future__ import annotations

import base64
import json
import logging
import re
import shutil
import subprocess
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx

from app.config import get_settings
from app.services.jumbo_receipt_parser import (
    ParsedReceipt,
    ParsedReceiptItem,
    extract_receipt_text,
    parse_jumbo_receipt_text,
    parse_receipt_amount,
    parse_ticket_money,
)


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm"}
TEXT_SUFFIXES = {".txt", ".ocr"}
logger = logging.getLogger("spent.receipts")

RECEIPT_PROMPT = """
Extrae este ticket de supermercado argentino y responde solo JSON valido.
No inventes productos. Preserva importes en ARS reales: por ejemplo 11.240,00 debe ser 11240.00, no 11.24.
Si hay varias imagenes, pueden ser partes del mismo ticket con solapamiento: evita duplicar el mismo item cuando sea claramente la misma linea repetida por overlap.
Incluye descuentos como items negativos separados.
Usa null cuando no puedas leer cantidad o precio unitario.

Formato:
{
  "comercio": "Jumbo",
  "fecha": "YYYY-MM-DD o null",
  "subtotal": 220555.81,
  "descuentos_total": -47508.60,
  "total": 173047.21,
  "productos": [
    {
      "descripcion": "Papas chips crema y cebolla 140gr C&Co",
      "cantidad": 2,
      "precio_unitario": 5620.00,
      "total": 11240.00,
      "subcategoria_sugerida": "Comida",
      "es_descuento": false,
      "confianza": 0.92
    }
  ]
}
"""


def parse_receipt_files(paths: list[tuple[Path, str | None]]) -> tuple[ParsedReceipt | None, str, str]:
    logger.info("receipt_parse_start files=%s", len(paths))
    parsed = parse_receipt_with_gemini(paths)
    if parsed is not None and parsed.items:
        logger.info("receipt_parse_result source=llm items=%s merchant=%s total=%s", len(parsed.items), parsed.merchant, parsed.total)
        return parsed, parsed.raw_text, "llm"

    logger.info("receipt_parse_fallback source=local_ocr")
    raw_chunks = [extract_receipt_text(path, content_type) for path, content_type in paths]
    raw_text = "\n".join(chunk for chunk in raw_chunks if chunk.strip())
    if not raw_text.strip():
        logger.warning("receipt_parse_result source=local_ocr items=0 reason=no_text")
        return None, "", "local_ocr"
    parsed_local = parse_jumbo_receipt_text(raw_text)
    logger.info("receipt_parse_result source=local_ocr items=%s merchant=%s total=%s", len(parsed_local.items), parsed_local.merchant, parsed_local.total)
    return parsed_local, raw_text, "local_ocr"


def parse_receipt_with_gemini(paths: list[tuple[Path, str | None]]) -> ParsedReceipt | None:
    settings = get_settings()
    if not settings.gemini_api_key:
        logger.info("receipt_llm_skipped reason=missing_api_key")
        return None

    try:
        inputs = _gemini_inputs(paths)
    except OSError as exc:
        logger.warning("receipt_llm_skipped reason=input_error error=%s", exc)
        return None
    if len(inputs) <= 1:
        logger.info("receipt_llm_skipped reason=no_supported_inputs")
        return None

    payload = {
        "model": settings.gemini_model,
        "system_instruction": "Sos un extractor de tickets. Respondes solo JSON valido, sin markdown.",
        "input": inputs,
        "generation_config": {
            "temperature": 0,
            "thinking_level": "minimal",
        },
    }
    try:
        logger.info("receipt_llm_request model=%s parts=%s", settings.gemini_model, len(inputs) - 1)
        response = httpx.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={
                "x-goog-api-key": settings.gemini_api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.gemini_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("receipt_llm_failed reason=http_status status=%s", exc.response.status_code)
        return None
    except httpx.HTTPError as exc:
        logger.warning("receipt_llm_failed reason=http_error error=%s", exc)
        return None

    try:
        response_payload = response.json()
    except ValueError:
        logger.warning("receipt_llm_failed reason=invalid_json_response")
        return None
    output_text = extract_gemini_output_text(response_payload)
    if not output_text:
        logger.warning("receipt_llm_failed reason=empty_output")
        return None
    parsed = parse_gemini_receipt_json(output_text)
    if parsed is None:
        logger.warning("receipt_llm_failed reason=invalid_receipt_json")
    return parsed


def extract_gemini_output_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    if isinstance(payload.get("text"), str):
        return payload["text"]

    texts: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"text", "output_text"} and isinstance(child, str):
                    texts.append(child)
                else:
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(payload.get("steps", payload))
    return "\n".join(texts).strip()


def parse_gemini_receipt_json(text: str) -> ParsedReceipt | None:
    json_text = _extract_json_object(text)
    if not json_text:
        return None
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    raw_items = payload.get("productos") or payload.get("items") or []
    items: list[ParsedReceiptItem] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        description = str(raw_item.get("descripcion") or raw_item.get("description") or "").strip()
        if not description:
            continue
        total_amount = _money_from_json(raw_item.get("total") or raw_item.get("total_amount"))
        if total_amount is None:
            continue
        quantity = _decimal_from_json(raw_item.get("cantidad") or raw_item.get("quantity"))
        unit_price = _money_from_json(raw_item.get("precio_unitario") or raw_item.get("unit_price"))
        is_discount = bool(raw_item.get("es_descuento") or raw_item.get("is_discount") or total_amount < 0)
        suggested_subcategory = str(
            raw_item.get("subcategoria_sugerida")
            or raw_item.get("categoria_sugerida")
            or raw_item.get("suggested_subcategory")
            or ""
        ).strip() or None
        if quantity is not None and unit_price is not None:
            expected_total = (quantity * unit_price).quantize(Decimal("0.01"))
            if expected_total and abs(total_amount - expected_total) <= max(Decimal("10.00"), abs(expected_total) * Decimal("0.03")):
                total_amount = expected_total
        items.append(
            ParsedReceiptItem(
                description=description[:240],
                quantity=quantity,
                unit_price=unit_price,
                total_amount=total_amount,
                is_discount=is_discount,
                suggested_subcategory=suggested_subcategory[:80] if suggested_subcategory else None,
            )
        )

    if not items:
        return None
    merchant = str(payload.get("comercio") or payload.get("merchant") or "Supermercado").strip() or "Supermercado"
    return ParsedReceipt(
        merchant=merchant[:80],
        total=_money_from_json(payload.get("total")),
        subtotal=_money_from_json(payload.get("subtotal")),
        discounts_total=_money_from_json(payload.get("descuentos_total") or payload.get("discounts_total")),
        items=items,
        raw_text=json.dumps(payload, ensure_ascii=False),
    )


def _gemini_inputs(paths: list[tuple[Path, str | None]]) -> list[dict[str, str]]:
    inputs: list[dict[str, str]] = [{"type": "text", "text": RECEIPT_PROMPT.strip()}]
    with TemporaryDirectory() as tmp_dir:
        expanded_paths: list[tuple[Path, str | None]] = []
        for path, content_type in paths:
            if _is_video(path, content_type):
                expanded_paths.extend((frame, "image/jpeg") for frame in _extract_video_frames(path, Path(tmp_dir)))
            else:
                expanded_paths.append((path, content_type))
        for path, content_type in expanded_paths[:8]:
            if _is_text(path, content_type):
                text = path.read_text(encoding="utf-8", errors="ignore")
                if text.strip():
                    inputs.append({"type": "text", "text": f"Texto OCR del ticket:\n{text[:12000]}"})
            elif _is_image(path, content_type):
                inputs.append(
                    {
                        "type": "image",
                        "data": base64.b64encode(path.read_bytes()).decode("ascii"),
                        "mime_type": content_type or _mime_from_suffix(path),
                    }
                )
    return inputs


def _extract_video_frames(path: Path, output_dir: Path) -> list[Path]:
    if shutil.which("ffmpeg") is None:
        return []
    frame_pattern = str(output_dir / "llm_frame_%03d.jpg")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(path), "-vf", "fps=0.5,scale=1400:-1", "-frames:v", "8", frame_pattern],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return sorted(output_dir.glob("llm_frame_*.jpg"))


def _extract_json_object(text: str) -> str | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return cleaned[start : end + 1]


def _money_from_json(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return Decimal(value).quantize(Decimal("0.01"))
    if isinstance(value, float):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    try:
        return parse_ticket_money(str(value))
    except (InvalidOperation, ValueError):
        try:
            return parse_receipt_amount(str(value))
        except (InvalidOperation, ValueError):
            return None


def _decimal_from_json(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", ".")).quantize(Decimal("0.001"))
    except InvalidOperation:
        return None


def _is_image(path: Path, content_type: str | None) -> bool:
    return (content_type or "").startswith("image/") or path.suffix.lower() in IMAGE_SUFFIXES


def _is_video(path: Path, content_type: str | None) -> bool:
    return (content_type or "").startswith("video/") or path.suffix.lower() in VIDEO_SUFFIXES


def _is_text(path: Path, content_type: str | None) -> bool:
    return (content_type or "").startswith("text/") or path.suffix.lower() in TEXT_SUFFIXES


def _mime_from_suffix(path: Path) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }.get(path.suffix.lower(), "image/jpeg")
