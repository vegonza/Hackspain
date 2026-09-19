from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.identifiers import compact_identifier, normalize_tax_id


class SupplierInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    legal_name: str = Field(min_length=1)
    tax_id: str = Field(min_length=1)
    iban: str = Field(min_length=1)
    city: str = Field(min_length=1)
    payment_terms_days: int = Field(ge=0)

    @field_validator('iban')
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return compact_identifier(value)


    @field_validator('tax_id')
    @classmethod
    def normalize_tax_id_field(cls, value: str) -> str:
        return normalize_tax_id(value)


class Supplier(SupplierInput):
    supplier_id: str = Field(min_length=1)
