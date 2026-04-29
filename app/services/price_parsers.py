"""Parsers for supplier price list imports.

Supports: CSV, XLS/XLSX, XML, YML (Yandex Market Language).
Each parser returns a normalized list of product dicts.
"""

import csv
import io
import re
from typing import List, Dict, Any, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)

REQUIRED_FIELDS = {"article", "name", "price"}
OPTIONAL_FIELDS = {
    "brand", "category", "stock_quantity", "stock_status",
    "description", "applicability", "weight", "oem_number",
    "min_order", "unit", "barcode", "country",
}


def _normalize_row(row: Dict[str, Any], field_map: Dict[str, str]) -> Dict[str, Any]:
    """Normalize a raw row dict using a field_map (source_name -> canonical_name)."""
    normalized = {}
    for source_key, canonical in field_map.items():
        value = row.get(source_key)
        if value is not None:
            normalized[canonical] = value

    if "price" in normalized and isinstance(normalized["price"], str):
        normalized["price"] = _parse_price(normalized["price"])
    if "stock_quantity" in normalized and isinstance(normalized["stock_quantity"], str):
        normalized["stock_quantity"] = _parse_int(normalized["stock_quantity"])
    if "weight" in normalized and isinstance(normalized["weight"], str):
        normalized["weight"] = _parse_float(normalized["weight"])

    return normalized


def _parse_price(value: str) -> float:
    cleaned = re.sub(r"[^\d.,]", "", str(value))
    cleaned = cleaned.replace(",", ".")
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_int(value: str) -> int:
    cleaned = re.sub(r"[^\d-]", "", str(value))
    try:
        return int(cleaned)
    except ValueError:
        return 0


def _parse_float(value: str) -> float:
    cleaned = re.sub(r"[^\d.,-]", "", str(value))
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _auto_detect_field_map(headers: List[str]) -> Dict[str, str]:
    """Auto-detect field mapping from header names."""
    field_map: Dict[str, str] = {}
    header_patterns = {
        "article": ["артикул", "article", "art", "код", "sku", "part_number", "partnumber", "номер"],
        "name": ["наименование", "название", "name", "title", "описание", "description", "товар"],
        "price": ["цена", "price", "стоимость", "cost", "розница", "retail"],
        "brand": ["бренд", "brand", "производитель", "manufacturer", "maker"],
        "category": ["категория", "category", "группа", "group", "раздел", "тип"],
        "stock_quantity": ["остаток", "кол-во", "количество", "stock", "qty", "quantity", "наличие", "склад"],
        "stock_status": ["статус", "status", "наличие_статус"],
        "description": ["описание_полное", "full_desc", "подробно"],
        "applicability": ["применимость", "применяемость", "applicability", "применение", "авто"],
        "weight": ["вес", "weight", "масса"],
        "oem_number": ["oem", "оригинальный_номер", "oem_number", "orig", "ориг"],
        "min_order": ["мин_заказ", "min_order", "минимальное"],
        "unit": ["единица", "unit", "ед_изм"],
        "barcode": ["штрихкод", "barcode", "ean", "ean13"],
        "country": ["страна", "country", "происхождение"],
    }

    for header in headers:
        header_lower = header.lower().strip()
        for canonical, patterns in header_patterns.items():
            for pattern in patterns:
                if pattern in header_lower:
                    field_map[header] = canonical
                    break
            if header in field_map:
                break

    return field_map


# ── CSV Parser ───────────────────────────────────────────────────────

