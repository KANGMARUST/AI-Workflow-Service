import json
import re
from decimal import Decimal, ROUND_HALF_UP, localcontext
from itertools import combinations

from .schemas import QuoteFields


def dec(value):
    return Decimal(str(value)) if value is not None and value != "" else None


def diagnostics(data: dict):
    warnings = []

    def warn(code, path, message):
        warnings.append({"code": code, "path": path, "message": message})

    for key in ("customer_name", "issue_date", "currency"):
        if not data.get(key):
            warn("missing_field", key, f"{key} 값이 없습니다. 원본을 확인하세요.")
    items = data.get("items", [])
    if not items:
        warn("missing_items", "items", "추출된 품목이 없습니다.")
    computed = []
    signatures = set()
    for i, item in enumerate(items):
        path = f"items.{i}"
        for key in ("specification", "unit", "quantity", "unit_price", "amount"):
            if item.get(key) is None or item.get(key) == "":
                warn("missing_field", f"{path}.{key}", f"품목 {i+1}의 {key} 값이 없습니다.")
        quantity, price, amount = (dec(item.get(k)) for k in ("quantity", "unit_price", "amount"))
        with localcontext() as ctx:
            ctx.prec = 38
            product = quantity * price if quantity is not None and price is not None else None
        computed.append(str(product) if product is not None else None)
        if product is not None and amount is not None and product != amount:
            warn("line_amount_mismatch", path, f"품목 {i+1}: 수량×단가 {product}와 원문 금액 {amount}가 다릅니다. 할인/반올림 조건도 확인하세요.")
        signature = tuple(item.get(k) for k in ("item_name", "specification", "unit", "quantity", "unit_price", "amount"))
        if signature in signatures:
            warn("possible_duplicate_item", path, "같은 내용의 품목 행이 있습니다. 원본의 반복 행인지 확인하세요.")
        signatures.add(signature)
    amounts = [dec(x.get("amount")) for x in items]
    total_lines = sum(amounts, Decimal(0)) if items and all(x is not None for x in amounts) else None
    subtotal, tax, total = (dec(data.get(k)) for k in ("subtotal", "tax_amount", "total_amount"))
    line_basis = total if data.get("tax_basis") == "inclusive" else subtotal
    if total_lines is not None and line_basis is not None and total_lines != line_basis:
        warn("subtotal_mismatch", "subtotal", f"품목 금액 합계 {total_lines}와 세금 조건에 따른 합계 {line_basis}가 다릅니다. 옵션/구성품/할인 조건을 확인하세요.")
    currencies = {x.get("currency") or data.get("currency") for x in items}
    if len(currencies) > 1:
        warn("mixed_currencies", "items", "통화가 다른 품목의 금액을 합산할 수 없습니다.")
    if subtotal is not None and tax is not None and total is not None and subtotal + tax != total:
        warn("total_mismatch", "total_amount", "공급가액+세액과 총액이 다릅니다.")
    if total is None:
        warn("missing_total", "total_amount", "원본 총액이 명시되지 않았습니다. 자동 생성하지 않았습니다.")
    if not data.get("tax_basis"):
        warn("unknown_tax_basis", "tax_basis", "단가가 세금 포함인지 별도인지 확인하세요.")
    if data.get("discount_terms") and normalized(data["discount_terms"]) not in {"없음", "무할인", "할인없음", "none"}:
        warn("discount_requires_review", "discount_terms", "할인 조건은 자동 계산하지 않습니다. 적용 단가와 최종 금액을 확인하세요.")
    return {"warnings": warnings, "computed_item_amounts": computed, "computed_subtotal": str(total_lines) if total_lines is not None else None, "requires_review": True}


def normalized(value):
    return re.sub(r"\s+", "", str(value or "")).casefold()


