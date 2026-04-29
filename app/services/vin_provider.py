"""Laximo-style VIN decoder provider.

Supports two modes:
- mock: returns realistic demo data based on VIN pattern parsing
- http: calls real Laximo SOAP API (requires LAXIMO_USER / LAXIMO_PASSWORD env vars)
"""

import re
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── VIN pattern helpers ──────────────────────────────────────────────

WMI_MAP: Dict[str, Dict[str, Any]] = {
    "WF0": {"brand": "Ford", "country": "Турция"},
    "XTA": {"brand": "KAMAZ", "country": "Россия"},
    "XTB": {"brand": "GAZ", "country": "Россия"},
    "XTC": {"brand": "MAZ", "country": "Беларусь"},
    "XTD": {"brand": "ZIL", "country": "Россия"},
    "XTE": {"brand": "UAZ", "country": "Россия"},
    "XTH": {"brand": "GAZ", "country": "Россия"},
    "XTJ": {"brand": "ZMZ", "country": "Россия"},
    "X0L": {"brand": "KAMAZ", "country": "Россия"},
    "1FV": {"brand": "Freightliner", "country": "USA"},
    "1FU": {"brand": "Freightliner", "country": "USA"},
    "1NV": {"brand": "Navistar", "country": "USA"},
    "1XP": {"brand": "Peterbilt", "country": "USA"},
    "1XK": {"brand": "Kenworth", "country": "USA"},
    "2NP": {"brand": "Peterbilt", "country": "Канада"},
    "2NK": {"brand": "Kenworth", "country": "Канада"},
    "3AL": {"brand": "Freightliner", "country": "Мексика"},
    "3BK": {"brand": "Kenworth", "country": "Мексика"},
    "4VZ": {"brand": "Volvo", "country": "USA"},
    "4U5": {"brand": "Mack", "country": "USA"},
    "5BP": {"brand": "Scania", "country": "Бразилия"},
    "6F4": {"brand": "Scania", "country": "Швеция"},
    "YV2": {"brand": "Volvo", "country": "Швеция"},
    "YV3": {"brand": "Volvo", "country": "Швеция"},
    "WDB": {"brand": "Mercedes-Benz", "country": "Германия"},
    "WDC": {"brand": "Mercedes-Benz", "country": "Германия"},
    "WDD": {"brand": "Mercedes-Benz", "country": "Германия"},
    "NMB": {"brand": "MAN", "country": "Германия"},
    "WMA": {"brand": "MAN", "country": "Германия"},
    "TDM": {"brand": "DAF", "country": "Нидерланды"},
    "TRU": {"brand": "DAF", "country": "Нидерланды"},
    "ZAR": {"brand": "Iveco", "country": "Италия"},
    "ZCG": {"brand": "Iveco", "country": "Италия"},
    "SAL": {"brand": "Scania", "country": "Швеция"},
    "KSJ": {"brand": "Hyundai", "country": "Корея"},
    "KPH": {"brand": "Kia", "country": "Корея"},
    "JTF": {"brand": "Hino", "country": "Япония"},
    "JHM": {"brand": "Isuzu", "country": "Япония"},
}