class CsvParser:
    name = "csv"

    @staticmethod
    def parse(content: bytes, encoding: str = "utf-8", delimiter: str = ";",
              field_map: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        text = content.decode(encoding, errors="replace")
        lines = text.strip().splitlines()
        if not lines:
            return []

        reader = csv.reader(lines, delimiter=delimiter)
        headers = next(reader)
        headers = [h.strip() for h in headers]

        if not field_map:
            field_map = _auto_detect_field_map(headers)

        products = []
        for row_values in reader:
            row = dict(zip(headers, [v.strip() for v in row_values]))
            normalized = _normalize_row(row, field_map)

            if "article" in normalized and "name" in normalized and "price" in normalized:
                products.append(normalized)

        logger.info("csv_parse_complete", extra={"extra": {"products": len(products)}})
        return products


# ── XLS/XLSX Parser ─────────────────────────────────────────────────

class XlsParser:
    name = "xls"

    @staticmethod
    def parse(content: bytes, sheet_index: int = 0,
              field_map: Optional[Dict[str, str]] = None,
              header_row: int = 0) -> List[Dict[str, Any]]:
        try:
            import openpyxl
        except ImportError:
            try:
                import xlrd
                return XlsParser._parse_xlrd(content, sheet_index, field_map, header_row)
            except ImportError:
                logger.error("xls_parse_no_library")
                return []

        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheet = wb.worksheets[sheet_index]
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                return []

            headers = [str(h or "").strip() for h in rows[header_row]]
            if not field_map:
                field_map = _auto_detect_field_map(headers)

            products = []
            for row_values in rows[header_row + 1:]:
                row = {}
                for i, val in enumerate(row_values):
                    if i < len(headers):
                        row[headers[i]] = str(val) if val is not None else ""
                normalized = _normalize_row(row, field_map)
                if "article" in normalized and "name" in normalized and "price" in normalized:
                    products.append(normalized)

            wb.close()
            logger.info("xls_parse_complete", extra={"extra": {"products": len(products)}})
            return products

        except Exception as exc:
            logger.error("xls_parse_error", extra={"extra": {"error": str(exc)}})
            return []

    @staticmethod
    def _parse_xlrd(content: bytes, sheet_index: int,
                    field_map: Optional[Dict[str, str]], header_row: int) -> List[Dict[str, Any]]:
        import xlrd
        wb = xlrd.open_workbook(file_contents=content)
        sheet = wb.sheet_by_index(sheet_index)

        headers = [str(sheet.cell_value(header_row, col)).strip() for col in range(sheet.ncols)]
        if not field_map:
            field_map = _auto_detect_field_map(headers)

        products = []
        for row_idx in range(header_row + 1, sheet.nrows):
            row = {}
            for col in range(sheet.ncols):
                if col < len(headers):
                    row[headers[col]] = str(sheet.cell_value(row_idx, col))
            normalized = _normalize_row(row, field_map)
            if "article" in normalized and "name" in normalized and "price" in normalized:
                products.append(normalized)

        return products


# ── XML Parser ───────────────────────────────────────────────────────

class XmlParser:
    name = "xml"

    @staticmethod
    def parse(content: bytes, encoding: str = "utf-8",
              field_map: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(content.decode(encoding, errors="replace"))
        except ET.ParseError as exc:
            logger.error("xml_parse_error", extra={"extra": {"error": str(exc)}})
            return []

        products = []

        for offer in root.iter("offer"):
            row = {}
            row["article"] = offer.get("id") or offer.findtext("article") or offer.findtext("vendorCode") or ""
            row["name"] = offer.findtext("name") or offer.findtext("title") or ""
            row["price"] = offer.findtext("price") or "0"
            row["brand"] = offer.findtext("vendor") or offer.findtext("brand") or ""
            row["category"] = offer.findtext("categoryId") or offer.findtext("category") or ""
            row["description"] = offer.findtext("description") or ""
            row["stock_quantity"] = offer.get("quantity") or offer.findtext("quantity") or "0"
            row["barcode"] = offer.findtext("barcode") or offer.findtext("ean") or ""

            params = {}
            for param in offer.iter("param"):
                param_name = param.get("name", "").lower()
                param_value = param.text or ""
                params[param_name] = param_value

            if "вес" in params or "weight" in params:
                row["weight"] = params.get("вес", params.get("weight", ""))
            if "страна" in params or "country" in params:
                row["country"] = params.get("страна", params.get("country", ""))

            if row.get("article") and row.get("name") and row.get("price"):
                products.append(_normalize_row(row, field_map or {k: k for k in row}))

        logger.info("xml_parse_complete", extra={"extra": {"products": len(products)}})
        return products


# ── YML (Yandex Market Language) Parser ──────────────────────────────

class YmlParser:
    """YML is a subset of XML with specific structure for product catalogs."""

    name = "yml"

    @staticmethod
    def parse(content: bytes, encoding: str = "utf-8",
              field_map: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(content.decode(encoding, errors="replace"))
        except ET.ParseError as exc:
            logger.error("yml_parse_error", extra={"extra": {"error": str(exc)}})
            return []

        categories = {}
        for cat in root.iter("category"):
            cat_id = cat.get("id")
            cat_name = cat.text or ""
            if cat_id:
                categories[cat_id] = cat_name

        products = []

        shop = root.find("shop")
        offers_parent = shop.find("offers") if shop is not None else root.find("offers")
        if offers_parent is None:
            offers_parent = root

        for offer in offers_parent.iter("offer"):
            row = {}
            offer_id = offer.get("id") or ""
            row["article"] = offer.get("id") or offer.findtext("vendorCode") or offer_id
            row["name"] = offer.findtext("name") or offer.findtext("title") or ""
            row["price"] = offer.findtext("price") or "0"
            row["brand"] = offer.findtext("vendor") or offer.findtext("brand") or ""

            cat_id = offer.findtext("categoryId") or ""
            row["category"] = categories.get(cat_id, cat_id)

            row["description"] = offer.findtext("description") or ""
            row["stock_quantity"] = offer.get("available", "true") == "true" and 10 or 0
            row["barcode"] = offer.findtext("barcode") or offer.findtext("ean") or ""
            row["oem_number"] = offer.findtext("vendorCode") or ""
            row["unit"] = offer.get("unit", "шт")
            row["weight"] = offer.findtext("weight") or offer.get("weight", "")
            row["country"] = offer.findtext("country_of_origin") or ""

            for param in offer.iter("param"):
                param_name = param.get("name", "").lower()
                param_value = param.text or ""
                if "применяемость" in param_name or "применимость" in param_name or "авто" in param_name:
                    row["applicability"] = param_value

            pictures = [pic.text for pic in offer.iter("picture") if pic.text]
            if pictures:
                row["images"] = pictures

            if row.get("article") and row.get("name") and row.get("price"):
                products.append(_normalize_row(row, field_map or {k: k for k in row}))

        logger.info("yml_parse_complete", extra={"extra": {"products": len(products), "categories": len(categories)}})
        return products


# ── Dispatcher ───────────────────────────────────────────────────────

PARSERS = {
    ".csv": CsvParser,
    ".xls": XlsParser,
    ".xlsx": XlsParser,
    ".xml": XmlParser,
    ".yml": YmlParser,
}


def detect_format(filename: str) -> Optional[str]:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext if ext in PARSERS else None


def parse_file(
    content: bytes,
    filename: str,
    encoding: str = "utf-8",
    delimiter: str = ";",
    field_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    fmt = detect_format(filename)
    if not fmt:
        logger.error("unknown_format", extra={"extra": {"filename": filename}})
        return []

    parser = PARSERS[fmt]

    if fmt == ".csv":
        return parser.parse(content, encoding=encoding, delimiter=delimiter, field_map=field_map)
    elif fmt in (".xls", ".xlsx"):
        return parser.parse(content, field_map=field_map)
    elif fmt in (".xml", ".yml"):
        return parser.parse(content, encoding=encoding, field_map=field_map)

    return []
