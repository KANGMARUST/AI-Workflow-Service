from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
class QuoteStatus(str, Enum):
    review_required="review_required"; confirmed="confirmed"; rejected="rejected"; archived="archived"; extracting="extracting"
class QuoteItem(BaseModel):
    item_name: str
    original_item_name: str|None=None
    specification: str|None=None
    unit: str|None=None
    quantity: Decimal|None=None
    unit_price: Decimal|None=None
    amount: Decimal|None=None
    currency: str="KRW"
class QuoteSummary(BaseModel):
    quote_id: str
    quote_number: str|None=None
    title: str|None=None
    customer_name: str|None=None
    contact_name: str|None=None
    issue_date: date|None=None
    total_amount: Decimal|None=None
    currency: str="KRW"
    status: QuoteStatus=QuoteStatus.review_required
    item_count: int=0
    source_filename: str|None=None
class QuoteListResponse(BaseModel):
    items: list[QuoteSummary]
    total: int
    limit: int
    offset: int
class QuoteSearchRequest(BaseModel):
    keyword: str|None=None
    customer_name: str|None=None
    item_name: str|None=None
    date_from: date|None=None
    date_to: date|None=None
    amount_min: Decimal|None=None
    amount_max: Decimal|None=None
    status: QuoteStatus|None=None
    limit: int=Field(default=20,ge=1,le=100)
    offset: int=Field(default=0,ge=0)
class QuoteEditRequest(BaseModel):
    title: str|None=None
    customer_name: str|None=None
    contact_name: str|None=None
    issue_date: date|None=None
    total_amount: Decimal|None=None
    items: list[QuoteItem]|None=None
    review_note: str|None=None
class QuoteStatusRequest(BaseModel):
    status: QuoteStatus
    note: str|None=None