MODEL_HINTS: Dict[str, List[Dict[str, Any]]] = {
    "KAMAZ": [
        {"pattern": r"5490", "model": "5490", "body_type": "Седельный тягач", "engine": "Cummins ISL9.5", "chassis": "6x4", "gvw": 24000},
        {"pattern": r"6520", "model": "6520", "body_type": "Самосвал", "engine": "KAMAZ 740.63", "chassis": "6x4", "gvw": 27500},
        {"pattern": r"6511[57]", "model": "65115", "body_type": "Самосвал", "engine": "KAMAZ 740.62", "chassis": "6x4", "gvw": 25200},
        {"pattern": r"4311[48]", "model": "43118", "body_type": "Вездеход", "engine": "KAMAZ 740.55", "chassis": "6x6", "gvw": 21600},
        {"pattern": r"6522", "model": "6522", "body_type": "Самосвал", "engine": "KAMAZ 740.63", "chassis": "6x6", "gvw": 27500},
        {"pattern": r"4410[89]", "model": "44108", "body_type": "Седельный тягач", "engine": "KAMAZ 740.55", "chassis": "6x6", "gvw": 21800},
    ],
    "Mercedes-Benz": [
        {"pattern": r"184[0-9]", "model": "Actros 1845", "body_type": "Седельный тягач", "engine": "OM 471", "chassis": "4x2", "gvw": 18000},
        {"pattern": r"Actros|1848|1851", "model": "Actros", "body_type": "Седельный тягач", "engine": "OM 471/473", "chassis": "4x2/6x4", "gvw": 26000},
        {"pattern": r"Atego|102[0-9]", "model": "Atego", "body_type": "Среднетоннажный", "engine": "OM 936", "chassis": "4x2", "gvw": 16000},
        {"pattern": r"Axor|204[0-9]", "model": "Axor", "body_type": "Седельный тягач", "engine": "OM 457", "chassis": "4x2", "gvw": 19000},
    ],
    "Volvo": [
        {"pattern": r"FH|FH1[234]", "model": "FH", "body_type": "Седельный тягач", "engine": "D13K", "chassis": "4x2/6x4", "gvw": 20000},
        {"pattern": r"FM|FM1[23]", "model": "FM", "body_type": "Самосвал/Тягач", "engine": "D11K/D13K", "chassis": "4x2/6x4", "gvw": 26000},
        {"pattern": r"FMX", "model": "FMX", "body_type": "Вездеход", "engine": "D11K/D13K", "chassis": "6x4/6x6", "gvw": 27000},
    ],
    "Scania": [
        {"pattern": r"[RSGT]", "model": "R-series", "body_type": "Седельный тягач", "engine": "DC13", "chassis": "4x2/6x4", "gvw": 20000},
        {"pattern": r"P", "model": "P-series", "body_type": "Среднетоннажный", "engine": "DC09/DC13", "chassis": "4x2", "gvw": 18000},
        {"pattern": r"G", "model": "G-series", "body_type": "Седельный тягач", "engine": "DC13", "chassis": "4x2/6x2", "gvw": 24000},
    ],
    "MAN": [
        {"pattern": r"TGX", "model": "TGX", "body_type": "Седельный тягач", "engine": "D2676", "chassis": "4x2/6x4", "gvw": 26000},
        {"pattern": r"TGS", "model": "TGS", "body_type": "Самосвал/Строительный", "engine": "D2067/D2676", "chassis": "6x4/8x4", "gvw": 33000},
        {"pattern": r"TGL", "model": "TGL", "body_type": "Среднетоннажный", "engine": "D0836", "chassis": "4x2", "gvw": 12000},
    ],
    "DAF": [
        {"pattern": r"XF", "model": "XF", "body_type": "Седельный тягач", "engine": "MX-13", "chassis": "4x2/6x4", "gvw": 26000},
        {"pattern": r"CF", "model": "CF", "body_type": "Универсальный", "engine": "MX-11", "chassis": "4x2/6x2", "gvw": 24000},
        {"pattern": r"LF", "model": "LF", "body_type": "Среднетоннажный", "engine": "PACCAR GR", "chassis": "4x2", "gvw": 12000},
    ],
    "Iveco": [
        {"pattern": r"Stralis|S-Way", "model": "S-Way", "body_type": "Седельный тягач", "engine": "Cursor 13", "chassis": "4x2/6x4", "gvw": 26000},
        {"pattern": r"Trakker", "model": "Trakker", "body_type": "Вездеход/Самосвал", "engine": "Cursor 13", "chassis": "6x4/8x4", "gvw": 33000},
        {"pattern": r"Daily", "model": "Daily", "body_type": "Фургон", "engine": "F1A/F1C", "chassis": "4x2", "gvw": 7200},
    ],
    "Freightliner": [
        {"pattern": r"Cascadia", "model": "Cascadia", "body_type": "Седельный тягач", "engine": "Detroit DD15", "chassis": "6x4", "gvw": 26000},
        {"pattern": r"Columbia", "model": "Columbia", "body_type": "Седельный тягач", "engine": "Detroit DD15", "chassis": "6x4", "gvw": 26000},
    ],
    "Kenworth": [
        {"pattern": r"T680", "model": "T680", "body_type": "Седельный тягач", "engine": "PACCAR MX-13", "chassis": "6x4", "gvw": 26000},
        {"pattern": r"W900", "model": "W900", "body_type": "Седельный тягач", "engine": "Cummins X15", "chassis": "6x4", "gvw": 26000},
    ],
    "Peterbilt": [
        {"pattern": r"579", "model": "579", "body_type": "Седельный тягач", "engine": "PACCAR MX-13", "chassis": "6x4", "gvw": 26000},
        {"pattern": r"389", "model": "389", "body_type": "Седельный тягач", "engine": "Cummins X15", "chassis": "6x4", "gvw": 26000},
    ],
    "Mack": [
        {"pattern": r"Anthem", "model": "Anthem", "body_type": "Седельный тягач", "engine": "MP8", "chassis": "6x4", "gvw": 26000},
        {"pattern": r"Granite", "model": "Granite", "body_type": "Самосвал", "engine": "MP8", "chassis": "6x4/8x4", "gvw": 33000},
    ],
}

