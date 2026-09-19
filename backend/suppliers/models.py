from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.identifiers import compact_identifier


class SupplierInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    legal_name: str = Field(min_length=1)
    tax_id: str = Field(min_length=1)
    iban: str = Field(min_length=1)
    city: str = Field(min_length=1)
    payment_terms_days: int = Field(ge=0)

    @field_validator('tax_id', 'iban')
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return compact_identifier(value)


class Supplier(SupplierInput):
    supplier_id: str = Field(min_length=1)
