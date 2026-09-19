from datetime import date as Date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.identifiers import compact_identifier, order_key


class OrderInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    supplier_id: str = Field(min_length=1)
    tax_id: str | None = None
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    status: str = Field(min_length=1)
    date: Date

    @field_validator('tax_id')
    @classmethod
    def normalize_tax_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return compact_identifier(value) or None


class Order(OrderInput):
    order_id: str = Field(min_length=1)
    review_required: bool = False

    @field_validator('order_id')
    @classmethod
    def normalize_order_id(cls, value: str) -> str:
        return order_key(value)