VEHICLE_TREE: List[Dict[str, Any]] = [
    {
        "id": "engine",
        "name": "Двигатель",
        "icon": "engine",
        "children": [
            {"id": "engine_gasket", "name": "Прокладки двигателя", "keywords": ["прокладк", "головк", "блок", "ГБЦ"]},
            {"id": "engine_pistons", "name": "Поршневая группа", "keywords": ["поршен", "поршн", "кольц", "шатун", "гильз"]},
            {"id": "engine_crankshaft", "name": "Коленвал и вкладыши", "keywords": ["коленвал", "вкладыш", "вал"]},
            {"id": "engine_turbo", "name": "Турбокомпрессор", "keywords": ["турб", "компрессор", "наддув"]},
            {"id": "engine_fuel", "name": "Топливная система", "keywords": ["форсунк", "ТНВД", "насос", "топлив", "рамп", "common rail"]},
            {"id": "engine_cooling", "name": "Система охлаждения", "keywords": ["радиатор", "помп", "охлажд", "термостат", "вентилятор", "антифриз"]},
            {"id": "engine_oil", "name": "Смазочная система", "keywords": ["масл", "фильтр масл", "картер"]},
            {"id": "engine_sensors", "name": "Датчики двигателя", "keywords": ["датчик", "сенсор", "температур", "давлен"]},
        ],
    },
    {
        "id": "transmission",
        "name": "Трансмиссия",
        "icon": "transmission",
        "children": [
            {"id": "trans_clutch", "name": "Сцепление", "keywords": ["сцеплен", "диск", "корзин", "выжимн"]},
            {"id": "trans_gearbox", "name": "КПП", "keywords": ["коробк", "передач", "шестерн", "синхронизатор"]},
            {"id": "trans_driveshaft", "name": "Кардан", "keywords": ["кардан", "крестовин", "подвесн"]},
            {"id": "trans_rear_axle", "name": "Задний мост", "keywords": ["мост", "редуктор", "дифференциал", "полуос"]},
        ],
    },
    {
        "id": "brakes",
        "name": "Тормозная система",
        "icon": "brakes",
        "children": [
            {"id": "brake_pads", "name": "Колодки и диски", "keywords": ["колодк", "диск тормоз", "накладк"]},
            {"id": "brake_drums", "name": "Барабаны", "keywords": ["барабан", "тормозн"]},
            {"id": "brake_valves", "name": "Краны и клапаны", "keywords": ["кран", "клапан", "регулятор тормоз", "AB"]},
            {"id": "brake_compressor", "name": "Компрессор пневмотормозов", "keywords": ["компрессор", "пневмо"]},
        ],
    },
    {
        "id": "suspension",
        "name": "Подвеска и рама",
        "icon": "suspension",
        "children": [
            {"id": "sus_springs", "name": "Рессоры и пружины", "keywords": ["рессор", "пружин", "лист"]},
            {"id": "sus_shock", "name": "Амортизаторы", "keywords": ["амортизатор", "стойк"]},
            {"id": "sus_air", "name": "Пневмоподвеска", "keywords": ["пневмобаллон", "пневмо", "подвеск"]},
            {"id": "sus_bushings", "name": "Сайлентблоки и втулки", "keywords": ["сайлентблок", "втулк", "подушк"]},
        ],
    },
    {
        "id": "cab",
        "name": "Кабина и оперение",
        "icon": "cab",
        "children": [
            {"id": "cab_glass", "name": "Стёкла", "keywords": ["стекло", "лобов", "зерк"]},
            {"id": "cab_doors", "name": "Двери и замки", "keywords": ["двер", "замок", "ручк"]},
            {"id": "cab_seats", "name": "Сиденья", "keywords": ["сидень", "кресл", "подлокотник"]},
            {"id": "cab_climate", "name": "Отопление и кондиционер", "keywords": ["отоплен", "кондицион", "печк", "климат"]},
            {"id": "cab_electric", "name": "Электрика кабины", "keywords": ["проводк", "реле", "предохран", "переключ", "фар"]},
        ],
    },
    {
        "id": "electrical",
        "name": "Электрооборудование",
        "icon": "electrical",
        "children": [
            {"id": "elec_starter", "name": "Стартер", "keywords": ["стартер"]},
            {"id": "elec_alternator", "name": "Генератор", "keywords": ["генератор", "альтернатор"]},
            {"id": "elec_battery", "name": "Аккумуляторы", "keywords": ["аккумулятор", "батаре", "АКБ"]},
            {"id": "elec_lighting", "name": "Освещение", "keywords": ["фар", "ламп", "поворотник", "габарит", "светодиод"]},
            {"id": "elec_ecu", "name": "Блоки управления (ECU)", "keywords": ["ECU", "блок управлен", "контроллер"]},
        ],
    },
    {
        "id": "chassis_body",
        "name": "Шасси и надстройка",
        "icon": "chassis",
        "children": [
            {"id": "ch_frame", "name": "Рама и детали", "keywords": ["рам", "лонжерон", "кронштейн", "попереч"]},
            {"id": "ch_fifth_wheel", "name": "Седельно-сцепное устройство", "keywords": ["седло", "сцепн", "к шквор", "пятое колес"]},
            {"id": "ch_wheels", "name": "Колёса и шины", "keywords": ["колес", "шин", "диск колес", "ступиц", "подшипник"]},
            {"id": "ch_exhaust", "name": "Выхлопная система", "keywords": ["глушител", "выпуск", "выхлоп", "катализатор", "AdBlue", "SCR"]},
        ],
    },
]


