"""SQLite models via SQLModel. Add as agents need them."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class ItemStatus(StrEnum):
    UNREAD = "unread"
    IN_PROGRESS = "in_progress"
    READ = "read"


class ItemKind(StrEnum):
    URL = "url"
    PAPER = "paper"
    NOTE = "note"


class ReadingListItem(SQLModel, table=True):
    __tablename__ = "reading_list_items"

    id: int | None = Field(default=None, primary_key=True)
    url: str | None = Field(default=None, index=True, unique=True)  # null for freeform notes
    title: str
    summary: str | None = None
    source: str | None = None
    kind: ItemKind = ItemKind.URL
    tags: str = ""  # comma-separated
    status: ItemStatus = ItemStatus.UNREAD
    progress: int = 0  # 0-100
    saved_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime | None = None
    mirror_path: str | None = None  # path relative to vault root


class AuditLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    agent: str = Field(index=True)
    action: str
    payload: str
    success: bool = True


class PlaidItem(SQLModel, table=True):
    """One row per linked bank Item."""
    id: int | None = Field(default=None, primary_key=True)
    item_id: str = Field(unique=True, index=True)
    institution_name: str
    access_token_encrypted: bytes  # encrypted at rest
    cursor: str | None = None
    linked_at: datetime = Field(default_factory=datetime.utcnow)


class Transaction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    plaid_transaction_id: str = Field(unique=True, index=True)
    account_id: str = Field(index=True)
    date: datetime = Field(index=True)
    amount: float
    merchant: str | None = None
    category: str | None = None
    raw_category: str | None = None
    pending: bool = False


class FoodEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    description: str
    quantity: str | None = None
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    source: str = "manual"  # manual | receipt | imported


class HealthMetricDaily(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    date: datetime = Field(index=True)
    metric: str = Field(index=True)  # steps, active_energy, weight, resting_hr, ...
    value: float
    unit: str | None = None
