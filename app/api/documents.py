from collections import defaultdict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    REPORTLAB_AVAILABLE = True
except ImportError:
    A4 = None
    mm = 1
    pdfmetrics = None
    TTFont = None
    canvas = Any
    REPORTLAB_AVAILABLE = False

from app.api.auth import get_current_active_user
from app.core.database import get_db
from app.core.enums import OrderStatus
from app.models.order import Order, OrderItem
from app.models.user import User

router = APIRouter(prefix="/documents", tags=["Documents"])

FONT_NAME = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def _status_value(order_status) -> str:
    if hasattr(order_status, "value"):
        return order_status.value
    return str(order_status)


def _register_pdf_fonts():
    if not REPORTLAB_AVAILABLE:
        return

    global FONT_NAME, FONT_BOLD

    if FONT_NAME != "Helvetica":
        return

    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/ARIAL.TTF"),
    ]
    bold_candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/ARIALBD.TTF"),
    ]

    regular_font = next((path for path in candidates if path.exists()), None)
    bold_font = next((path for path in bold_candidates if path.exists()), None)

    if regular_font and bold_font:
        pdfmetrics.registerFont(TTFont("TruckHubArial", str(regular_font)))
        pdfmetrics.registerFont(TTFont("TruckHubArialBold", str(bold_font)))
        FONT_NAME = "TruckHubArial"
        FONT_BOLD = "TruckHubArialBold"


def _draw_text(pdf: canvas.Canvas, text: str, x: float, y: float, bold: bool = False, size: int = 10):
    pdf.setFont(FONT_BOLD if bold else FONT_NAME, size)
    pdf.drawString(x, y, text)


def _draw_wrapped_text(
    pdf: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    bold: bool = False,
    size: int = 10,
    line_gap: int = 13,
):
    font_name = FONT_BOLD if bold else FONT_NAME
    pdf.setFont(font_name, size)
    words = str(text or "").split()
    if not words:
        return y - line_gap

    current_line = ""
    current_y = y
    for word in words:
        trial_line = f"{current_line} {word}".strip()
        if pdf.stringWidth(trial_line, font_name, size) <= max_width:
            current_line = trial_line
        else:
            pdf.drawString(x, current_y, current_line)
            current_y -= line_gap
            current_line = word
    if current_line:
        pdf.drawString(x, current_y, current_line)
        current_y -= line_gap
    return current_y


def _build_shipment_groups(items: list[OrderItem]) -> list[dict]:
    grouped: dict[str, dict] = {}

    for item in items:
        supplier_key = item.supplier_id or "unknown"
        shipment = grouped.get(supplier_key)
        if shipment is None:
            shipment = {
                "supplier_id": item.supplier_id,
                "supplier_name": item.supplier_name or "Не указан",
                "status": item.shipment_status or "pending",
                "tracking_number": item.shipment_tracking_number,
                "items_count": 0,
                "total_amount": 0.0,
                "items": [],
            }
            grouped[supplier_key] = shipment

        shipment["items_count"] += 1
        shipment["total_amount"] += item.total_price
        shipment["items"].append(
            {
                "id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
                "supplier_name": item.supplier_name,
                "shipment_status": item.shipment_status or "pending",
                "shipment_tracking_number": item.shipment_tracking_number,
                "is_installation": item.is_installation,
            }
        )

    return list(grouped.values())


