"""Approval requests, decisions, and scripted approval providers.

`RecordingProvider` keeps the harness-side record of what the human approved.
The monitor compares deliveries against that record, not against the
interpreter's own audit log.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable, Iterable


def h(*parts: object) -> str:
    return "sha256:" + hashlib.sha256(repr(parts).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Item:
    """One message (or money action) the owner is asked about."""

    to: str
    text: str


@dataclass
class ApprovalRequest:
    request_id: str
    kind: str  # message | batch | money
    items: list[Item]  # every message covered (a batch covers all, not only the preview)
    preview: list[Item]
    timeout: timedelta
    template: str | None = None  # batch: template body the owner may edit


@dataclass
class Decision:
    action: str  # approve | deny | edit | timeout
    delay: timedelta = timedelta(minutes=1)
    new_text: str | None = None  # for edit
    after: Callable[[], None] | None = None  # test hook: runs after the decision (e.g. data changes)


class Provider:
    def decide(self, req: ApprovalRequest) -> Decision:  # pragma: no cover - interface
        raise NotImplementedError


class Always(Provider):
    def __init__(self, action: str = "approve", delay: timedelta = timedelta(minutes=1)):
        self.action, self.delay = action, delay

    def decide(self, req: ApprovalRequest) -> Decision:
        return Decision(self.action, self.delay)


class Script(Provider):
    """Returns the given decisions in order; repeats the last one."""

    def __init__(self, decisions: Iterable[Decision]):
        self.decisions = list(decisions)
        self.i = 0

    def decide(self, req: ApprovalRequest) -> Decision:
        d = self.decisions[min(self.i, len(self.decisions) - 1)]
        self.i += 1
        return d


class FromFunction(Provider):
    def __init__(self, fn: Callable[[ApprovalRequest], Decision]):
        self.fn = fn

    def decide(self, req: ApprovalRequest) -> Decision:
        return self.fn(req)


@dataclass
class RecordingProvider(Provider):
    """Wraps a provider and records every request and every approved item."""

    inner: Provider
    requests: list[ApprovalRequest] = field(default_factory=list)
    approved: list[tuple[str, Item]] = field(default_factory=list)  # (request_id, item)

    def decide(self, req: ApprovalRequest) -> Decision:
        self.requests.append(req)
        d = self.inner.decide(req)
        if d.action == "approve" and d.delay <= req.timeout:
            self.approved.extend((req.request_id, it) for it in req.items)
        return d
