import copy
import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select

from .database import Item, Quote, Revision, now
from .domain import diagnostics, normalized
from .schemas import QuoteFields, QuoteSearchRequest


def require(session, quote_id, deleted=False):
    quote = session.get(Quote, quote_id)
    if not quote or (quote.deleted_at and not deleted):
        raise HTTPException(404, "견적서를 찾을 수 없습니다.")
    return quote


def detail(quote):
    data = {**QuoteFields().model_dump(mode="json"), **copy.deepcopy(quote.payload)}
    data["items"] = [dict(x.payload, item_id=x.id, line_number=x.line_number) for x in quote.items]
    quoted_amount = data.get("total_amount") if data.get("total_amount") is not None else data.get("subtotal")
    return {**data, "quoted_amount": quoted_amount, "quote_id": quote.id, "kind": quote.kind, "source_quote_id": quote.source_quote_id,
            "source_filename": quote.source_filename, "status": quote.status,
            "version": quote.version, "created_at": quote.created_at, "updated_at": quote.updated_at,
            "deleted_at": quote.deleted_at, "extraction_status": quote.extraction_status,
            "item_count": len(quote.items), "validation": diagnostics(data)}


def clean_fields(quote):
    data = {**QuoteFields().model_dump(mode="json"), **copy.deepcopy(quote.payload)}
    data["items"] = [x.payload.copy() for x in quote.items]
    return data


def set_fields(quote, data):
    canonical = QuoteFields.model_validate(data).model_dump(mode="json")
    items = canonical.pop("items")
    quote.payload = canonical
    quote.items = [Item(line_number=i+1, item_name=x["item_name"], item_name_original=x.get("original_item_name"), payload=x) for i, x in enumerate(items)]
    quote.updated_at = now()


def record(session, quote, action):
    session.flush()
    session.add(Revision(quote_id=quote.id, version=quote.version, action=action, snapshot=detail(quote)))


def check_version(quote, expected):
    if expected is not None and expected != quote.version:
        raise HTTPException(409, "다른 작업으로 견적서가 변경되었습니다. 최신 정보를 다시 조회하세요.")


def ensure_idle(quote):
    if quote.status == "extracting":
        raise HTTPException(409, "추출 중입니다. 완료 후 수정하거나 삭제하세요.")


def search(session, query: QuoteSearchRequest, trash=False):
    stmt = select(Quote).where(Quote.deleted_at.is_not(None) if trash else Quote.deleted_at.is_(None))
    if query.status:
        stmt = stmt.where(Quote.status == query.status.value)
    if query.kind:
        stmt = stmt.where(Quote.kind == query.kind)
    quotes = session.scalars(stmt.order_by(Quote.created_at.desc(), Quote.id.desc())).all()
    # JSON decimal strings retain exact input precision in both SQLite and PostgreSQL.
    # MVP filtering deliberately uses Decimal, never a floating-point DB cast.
    matches = []
    for q in quotes:
        d = detail(q)
        if query.direction and d.get("direction") != query.direction:
            continue
        if query.keyword and normalized(query.keyword) not in normalized(json.dumps(clean_fields(q), ensure_ascii=False)):
            continue
        if any(getattr(query, k) and normalized(getattr(query, k)) not in normalized(d.get(k)) for k in ("customer_name", "contact_name")):
            continue
        if query.item_name and not any(normalized(query.item_name) in normalized(x["item_name"]) for x in d["items"]):
            continue
        day = d.get("issue_date")
        if query.date_from and (not day or day < query.date_from.isoformat()):
            continue
        if query.date_to and (not day or day > query.date_to.isoformat()):
            continue
        amount = Decimal(d["total_amount"]) if d.get("total_amount") is not None else None
        if query.amount_min is not None and (amount is None or amount < query.amount_min):
            continue
        if query.amount_max is not None and (amount is None or amount > query.amount_max):
            continue
        matches.append(d)
    return {"items": matches[query.offset:query.offset+query.limit], "total": len(matches), "limit": query.limit, "offset": query.offset}