def _build_document_lifecycle(order: Order, items: list[OrderItem], has_installation: bool) -> dict:
    order_status = _status_value(order.status)
    shipments = _build_shipment_groups(items)

    invoice_status = "pending"
    if (order.payment_status or "").lower() == "succeeded" or order_status in {
        OrderStatus.PAID.value,
        OrderStatus.SHIPPED.value,
        OrderStatus.DELIVERED.value,
    }:
        invoice_status = "ready"

    upd_status = "pending"
    if any((shipment["status"] or "").lower() in {"shipped", "delivered"} for shipment in shipments):
        upd_status = "partial" if any((shipment["status"] or "").lower() == "pending" for shipment in shipments) else "ready"

    act_status = "not_required"
    if has_installation:
        act_status = "pending"
        if order_status == OrderStatus.DELIVERED.value:
            act_status = "ready"

    shipment_documents = []
    for shipment in shipments:
        shipment_status = (shipment["status"] or "pending").lower()
        shipment_documents.append(
            {
                "supplier_id": shipment["supplier_id"],
                "supplier_name": shipment["supplier_name"],
                "status": shipment_status,
                "tracking_number": shipment["tracking_number"],
                "items_count": shipment["items_count"],
                "total_amount": shipment["total_amount"],
                "invoice": {
                    "status": "ready" if invoice_status == "ready" else "pending",
                    "available": invoice_status == "ready",
                },
                "upd": {
                    "status": "ready" if shipment_status in {"shipped", "delivered"} else "pending",
                    "available": shipment_status in {"shipped", "delivered"},
                },
            }
        )

    return {
        "order_status": order_status,
        "invoice": {
            "status": invoice_status,
            "available": invoice_status == "ready",
        },
        "upd": {
            "status": upd_status,
            "available": upd_status in {"ready", "partial"},
        },
        "act": {
            "status": act_status,
            "available": act_status == "ready",
            "required": has_installation,
        },
        "shipments": shipment_documents,
    }


async def _get_order_with_items(order_id: str, current_user: User, db: AsyncSession):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        return None, None, None

    items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    items = items_result.scalars().all()
    has_installation = any(item.is_installation for item in items)
    return order, items, has_installation


def _document_filename(kind: str, order_number: str, suffix: str | None = None) -> str:
    base = f"{kind.lower()}-{order_number}"
    if suffix:
        base = f"{base}-{suffix}"
    return f"{base}.pdf"


def _create_pdf_response(filename: str, payload_writer):
    if not REPORTLAB_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"detail": "PDF generation is temporarily unavailable on the server"},
        )

    _register_pdf_fonts()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    payload_writer(pdf)
    pdf.save()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _render_invoice_pdf(pdf: canvas.Canvas, invoice: dict):
    width, height = A4
    margin_x = 18 * mm
    y = height - 22 * mm
    _draw_text(pdf, "TruckHub", margin_x, y, bold=True, size=18)
    y -= 10 * mm
    _draw_text(pdf, f"Счет {invoice['invoice_number']}", margin_x, y, bold=True, size=16)
    _draw_text(pdf, f"Заказ: {invoice['order_number']}", 125 * mm, y, size=10)
    y -= 7 * mm
    _draw_text(pdf, f"Дата: {invoice['date'][:19].replace('T', ' ')}", 125 * mm, y, size=10)
    y -= 12 * mm
    _draw_text(pdf, "Продавец", margin_x, y, bold=True, size=11)
    _draw_text(pdf, "Покупатель", 105 * mm, y, bold=True, size=11)
    y -= 6 * mm
    y_left = _draw_wrapped_text(pdf, invoice["seller"]["name"], margin_x, y, 70 * mm, bold=True)
    y_left = _draw_wrapped_text(pdf, f"ИНН: {invoice['seller']['inn']}", margin_x, y_left, 70 * mm)
    y_left = _draw_wrapped_text(pdf, f"Адрес: {invoice['seller']['address']}", margin_x, y_left, 70 * mm)
    y_right = _draw_wrapped_text(pdf, invoice["buyer"]["name"], 105 * mm, y, 75 * mm, bold=True)
    y_right = _draw_wrapped_text(pdf, f"ИНН: {invoice['buyer']['inn']}", 105 * mm, y_right, 75 * mm)
    y_right = _draw_wrapped_text(pdf, f"Адрес: {invoice['buyer']['address']}", 105 * mm, y_right, 75 * mm)
    y = min(y_left, y_right) - 8 * mm
    _draw_text(pdf, "№", margin_x, y, bold=True)
    _draw_text(pdf, "Наименование", margin_x + 12 * mm, y, bold=True)
    _draw_text(pdf, "Кол-во", 120 * mm, y, bold=True)
    _draw_text(pdf, "Цена", 145 * mm, y, bold=True)
    _draw_text(pdf, "Сумма", 172 * mm, y, bold=True)
    y -= 5 * mm
    pdf.line(margin_x, y + 2 * mm, width - margin_x, y + 2 * mm)
    for index, item in enumerate(invoice["items"], start=1):
        _draw_text(pdf, str(index), margin_x, y)
        y = _draw_wrapped_text(pdf, item["name"], margin_x + 12 * mm, y, 90 * mm)
        row_y = y + 13
        _draw_text(pdf, str(item["quantity"]), 120 * mm, row_y)
        _draw_text(pdf, f"{item['price']:.2f}", 145 * mm, row_y)
        _draw_text(pdf, f"{item['total']:.2f}", 172 * mm, row_y)
        y -= 2 * mm
    y -= 8 * mm
    _draw_text(pdf, f"Сумма без НДС: {invoice['total_amount']:.2f} ₽", 120 * mm, y, bold=True)
    y -= 6 * mm
    _draw_text(pdf, f"НДС: {invoice['vat_amount']:.2f} ₽", 120 * mm, y)
    y -= 6 * mm
    _draw_text(pdf, f"Итого к оплате: {invoice['total_with_vat']:.2f} ₽", 120 * mm, y, bold=True, size=12)


