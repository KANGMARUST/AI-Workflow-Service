import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from .domain import parse_json_field
from .schemas import QuoteFields, QuoteItem

MISSING = {"", "미기재", "미정", "없음", "n/a", "null", "none", "-", "불명"}


def scalar(value):
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict) and "value" in value:
        value = value["value"]
    return value


def normalize_result(source):
    if not isinstance(source, dict):
        raise ValueError("추출 결과는 객체여야 합니다.")
    warnings = []
    data = {}
    numeric = {"subtotal", "tax_amount", "tax_rate", "total_amount", "quantity", "unit_price", "amount"}
    dates = {"issue_date", "valid_until", "delivery_date"}

    def clean(key, value, path):
        value = scalar(value)
        if key in ("discount_terms", "payment_terms", "delivery_terms", "notes") and value == "없음":
            return value
        if value is None or str(value).strip().casefold() in MISSING:
            return None
        if key in numeric:
            text = str(value).strip().replace(",", "")
            if key == "tax_amount" and text.endswith("%"):
                warnings.append(f"{path}: 세율만 기재되어 세액을 확정할 수 없습니다.")
                return None
            # No calculation, only an explicitly written decimal plus known units.
            text = re.sub(r"^(KRW|USD|EUR|₩|\$|€)\s*|\s*(원|개|EA|%|KRW|USD|EUR)$", "", text, flags=re.I).strip()
            try:
                number = Decimal(text)
                if not number.is_finite() or number < 0:
                    raise InvalidOperation
                return str(number)
            except InvalidOperation:
                warnings.append(f"{path}: 숫자 형식이 불명확합니다. 원문을 확인하세요.")
                return None
        if key in dates:
            text = re.sub(r"\s*([./-])\s*", r"\1", str(value).strip()).rstrip(".")
            for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y년 %m월 %d일"):
                try:
                    return datetime.strptime(text, fmt).date().isoformat()
                except ValueError:
                    continue
            warnings.append(f"{path}: 날짜를 확정할 수 없습니다.")
            return None
        if key == "currency":
            text = {"원": "KRW", "₩": "KRW", "달러": "USD", "€": "EUR"}.get(str(value), str(value).upper())
            if not re.fullmatch(r"[A-Z]{3}", text):
                warnings.append(f"{path}: 통화를 확인하세요.")
                return None
            return text
        return str(value)

    for key in QuoteFields.model_fields:
        if key not in ("items", "raw_fields"):
            data[key] = clean(key, source.get(key), key)
    try:
        raw = parse_json_field(source.get("raw_fields_json", source.get("raw_fields")), {})
        data["raw_fields"] = raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, TypeError):
        data["raw_fields"] = {}
        warnings.append("원문 헤더 JSON을 해석하지 못했습니다.")
    rows = source.get("items", [])
    if not isinstance(rows, list):
        raise ValueError("품목 추출 결과는 배열이어야 합니다.")
    if len(rows) > 2000:
        raise ValueError("품목은 최대 2000행까지 지원합니다.")
    data["items"] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("품목 행은 객체여야 합니다.")
        item = {k: clean(k, row.get(k), f"items.{i}.{k}") for k in QuoteItem.model_fields if k != "raw_fields"}
        if not item.get("item_name"):
            item["item_name"] = "[품목명 확인 필요]"
            warnings.append(f"items.{i}: 품목명 확인이 필요합니다.")
        try:
            raw = parse_json_field(row.get("raw_fields_json", row.get("raw_fields")), {})
            item["raw_fields"] = raw if isinstance(raw, dict) else {}
        except (json.JSONDecodeError, TypeError):
            item["raw_fields"] = {}
            warnings.append(f"items.{i}: 원문 JSON을 해석하지 못했습니다.")
        data["items"].append(item)
    if source.get("review_warnings"):
        warnings.append(str(scalar(source["review_warnings"])))
    try:
        normalized = QuoteFields.model_validate(data).model_dump(mode="json")
    except ValidationError as exc:
        raise ValueError("추출 값의 길이·숫자 정밀도 또는 형식이 허용 범위를 벗어났습니다. 원본을 확인하세요.") from exc
    return normalized, warnings