def _parse_vin(vin: str) -> Dict[str, Any]:
    """Parse VIN string into structured vehicle info using pattern matching."""
    vin = vin.upper().strip()
    wmi = vin[:3]

    wmi_info = WMI_MAP.get(wmi, {"brand": "Unknown", "country": "Не определено"})
    brand = wmi_info["brand"]
    country = wmi_info.get("country", "")

    year = None
    if len(vin) >= 10:
        year_char = vin[9]
        year_map = {
            "A": 2010, "B": 2011, "C": 2012, "D": 2013, "E": 2014,
            "F": 2015, "G": 2016, "H": 2017, "J": 2018, "K": 2019,
            "L": 2020, "M": 2021, "N": 2022, "P": 2023, "R": 2024,
            "S": 2025, "T": 2026, "V": 2027, "W": 2028, "X": 2029,
            "Y": 2030, "1": 2031, "2": 2032, "3": 2033, "4": 2034,
            "5": 2035, "6": 2036, "7": 2037, "8": 2038, "9": 2039,
        }
        year = year_map.get(year_char)

    model_info: Dict[str, Any] = {}
    model_hints = MODEL_HINTS.get(brand, [])
    for hint in model_hints:
        if re.search(hint["pattern"], vin) or re.search(hint["pattern"], brand):
            model_info = hint
            break

    if not model_info and model_hints:
        model_info = model_hints[0]

    return {
        "vin": vin,
        "wmi": wmi,
        "brand": brand,
        "country": country,
        "model": model_info.get("model", "Не определена"),
        "year": year,
        "engine": model_info.get("engine", "Не определён"),
        "chassis": model_info.get("chassis", "Не определён"),
        "body_type": model_info.get("body_type", "Не определён"),
        "gvw": model_info.get("gvw"),
    }


# ── Providers ────────────────────────────────────────────────────────

class MockLaximoProvider:
    """Mock VIN decoder that uses local pattern matching for demo/testing."""

    name = "mock_laximo"

    def health(self) -> Dict[str, Any]:
        return {"status": "ok", "provider": self.name}

    def decode_vin(self, vin: str) -> Dict[str, Any]:
        info = _parse_vin(vin)
        info["source"] = "mock_laximo"
        return info

    def get_vehicle_tree(self, vin: str) -> List[Dict[str, Any]]:
        return VEHICLE_TREE