def _render_upd_pdf(pdf: canvas.Canvas, upd: dict):
    width, height = A4
    margin_x = 18 * mm
    y = height - 22 * mm
    _draw_text(pdf, "TruckHub", margin_x, y, bold=True, size=18)
    y -= 10 * mm
    _draw_text(pdf, f"УПД {upd['invoice_number']}", margin_x, y, bold=True, size=16)
    _draw_text(pdf, f"Заказ: {upd['order_number']}", 125 * mm, y, size=10)
    y -= 7 * mm
    _draw_text(pdf, f"Дата: {upd['date'][:19].replace('T', ' ')}", 125 * mm, y, size=10)
    y -= 14 * mm
    for title, block_x, block in [("Поставщик", margin_x, upd["seller"]), ("Покупатель", 105 * mm, upd["buyer"])]:
        _draw_text(pdf, title, block_x, y, bold=True, size=11)
        _draw_wrapped_text(pdf, block["name"], block_x, y - 6 * mm, 70 * mm, bold=True)
        _draw_wrapped_text(pdf, f"ИНН: {block['inn']}", block_x, y - 12 * mm, 70 * mm)
        _draw_wrapped_text(pdf, f"Адрес: {block['address']}", block_x, y - 18 * mm, 70 * mm)
    y -= 30 * mm
    _draw_text(pdf, "Позиции поставки", margin_x, y, bold=True, size=12)
    y -= 8 * mm
    for index, item in enumerate(upd["items"], start=1):
        _draw_text(pdf, f"{index}. {item['name']}", margin_x, y)
        _draw_text(pdf, f"{item['quantity']} шт. × {item['price']:.2f} = {item['total']:.2f} ₽", 125 * mm, y)
        y -= 7 * mm
    y -= 6 * mm
    _draw_text(pdf, f"Сумма документа: {upd['total_amount']:.2f} ₽", margin_x, y, bold=True)
    y -= 6 * mm
    _draw_text(pdf, f"Ставка НДС: {upd['vat_rate']}", margin_x, y)


