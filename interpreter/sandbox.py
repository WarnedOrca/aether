"""Build mock workspaces for a procedure and run it with the monitor attached.

Used by the tests, the property tests, and (later) data generation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from checker import nodes as N
from checker.policy import build_model

from .approvals import Always, Provider, RecordingProvider
from .monitor import audit_agrees, violations
from .runtime import Interpreter, RunResult
from .values import EMPTY, Money
from .workspace import Workspace

DEFAULT_NOW = datetime(2026, 3, 2, 9, 0)  # a Monday, 09:00 (fixed so runs repeat exactly)
_NAMES = ["Ana", "Ben", "Chen", "Dana", "Eli", "Fatima", "Gus", "Hana", "Ivan", "Jo"]


@dataclass
class Literals:
    """Constants that appear in a program. Data built near them reaches more branches."""

    texts: list[str]
    numbers: list[Decimal]
    money: list[Decimal]
    days: list[int]


def literals(proc: N.Procedure) -> Literals:
    texts, numbers, money, days = set(), set(), set(), set()

    def walk(x):
        if isinstance(x, N.BinOp):  # only strings that are compared against data matter
            for side in (x.left, x.right):
                if isinstance(side, N.Str) and not any(isinstance(p, N.Interp) for p in side.parts):
                    texts.add(side.raw)
        if isinstance(x, N.Num):
            numbers.add(x.value)
        elif isinstance(x, N.MoneyLit):
            money.add(x.value)
        elif isinstance(x, N.DurationLit) and x.unit in ("day", "week"):
            days.add(int(x.amount) * (7 if x.unit == "week" else 1))
        if isinstance(x, (tuple, list)):
            for y in x:
                walk(y)
        elif hasattr(x, "__dataclass_fields__"):
            for f in x.__dataclass_fields__:
                walk(getattr(x, f))

    walk(proc.body)
    # numbers compared with days_between(...) are day offsets too (e.g. ">= 365")
    days |= {int(n) for n in numbers if n == int(n) and 0 < n <= 1000}
    return Literals(sorted(texts), sorted(numbers), sorted(money), sorted(days))


def random_value(typ: str, rng: random.Random, now: datetime, empty_rate: float = 0.0,
                 lit: Literals | None = None) -> Any:
    if rng.random() < empty_rate:
        return EMPTY
    lit = lit or Literals([], [], [], [])
    near = rng.random() < 0.6  # most values sit on or next to a program constant
    if typ == "Text":
        pool = (lit.texts if near and lit.texts else _NAMES)
        return rng.choice(pool)
    if typ == "Number":
        if near and lit.numbers:
            return rng.choice(lit.numbers) + rng.choice([Decimal(-1), Decimal(0), Decimal(1)])
        return Decimal(rng.randint(0, 6000) if rng.random() < 0.2 else rng.randint(0, 12))
    if typ == "Money":
        if near and lit.money:
            base = rng.choice(lit.money)
            return Money(base + rng.choice([Decimal("-0.01"), Decimal(0), Decimal("0.01"), -base]))
        return Money(Decimal(rng.randint(-100, 20000)) / 100)
    if typ == "Bool":
        return rng.random() < 0.5
    if typ == "Date":
        if near and lit.days:
            return now.date() + timedelta(days=rng.choice([-1, 1]) * rng.choice(lit.days) + rng.choice([-1, 0, 1]))
        return now.date() + timedelta(days=rng.randint(-200, 30))
    if typ == "DateTime":
        if near and lit.days:
            days = rng.choice([-1, 1]) * rng.choice(lit.days) + rng.choice([-1, 0, 1])
            return now + timedelta(days=days, hours=rng.randint(-2, 8))
        return now + timedelta(days=rng.randint(-1, 2), hours=rng.randint(-2, 8))
    if typ == "Phone":
        return f"+1555{rng.randint(1000000, 9999999)}"
    if typ == "Email":
        return f"{rng.choice(_NAMES).lower()}{rng.randint(1, 99)}@example.com"
    raise ValueError(typ)


def workspace_for(proc: N.Procedure, rng: random.Random | None = None, rows: int = 5,
                  now: datetime = DEFAULT_NOW, empty_rate: float = 0.0,
                  data: dict[str, list[dict]] | None = None, extra_texts: list[str] | None = None) -> Workspace:
    """A workspace bound to the procedure's sheets and calendars.

    `data` gives exact rows per sheet alias; otherwise rows are random.
    `extra_texts` adds values (e.g. on-request inputs) to the text pool.
    """
    rng = rng or random.Random(0)
    lit = literals(proc)
    if extra_texts:
        lit = Literals(sorted(set(lit.texts) | set(extra_texts)), lit.numbers, lit.money, lit.days)
    ws = Workspace(now)
    for alias, sheet in proc.sheets.items():
        cols = {c.name: c.type for c in sheet.columns.values()}
        if data is not None and alias in data:
            ws.add_sheet(alias, sheet.title, cols, data[alias])
        else:
            gen = [{c: random_value(t, rng, now, empty_rate, lit) for c, t in cols.items()} for _ in range(rows)]
            ws.add_sheet(alias, sheet.title, cols, gen)
    for alias, title in proc.calendars.items():
        ws.add_calendar(alias, title)
    return ws


@dataclass
class Outcome:
    result: RunResult
    ws: Workspace
    approvals: RecordingProvider
    problems: list[str]  # monitor violations (should always be empty)


def run_monitored(proc: N.Procedure, policy: N.Policy, ws: Workspace, provider: Provider | None = None,
                  row_id: str | None = None, params: dict | None = None) -> Outcome:
    rec = RecordingProvider(provider or Always("approve"))
    if row_id is None and isinstance(proc.trigger, N.NewRow):
        ids = ws.row_ids(proc.trigger.sheet)
        row_id = ids[-1] if ids else None
    result = Interpreter(proc, policy, ws, rec).run(row_id=row_id, params=params)
    problems = violations(ws.connector_log, rec, build_model(policy)) + audit_agrees(result.audit, ws.connector_log)
    return Outcome(result, ws, rec, problems)
