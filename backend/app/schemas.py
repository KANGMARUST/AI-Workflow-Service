from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4, allow_inf_nan=False)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, str_max_length=10000)


class QuoteStatus(str, Enum):
    review_required = "review_required"
    confirmed = "confirmed"
    rejected = "rejected"
    archived = "archived"
    extracting = "extracting"


class QuoteItem(InputModel):
    item_name: str = Field(min_length=1, max_length=500)
    original_item_name: str | None = None
    specification: str | None = None
    unit: str | None = None
    quantity: Money | None = None
    unit_price: Money | None = None
    amount: Money | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    raw_fields: dict[str, Any] = Field(default_factory=dict)


class QuoteFields(InputModel):
    quote_number: str | None = None
    title: str | None = None
    issuer_company: str | None = None
    customer_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    issue_date: date | None = None
    valid_until: date | None = None
    delivery_date: date | None = None
    subtotal: Money | None = None
    tax_amount: Money | None = None
    tax_rate: Money | None = None
    tax_terms: str | None = None
    tax_basis: Literal["exclusive", "inclusive"] | None = None
    total_amount: Money | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    discount_terms: str | None = None
    payment_terms: str | None = None
    delivery_terms: str | None = None
    notes: str | None = None
    review_note: str | None = None
    items: list[QuoteItem] = Field(default_factory=list, max_length=2000)
    raw_fields: dict[str, Any] = Field(default_factory=dict)


class QuoteEditRequest(QuoteFields):
    expected_version: int | None = Field(default=None, ge=1)
    items: list[QuoteItem] | None = Field(default=None, max_length=2000)
    raw_fields: dict[str, Any] | None = None


class QuoteSummary(BaseModel):
    quote_id: str
    quote_number: str | None = None
    title: str | None = None
    customer_name: str | None = None
    contact_name: str | None = None
    issue_date: date | None = None
    total_amount: Decimal | None = None
    currency: str | None = None
    status: QuoteStatus = QuoteStatus.review_required
    item_count: int = 0
    source_filename: str | None = None
    kind: str = "archive"
    version: int = 1
    created_at: str | None = None


class QuoteListResponse(BaseModel):
    items: list[QuoteSummary]
    total: int
    limit: int
    offset: int


class QuoteSearchRequest(InputModel):
    keyword: str | None = Field(default=None, max_length=200)
    customer_name: str | None = Field(default=None, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    item_name: str | None = Field(default=None, max_length=200)
    date_from: date | None = None
    date_to: date | None = None
    amount_min: Money | None = None
    amount_max: Money | None = None
    status: QuoteStatus | None = None
    kind: Literal["archive", "draft"] | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def ranges(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("시작일은 종료일보다 늦을 수 없습니다.")
        if self.amount_min is not None and self.amount_max is not None and self.amount_min > self.amount_max:
            raise ValueError("최소 금액은 최대 금액보다 클 수 없습니다.")
        return self


class QuoteStatusRequest(InputModel):
    status: QuoteStatus
    note: str | None = None
    expected_version: int | None = Field(default=None, ge=1)


class ExtractionRequest(InputModel):
    quote_id: str
    provider: Literal["auto", "local", "upstage"] = "auto"
    force: bool = False


class CompareRequest(InputModel):
    quote_ids: list[str] = Field(min_length=2, max_length=10)
    item_name: str | None = None

    @model_validator(mode="after")
    def unique_ids(self):
        if len(set(self.quote_ids)) != len(self.quote_ids):
            raise ValueError("견적 ID가 중복되었습니다.")
        return self


class AgentRequest(InputModel):
    kind: Literal["compare"]
    quote_ids: list[str] = Field(min_length=2, max_length=5)