def _render_act_pdf(pdf: canvas.Canvas, act: dict):
    width, height = A4
    margin_x = 18 * mm
    y = height - 22 * mm
    _draw_text(pdf, "TruckHub Service", margin_x, y, bold=True, size=18)
    y -= 10 * mm
    _draw_text(pdf, f"Акт {act['act_number']}", margin_x, y, bold=True, size=16)
    _draw_text(pdf, f"Заказ: {act['order_number']}", 125 * mm, y, size=10)
    y -= 7 * mm
    _draw_text(pdf, f"Дата: {act['date'][:19].replace('T', ' ')}", 125 * mm, y, size=10)
    y -= 14 * mm
    _draw_text(pdf, "Исполнитель", margin_x, y, bold=True, size=11)
    _draw_wrapped_text(pdf, act["executor"]["name"], margin_x, y - 6 * mm, 70 * mm, bold=True)
    _draw_wrapped_text(pdf, f"ИНН: {act['executor']['inn']}", margin_x, y - 12 * mm, 70 * mm)
    _draw_wrapped_text(pdf, f"Адрес: {act['executor']['address']}", margin_x, y - 18 * mm, 70 * mm)
    _draw_text(pdf, "Заказчик", 105 * mm, y, bold=True, size=11)
    _draw_wrapped_text(pdf, act["customer"]["name"], 105 * mm, y - 6 * mm, 70 * mm, bold=True)
    _draw_wrapped_text(pdf, f"ИНН: {act['customer']['inn']}", 105 * mm, y - 12 * mm, 70 * mm)
    y -= 30 * mm
    _draw_text(pdf, "Оказанные услуги", margin_x, y, bold=True, size=12)
    y -= 8 * mm
    if act["services"]:
        for index, item in enumerate(act["services"], start=1):
            _draw_text(pdf, f"{index}. {item['name']}", margin_x, y)
            _draw_text(pdf, f"{item['quantity']} × {item['price']:.2f} = {item['total']:.2f} ₽", 125 * mm, y)
            y -= 7 * mm
    else:
        _draw_text(pdf, "Услуги установки в заказе отсутствуют.", margin_x, y)
        y -= 7 * mm
    y -= 6 * mm
    _draw_text(pdf, f"Итого по акту: {act['total_amount']:.2f} ₽", margin_x, y, bold=True)
    y -= 14 * mm
    _draw_text(pdf, f"Исполнитель: {act['signature_executor']}", margin_x, y)
    _draw_text(pdf, f"Заказчик: {act['signature_customer']}", 105 * mm, y)


def _build_shipment_invoice(order: Order, shipment: dict, current_user: User) -> dict:
    total_amount = shipment["total_amount"]
    vat_rate = 20 if current_user.inn else 0
    vat_amount = total_amount * 0.2 if current_user.inn else 0
    total_with_vat = total_amount * 1.2 if current_user.inn else total_amount

    return {
        "document_type": "SHIPMENT_INVOICE",
        "invoice_number": f"INV-{order.order_number}-{(shipment['supplier_id'] or 'na')[:6]}",
        "order_number": order.order_number,
        "shipment_supplier_name": shipment["supplier_name"],
        "date": datetime.now().isoformat(),
        "seller": {
            "name": shipment["supplier_name"] or "TruckHub Supplier",
            "inn": "0000000000",
            "address": "г. Москва, адрес поставщика",
        },
        "buyer": {
            "name": current_user.company_name or current_user.email,
            "inn": current_user.inn or "Не указан",
            "address": current_user.address or "Не указан",
        },
        "items": [
            {
                "name": f"Товар {item['product_id'][:8]}",
                "quantity": item["quantity"],
                "price": item["unit_price"],
                "total": item["total_price"],
            }
            for item in shipment["items"]
        ],
        "total_amount": total_amount,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "total_with_vat": total_with_vat,
        "tracking_number": shipment["tracking_number"],
        "shipment_status": shipment["status"],
    }


def _build_shipment_upd(order: Order, shipment: dict, current_user: User) -> dict:
    return {
        "document_type": "SHIPMENT_UPD",
        "invoice_number": f"UPD-{order.order_number}-{(shipment['supplier_id'] or 'na')[:6]}",
        "order_number": order.order_number,
        "shipment_supplier_name": shipment["supplier_name"],
        "date": datetime.now().isoformat(),
        "seller": {
            "name": shipment["supplier_name"] or "TruckHub Supplier",
            "inn": "0000000000",
            "address": "г. Москва, адрес поставщика",
        },
        "buyer": {
            "name": current_user.company_name or current_user.email,
            "inn": current_user.inn or "Не указан",
            "address": current_user.address or "Не указан",
        },
        "items": [
            {
                "name": f"Товар {item['product_id'][:8]}",
                "quantity": item["quantity"],
                "price": item["unit_price"],
                "total": item["total_price"],
            }
            for item in shipment["items"]
        ],
        "total_amount": shipment["total_amount"],
        "vat_rate": "Без НДС" if not current_user.inn else "20%",
        "tracking_number": shipment["tracking_number"],
        "shipment_status": shipment["status"],
    }


