"""Runtime values for the Aether interpreter."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


class _Empty:
    """The value of a blank sheet cell."""

    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __repr__(self) -> str:
        return "empty"

    def __bool__(self) -> bool:
        return False


EMPTY = _Empty()


@dataclass(frozen=True, order=True)
class Money:
    amount: Decimal

    def __post_init__(self):
        object.__setattr__(self, "amount", Decimal(self.amount).quantize(Decimal("0.01"), ROUND_HALF_UP))

    def __str__(self) -> str:
        return f"${self.amount:,.2f}"


@dataclass(frozen=True)
class RowRef:
    sheet: str  # alias
    row_id: str


@dataclass
class DraftValue:
    channel: str
    to: Any
    subject: str | None
    body: str
    incomplete: list[str] = field(default_factory=list)  # names of empty slots without default

    def text(self) -> str:
        return self.body if self.subject is None else f"{self.subject}\n{self.body}"


@dataclass
class ApprovedValue:
    draft: DraftValue
    approval_id: str
    used: bool = False


@dataclass
class DraftBatchValue:
    var: str
    rows: list[RowRef]
    bound: int
    msg: Any  # nodes.Message (template)
    scope: dict  # variables visible when drafted


@dataclass
class ApprovedBatchValue:
    batch: DraftBatchValue
    approval_id: str
    template_hash: str
    recipients_hash: str
    messages_hash: str
    count: int
    expires_at: datetime
    used: bool = False


def fmt(v: Any) -> str:
    """How a value appears inside a message."""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, Decimal):
        q = v.normalize()
        return f"{q:f}" if q == q.to_integral() else f"{v:f}"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, timedelta):
        return f"{v}"
    return str(v)


def type_name(v: Any) -> str:
    return type(v).__name__