def compare_quotes(quotes, item_name=None):
    rows, groups, excluded = [], {}, []
    for q in quotes:
        for i, item in enumerate(q.get("items", [])):
            if item_name and normalized(item_name) not in normalized(item["item_name"]):
                continue
            row = {**item, "quote_id": q["quote_id"], "line_number": i+1,
                   **{k: q.get(k) for k in ("customer_name", "issue_date", "payment_terms", "delivery_terms", "discount_terms", "tax_rate", "tax_terms", "tax_basis")}}
            row["currency"] = item.get("currency") or q.get("currency")
            rows.append(row)
            key = tuple(normalized(row.get(k)) for k in ("item_name", "specification", "unit", "currency"))
            if all(key) and row.get("unit_price") is not None:
                groups.setdefault(key, []).append(row)
            else:
                excluded.append({"quote_id": q["quote_id"], "line_number": i+1, "reason": "규격·단위·통화 또는 단가가 없어 비교할 수 없습니다."})
    pairs = []
    used = set()
    for group in groups.values():
        for a, b in combinations(group, 2):
            if a["quote_id"] == b["quote_id"]:
                continue
            used.update([(a["quote_id"], a["line_number"]), (b["quote_id"], b["line_number"])])
            differences = [k for k in ("quantity", "issue_date", "payment_terms", "delivery_terms", "discount_terms", "tax_rate", "tax_basis") if a.get(k) != b.get(k)]
            unknown = [k for k in ("quantity", "payment_terms", "delivery_terms", "tax_rate", "tax_basis") if a.get(k) is None or b.get(k) is None]
            before, after = dec(a["unit_price"]), dec(b["unit_price"])
            with localcontext() as ctx:
                ctx.prec = 38
                percent = ((after-before)/before*100).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if before else None
            pairs.append({"quote_ids": [a["quote_id"], b["quote_id"]], "line_numbers": [a["line_number"], b["line_number"]], "comparability": "conditional" if differences or unknown else "comparable", "condition_differences": differences, "unknown_conditions": unknown, "price_difference": str(after-before), "price_difference_percent": str(percent) if percent is not None else None})
    excluded_ids = {(x["quote_id"], x["line_number"]) for x in excluded}
    for row in rows:
        key = (row["quote_id"], row["line_number"])
        if key not in used and key not in excluded_ids:
            excluded.append({"quote_id": key[0], "line_number": key[1], "reason": "동일 품목·규격·단위·통화의 다른 견적이 없습니다."})
    status = "insufficient_data" if not pairs else "conditional" if any(x["comparability"] == "conditional" for x in pairs) else "comparable"
    return {"comparison_status": status, "rows": rows, "pairs": pairs, "excluded_rows": excluded, "warnings": ["과거 제시 단가이며 실제 매출·수주·시장가격을 의미하지 않습니다. 적용 단가는 담당자가 확정하세요."]}


def calculate_draft(data, tax_rate=None, tax_basis=None):
    result = dict(data)
    items = []
    for original in data.get("items", []):
        item = dict(original)
        qty, price = dec(item.get("quantity")), dec(item.get("unit_price"))
        with localcontext() as ctx:
            ctx.prec = 38
            item["amount"] = str((qty*price).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)) if qty is not None and price is not None else None
        items.append(item)
    result["items"] = items
    amounts = [dec(x["amount"]) for x in items]
    currencies = {x.get("currency") or data.get("currency") for x in items}
    subtotal = sum(amounts, Decimal(0)) if items and len(currencies) <= 1 and all(x is not None for x in amounts) else None
    rate = dec(tax_rate) if tax_rate is not None else dec(data.get("tax_rate"))
    result["tax_rate"] = str(rate) if rate is not None else None
    basis = tax_basis or data.get("tax_basis")
    result["tax_basis"] = basis
    if basis:
        result["tax_terms"] = "부가세 포함" if basis == "inclusive" else "부가세 별도"
    tax, total = None, None
    discount = data.get("discount_terms")
    supported = not discount or normalized(discount) in {"없음", "무할인", "할인없음", "none"}
    if subtotal is not None and rate is not None and supported:
        with localcontext() as ctx:
            ctx.prec = 38
            if basis == "exclusive" or rate == 0:
                tax = (subtotal*rate/100).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                total = subtotal+tax
            elif basis == "inclusive":
                total = subtotal
                subtotal = (total/(1+rate/100)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                tax = total-subtotal
    result["subtotal"] = str(subtotal) if subtotal is not None else None
    result["tax_amount"] = str(tax) if tax is not None else None
    result["total_amount"] = str(total) if total is not None else None
    return QuoteFields.model_validate(result).model_dump(mode="json")


def parse_json_field(value, default):
    if value is None or value == "":
        return default
    return json.loads(value) if isinstance(value, str) else value