@router.get("/lifecycle/{order_id}")
async def get_document_lifecycle(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    order, items, has_installation = await _get_order_with_items(order_id, current_user, db)
    if not order:
        return JSONResponse(status_code=404, content={"detail": "Order not found"})

    shipments = _build_shipment_groups(items)
    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "lifecycle": _build_document_lifecycle(order, items, has_installation),
        "shipments": shipments,
    }


@router.get("/invoice/{order_id}")
async def generate_invoice(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    order, items, has_installation = await _get_order_with_items(order_id, current_user, db)
    if not order:
        return JSONResponse(status_code=404, content={"detail": "Order not found"})

    invoice = {
        "document_type": "INVOICE",
        "invoice_number": f"INV-{order.order_number}",
        "order_number": order.order_number,
        "date": datetime.now().isoformat(),
        "seller": {
            "name": "TruckHub",
            "inn": "0000000000",
            "address": "г. Москва, ул. Примерная, д. 1",
        },
        "buyer": {
            "name": current_user.company_name or f"{current_user.email}",
            "inn": current_user.inn or "Не указан",
            "address": current_user.address or "Не указан",
        },
        "items": [
            {
                "name": f"Товар {item.product_id[:8]}",
                "quantity": item.quantity,
                "price": item.unit_price,
                "total": item.total_price,
            }
            for item in items
        ],
        "total_amount": order.total_amount,
        "vat_rate": 20 if current_user.inn else 0,
        "vat_amount": order.total_amount * 0.2 if current_user.inn else 0,
        "total_with_vat": order.total_amount * 1.2 if current_user.inn else order.total_amount,
        "lifecycle": _build_document_lifecycle(order, items, has_installation),
    }
    return invoice


@router.get("/upd/{order_id}")
async def generate_upd(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    order, items, has_installation = await _get_order_with_items(order_id, current_user, db)
    if not order:
        return JSONResponse(status_code=404, content={"detail": "Order not found"})

    upd = {
        "document_type": "UPD",
        "invoice_number": f"UPD-{order.order_number}",
        "order_number": order.order_number,
        "date": datetime.now().isoformat(),
        "seller": {
            "name": "TruckHub",
            "inn": "0000000000",
            "address": "г. Москва, ул. Примерная, д. 1",
        },
        "buyer": {
            "name": current_user.company_name or f"{current_user.email}",
            "inn": current_user.inn or "Не указан",
            "address": current_user.address or "Не указан",
        },
        "items": [
            {
                "name": f"Товар {item.product_id[:8]}",
                "quantity": item.quantity,
                "price": item.unit_price,
                "total": item.total_price,
            }
            for item in items
        ],
        "total_amount": order.total_amount,
        "vat_rate": "Без НДС" if not current_user.inn else "20%",
        "acts": [],
        "lifecycle": _build_document_lifecycle(order, items, has_installation),
    }
    return upd


@router.get("/act/{order_id}")
async def generate_act(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    order, items, _ = await _get_order_with_items(order_id, current_user, db)
    if not order:
        return JSONResponse(status_code=404, content={"detail": "Order not found"})

    installation_items = [item for item in items if item.is_installation]
    has_installation = len(installation_items) > 0

    act = {
        "document_type": "ACT",
        "act_number": f"ACT-{order.order_number}",
        "order_number": order.order_number,
        "date": datetime.now().isoformat(),
        "executor": {
            "name": "TruckHub Service",
            "inn": "0000000000",
            "address": "г. Москва, ул. Сервисная, д. 1",
        },
        "customer": {
            "name": current_user.company_name or f"{current_user.email}",
            "inn": current_user.inn or "Не указан",
        },
        "services": [
            {
                "name": f"Услуга установки {item.product_id[:8]}",
                "quantity": item.quantity,
                "price": item.unit_price,
                "total": item.total_price,
            }
            for item in installation_items
        ],
        "total_amount": sum(item.total_price for item in installation_items),
        "signature_executor": "TruckHub",
        "signature_customer": current_user.email,
        "lifecycle": _build_document_lifecycle(order, items, has_installation),
    }
    return act


@router.get("/shipment/{order_id}/invoice/{supplier_id}")
async def generate_shipment_invoice(
    order_id: str,
    supplier_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    order, items, _ = await _get_order_with_items(order_id, current_user, db)
    if not order:
        return JSONResponse(status_code=404, content={"detail": "Order not found"})

    shipments = _build_shipment_groups(items)
    shipment = next((shipment for shipment in shipments if (shipment["supplier_id"] or "unknown") == supplier_id), None)
    if not shipment:
        return JSONResponse(status_code=404, content={"detail": "Shipment not found"})
    return _build_shipment_invoice(order, shipment, current_user)


@router.get("/shipment/{order_id}/upd/{supplier_id}")
async def generate_shipment_upd(
    order_id: str,
    supplier_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    order, items, _ = await _get_order_with_items(order_id, current_user, db)
    if not order:
        return JSONResponse(status_code=404, content={"detail": "Order not found"})

    shipments = _build_shipment_groups(items)
    shipment = next((shipment for shipment in shipments if (shipment["supplier_id"] or "unknown") == supplier_id), None)
    if not shipment:
        return JSONResponse(status_code=404, content={"detail": "Shipment not found"})
    return _build_shipment_upd(order, shipment, current_user)


@router.get("/invoice/{order_id}/pdf")
async def generate_invoice_pdf(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not REPORTLAB_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"detail": "PDF generation is temporarily unavailable on the server"},
        )
    invoice = await generate_invoice(order_id, current_user, db)
    if isinstance(invoice, JSONResponse):
        return invoice
    return _create_pdf_response(
        _document_filename("invoice", invoice["order_number"]),
        lambda pdf: _render_invoice_pdf(pdf, invoice),
    )


@router.get("/upd/{order_id}/pdf")
async def generate_upd_pdf(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not REPORTLAB_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"detail": "PDF generation is temporarily unavailable on the server"},
        )
    upd = await generate_upd(order_id, current_user, db)
    if isinstance(upd, JSONResponse):
        return upd
    return _create_pdf_response(
        _document_filename("upd", upd["order_number"]),
        lambda pdf: _render_upd_pdf(pdf, upd),
    )


@router.get("/act/{order_id}/pdf")
async def generate_act_pdf(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not REPORTLAB_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"detail": "PDF generation is temporarily unavailable on the server"},
        )
    act = await generate_act(order_id, current_user, db)
    if isinstance(act, JSONResponse):
        return act
    return _create_pdf_response(
        _document_filename("act", act["order_number"]),
        lambda pdf: _render_act_pdf(pdf, act),
    )


@router.get("/shipment/{order_id}/invoice/{supplier_id}/pdf")
async def generate_shipment_invoice_pdf(
    order_id: str,
    supplier_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not REPORTLAB_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"detail": "PDF generation is temporarily unavailable on the server"},
        )
    invoice = await generate_shipment_invoice(order_id, supplier_id, current_user, db)
    if isinstance(invoice, JSONResponse):
        return invoice
    return _create_pdf_response(
        _document_filename("shipment-invoice", invoice["order_number"], supplier_id[:6]),
        lambda pdf: _render_invoice_pdf(pdf, invoice),
    )


@router.get("/shipment/{order_id}/upd/{supplier_id}/pdf")
async def generate_shipment_upd_pdf(
    order_id: str,
    supplier_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not REPORTLAB_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"detail": "PDF generation is temporarily unavailable on the server"},
        )
    upd = await generate_shipment_upd(order_id, supplier_id, current_user, db)
    if isinstance(upd, JSONResponse):
        return upd
    return _create_pdf_response(
        _document_filename("shipment-upd", upd["order_number"], supplier_id[:6]),
        lambda pdf: _render_upd_pdf(pdf, upd),
    )