class HttpLaximoProvider:
    """Real Laximo SOAP API integration.

    Requires environment variables:
    - LAXIMO_API_URL: base URL (e.g. https://ws.laximo.ru)
    - LAXIMO_USER: API user
    - LAXIMO_PASSWORD: API password
    """

    name = "http_laximo"

    def __init__(self) -> None:
        self.api_url = getattr(settings, "LAXIMO_API_URL", "") or "https://ws.laximo.ru"
        self.user = getattr(settings, "LAXIMO_USER", "")
        self.password = getattr(settings, "LAXIMO_PASSWORD", "")

    def health(self) -> Dict[str, Any]:
        if self.user and self.password:
            return {"status": "ok", "provider": self.name, "configured": True}
        return {"status": "degraded", "provider": self.name, "configured": False, "note": "credentials not set"}

    def decode_vin(self, vin: str) -> Dict[str, Any]:
        if not self.user or not self.password:
            logger.warning("laximo_credentials_missing, falling back to mock")
            return MockLaximoProvider().decode_vin(vin)

        try:
            return self._call_find_vehicle(vin)
        except Exception as exc:
            logger.exception("laximo_decode_vin_failed", extra={"extra": {"vin": vin, "error": str(exc)}})
            return MockLaximoProvider().decode_vin(vin)

    def get_vehicle_tree(self, vin: str) -> List[Dict[str, Any]]:
        if not self.user or not self.password:
            return VEHICLE_TREE

        try:
            return self._call_vehicle_tree(vin)
        except Exception as exc:
            logger.exception("laximo_vehicle_tree_failed", extra={"extra": {"vin": vin, "error": str(exc)}})
            return VEHICLE_TREE

    def _call_find_vehicle(self, vin: str) -> Dict[str, Any]:
        import httpx

        soap_body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:cat="http://laximo.ru/catalog/">'
            '<soap:Body>'
            f'<cat:FindVehicle>'
            f'<cat:VIN>{vin}</cat:VIN>'
            f'<cat:User>{self.user}</cat:User>'
            f'<cat:Password>{self.password}</cat:Password>'
            f'</cat:FindVehicle>'
            '</soap:Body>'
            '</soap:Envelope>'
        )

        resp = httpx.post(
            self.api_url,
            content=soap_body,
            headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "FindVehicle"},
            timeout=15.0,
        )
        resp.raise_for_status()
        return self._parse_find_vehicle_response(resp.text, vin)

    def _call_vehicle_tree(self, vin: str) -> List[Dict[str, Any]]:
        import httpx

        soap_body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:cat="http://laximo.ru/catalog/">'
            '<soap:Body>'
            f'<cat:GetVehicleTree>'
            f'<cat:VIN>{vin}</cat:VIN>'
            f'<cat:User>{self.user}</cat:User>'
            f'<cat:Password>{self.password}</cat:Password>'
            f'</cat:GetVehicleTree>'
            '</soap:Body>'
            '</soap:Envelope>'
        )

        resp = httpx.post(
            self.api_url,
            content=soap_body,
            headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "GetVehicleTree"},
            timeout=15.0,
        )
        resp.raise_for_status()
        return self._parse_vehicle_tree_response(resp.text)

    def _parse_find_vehicle_response(self, xml_text: str, vin: str) -> Dict[str, Any]:
        """Parse Laximo SOAP FindVehicle response XML."""
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(xml_text)
            ns = {"cat": "http://laximo.ru/catalog/"}
            vehicle = root.find(".//cat:vehicle", ns)
            if vehicle is None:
                vehicle = root.find(".//vehicle")

            if vehicle is not None:
                def _get(tag: str) -> Optional[str]:
                    el = vehicle.find(f"cat:{tag}", ns) or vehicle.find(f".//{tag}")
                    return el.text if el is not None else None

                return {
                    "vin": vin,
                    "brand": _get("brand") or _get("make") or "Unknown",
                    "model": _get("model") or "Не определена",
                    "year": int(_get("year") or 0) or None,
                    "engine": _get("engine") or _get("engineCode") or "Не определён",
                    "chassis": _get("chassis") or _get("driveType") or "Не определён",
                    "body_type": _get("bodyType") or _get("body") or "Не определён",
                    "country": _get("country") or "",
                    "source": "laximo_api",
                }
        except ET.ParseError:
            logger.warning("laximo_xml_parse_error")

        return MockLaximoProvider().decode_vin(vin)

    def _parse_vehicle_tree_response(self, xml_text: str) -> List[Dict[str, Any]]:
        """Parse Laximo SOAP GetVehicleTree response XML."""
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(xml_text)
            ns = {"cat": "http://laximo.ru/catalog/"}
            units = root.findall(".//cat:unit", ns)
            if not units:
                units = root.findall(".//unit")

            tree: List[Dict[str, Any]] = []
            for unit in units:
                unit_id = unit.get("unitId") or unit.get("id") or ""
                name_el = unit.find("cat:name", ns) or unit.find("name")
                name = name_el.text if name_el is not None else unit.get("name", "")
                tree.append({
                    "id": unit_id,
                    "name": name,
                    "icon": "unit",
                    "children": [],
                })

            return tree if tree else VEHICLE_TREE
        except ET.ParseError:
            return VEHICLE_TREE
