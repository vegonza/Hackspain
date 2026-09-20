from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SettingsInput(BaseModel):
    email: str = Field(max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


class Invoice(BaseModel):
    id: UUID
    name: str
    kind: Literal['received', 'issued']
    path: str = Field(exclude=True)


class StatusCount(BaseModel):
    kind: Literal['received', 'issued']
    status: Literal['PAGAR', 'paid']
    count: int


class Overview(BaseModel):
    email: str
    invoices: list[Invoice]
    statuses: list[StatusCount]


class SendInput(SettingsInput):
    period: str
    received_ids: list[UUID]
    issued_ids: list[UUID]


class SendResult(BaseModel):
    sent: int


class Attachment(BaseModel):
    filename: str
    content: str


class Email(BaseModel):
    sender: str = Field(serialization_alias='from')
    to: list[str]
    subject: str
    text: str
    attachments: list[Attachment]


class PendingSend(BaseModel):
    id: UUID
    created_at: datetime
    received_ids: list[UUID]
    issued_ids: list[UUID]
    email: Email
    accepted: bool = False
