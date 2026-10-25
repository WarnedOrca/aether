"""Small helpers for varied English and for assembling program text."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

TIMES = ["08:00", "08:30", "09:00", "10:00", "11:00", "16:00", "17:30", "18:00"]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
WINDOWS = [("08:00", "20:00"), ("07:30", "19:00"), ("09:00", "21:00"), ("08:00", "18:00")]


def pick(rng: random.Random, options):
    return rng.choice(list(options))


def clock(t: str) -> str:
    """'17:30' -> '5:30pm'."""
    h, m = map(int, t.split(":"))
    suffix = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}{suffix}" if m == 0 else f"{h12}:{m:02d}{suffix}"


def schedule_phrase(rng: random.Random, kind: str, time: str, weekday: str | None = None) -> str:
    if kind == "daily":
        return pick(rng, [f"Every day at {clock(time)}", f"Each morning at {clock(time)}" if time < "12:00"
                          else f"Each day at {clock(time)}", f"Daily at {clock(time)}"])
    return pick(rng, [f"Every {weekday.capitalize()} at {clock(time)}", f"On {weekday.capitalize()}s at {clock(time)}",
                      f"Each {weekday.capitalize()} at {clock(time)}"])


def approval_phrase(rng: random.Random) -> str:
    return pick(rng, ["I want to approve each message first.", "Let me check the messages before they go out.",
                      "Nothing goes out until I've approved it.", "Show me the messages for approval first.",
                      "I need to OK every message."])


def humanize(col: str) -> str:
    return col.replace("_", " ")


@dataclass
class Prog:
    """Builds indented program text."""

    lines: list[str] = field(default_factory=list)
    depth: int = 1

    def add(self, line: str) -> None:
        self.lines.append("  " * self.depth + line)

    def open(self, line: str) -> None:
        self.add(line + " {")
        self.depth += 1

    def else_(self) -> None:
        self.depth -= 1
        self.add("} else {")
        self.depth += 1

    def close(self) -> None:
        self.depth -= 1
        self.add("}")

    def text(self) -> str:
        return "\n".join(self.lines)


def camel(*words: str) -> str:
    return "".join(w[:1].upper() + w[1:] for part in words for w in part.replace("-", "_").split("_"))
