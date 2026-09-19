from enum import StrEnum


class ErpWarning(StrEnum):
    MISSING_ENTRY_ID = "missing_entry_id"
    MISSING_SUPPLIER_ID = "missing_supplier_id"
    MISSING_TAX_ID = "missing_tax_id"
    MISSING_ORDER_ID = "missing_order_id"
    MISSING_STATUS = "missing_status"
    MISSING_DATE = "missing_date"
    MISSING_AMOUNT = "missing_amount"
    INVALID_DATE = "invalid_date"
    DATE_OUT_OF_RANGE = "date_out_of_range"
    INVALID_AMOUNT = "invalid_amount"
    ISO_DATE_FORMAT = "iso_date_format"
    ENGLISH_AMOUNT_FORMAT = "english_amount_format"
    UNKNOWN_STATUS = "unknown_status"
    POSSIBLE_CHARACTER_LOSS = "possible_character_loss"
