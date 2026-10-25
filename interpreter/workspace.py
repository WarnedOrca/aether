"""Mock connectors: sheets, calendars, outbox, money ledger, and the connector log.

The connector log is written here, not by the interpreter, so a separate monitor
can check what actually happened (SPEC.md section 12, "two independent witnesses").
The owner's workspace also decides which real sheet each alias means.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from .values import EMPTY, Money


@dataclass
class MockSheet:
    title: str
    columns: dict[str, str]  # name -> type
    rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    _ids: Any = field(default_factory=lambda: itertools.count(1), repr=False)

    def add(self, values: dict[str, Any]) -> str:
        rid = f"r{next(self._ids)}"
        self.rows[rid] = {c: values.get(c, EMPTY) for c in self.columns}
        return rid


@dataclass
class MockCalendar:
    title: str
    events: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class Workspace:
    now: datetime
    sheets: dict[str, MockSheet] = field(default_factory=dict)
    calendars: dict[str, MockCalendar] = field(default_factory=dict)
    connector_log: list[dict] = field(default_factory=list)
    _event_ids: Any = field(default_factory=lambda: itertools.count(1), repr=False)

    # ----- setup helpers
    def add_sheet(self, alias: str, title: str, columns: dict[str, str], rows: list[dict] | None = None) -> MockSheet:
        sheet = MockSheet(title, columns)
        for r in rows or []:
            sheet.add(r)
        self.sheets[alias] = sheet
        return sheet

    def add_calendar(self, alias: str, title: str) -> MockCalendar:
        self.calendars[alias] = MockCalendar(title)
        return self.calendars[alias]

    def _log(self, kind: str, **detail) -> None:
        self.connector_log.append({"kind": kind, "at": self.now.isoformat(), **detail})

    # ----- sheet access (every cell read is logged)
    def row_ids(self, alias: str) -> list[str]:
        return list(self.sheets[alias].rows)

    def has_row(self, alias: str, rid: str) -> bool:
        return rid in self.sheets[alias].rows

    def read(self, alias: str, rid: str, col: str) -> Any:
        self._log("read", sheet=alias, col=col, row=rid)
        return self.sheets[alias].rows[rid].get(col, EMPTY)

    def write(self, alias: str, rid: str, col: str, value: Any) -> None:
        self._log("write", sheet=alias, col=col, row=rid)
        self.sheets[alias].rows[rid][col] = value

    def append(self, alias: str, values: dict[str, Any]) -> str:
        rid = self.sheets[alias].add(values)
        self._log("append", sheet=alias, row=rid, cols=sorted(values))
        return rid

    # ----- effects
    def deliver(self, channel: str, to: str, subject: str | None, body: str) -> None:
        self._log("deliver", channel=channel, to=str(to), subject=subject, body=body)

    def move_money(self, op: str, amount: Money, ident: str, detail: str) -> None:
        self._log("money", op=op, amount=str(amount.amount), ident=ident, detail=detail)

    def book(self, alias: str, title: str, at: Any, length: timedelta | None) -> str:
        eid = f"ev{next(self._event_ids)}"
        self.calendars[alias].events[eid] = {"title": title, "at": at, "length": length}
        self._log("book", calendar=alias, event=eid)
        return eid

    def cancel(self, alias: str, eid: str) -> bool:
        found = self.calendars[alias].events.pop(eid, None) is not None
        self._log("cancel", calendar=alias, event=eid, found=found)
        return found

    def notify_owner(self, text: str) -> None:
        self._log("notify", text=text)

    # ----- ledgers derived from the connector log
    def sends_in(self, start: datetime, end: datetime) -> int:
        return sum(1 for e in self.connector_log
                   if e["kind"] == "deliver" and start <= datetime.fromisoformat(e["at"]) < end)

    def money_in(self, op: str, start: datetime, end: datetime) -> Decimal:
        return sum((Decimal(e["amount"]) for e in self.connector_log
                    if e["kind"] == "money" and e["op"] == op
                    and start <= datetime.fromisoformat(e["at"]) < end), Decimal(0))
