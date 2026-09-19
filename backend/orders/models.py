from datetime import date as Date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
        return ''.join(value.split()).upper() or None


class Order(OrderInput):
    order_id: str = Field(min_length=1)
