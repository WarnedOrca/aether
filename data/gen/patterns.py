"""Procedure patterns. Each builds (SOP, policy, program) from one set of random choices.

Because the English and the program are written from the same choices, they
agree by construction; the generator then keeps only samples that parse, pass
the checker, and run cleanly under the monitor.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .domains import Domain, Entity
from .text import WEEKDAYS, WINDOWS, TIMES, Prog, approval_phrase, camel, clock, humanize, pick, schedule_phrase


@dataclass
class Sample:
    pattern: str
    domain: str
    sop: str
    policy: str
    program: str
    meta: dict = field(default_factory=dict)


# ---------- shared builders

class Policy:
    def __init__(self, name: str):
        self.name, self.lines = name, []

    def add(self, line: str) -> None:
        if line not in self.lines:
            self.lines.append(line)

    def text(self) -> str:
        body = "\n".join(f"  {ln}" for ln in self.lines)
        return f"policy {self.name} {{\n{body}\n}}"


def entity_decl(e: Entity, with_money: bool = True) -> str:
    cols = [f"{e.person}: Text", f"{e.contact}: {'Phone' if e.channel == 'sms' else 'Email'}",
            f"{e.when}: {e.when_type}", f"{e.status}: Text"]
    if e.money and with_money:
        cols.append(f"{e.money}: Money")
    if e.private:
        cols.append(f"{e.private}: Text private")
    return f'sheet {e.sheet} "{e.sheet}" {{ {", ".join(cols)} }}'


def base_policy(d: Domain, rng: random.Random, reads: list[str], writes: list[str], batch: bool,
                loop_bound: int) -> Policy:
    e = d.entity
    p = Policy(camel(d.name, "policy"))
    cols = list(dict.fromkeys(reads + ([e.private] if e.private and rng.random() < 0.5 else [])))
    p.add(f"allow read {e.sheet}({', '.join(cols)})")
    if writes:
        p.add(f"allow write {e.sheet}({', '.join(writes)})")
    p.add(f"allow contact {e.sheet}.{e.contact}")
    if e.private:
        p.add(f"deny reveal {e.sheet}.{e.private}")
    cap = max(loop_bound, pick(rng, [50, 100, 150, 200]))
    p.add(f"limit sends {cap} per day")
    win = pick(rng, WINDOWS)
    p.add(f"send only between {win[0]} and {win[1]}")
    if batch:
        valid = pick(rng, ["1 hour", "2 hours", "30 minutes"])
        p.add(f"approval batch valid {valid} max {loop_bound} preview {min(5, loop_bound)}")
    return p


def draft_line(e: Entity, row: str, subject: str, body: str, each: str = "") -> str:
    to = f"{row}.{e.contact}"
    if e.channel == "sms":
        return f"draft {each}sms to {to}: \"{body}\""
    return f"draft {each}email to {to} subject \"{subject}\": \"{body}\""


def when_eq(e: Entity, days: int) -> str:
    rhs = f"today() + {days} day{'s' if days != 1 else ''}" if days else "today()"
    lhs = f"date_of({e.when})" if e.when_type == "DateTime" else e.when
    return f"{lhs} == {rhs}"


def when_text(e: Entity, row: str) -> str:
    return f"{{time_of({row}.{e.when})}}" if e.when_type == "DateTime" else f"{{{row}.{e.when}}}"


def name_slot(e: Entity, row: str, rng: random.Random) -> str:
    return f"{{{row}.{e.person} default 'there'}}" if rng.random() < 0.6 else f"{{{row}.{e.person}}}"


def timeout(rng: random.Random) -> str:
    return pick(rng, ["2 hours", "6 hours", "12 hours", "1 day"])


def send_block(prog: Prog, e: Entity, row: str, subject: str, body: str, rng: random.Random,
               batch: bool, table: str, bound: int, after: list[str]) -> None:
    """Per-message: loop with draft/approve/send. Batch: draft each + one approval + follow-up loop."""
    if batch:
        prog.add(f"let msgs = {draft_line(e, row, subject, body, each=f'each {row} in {table} up to {bound} ')}")
        prog.add(f"let ok = request batch approval of msgs from owner timeout {timeout(rng)} else stop \"batch not approved\"")
        prog.add("send ok")
        if after:
            prog.open(f"for each {row} in {table} up to {bound}")
            for a in after:
                prog.add(a)
            prog.close()
        return
    prog.open(f"for each {row} in {table} up to {bound}")
    prog.add(f"let m = {draft_line(e, row, subject, body)}")
    prog.add(f"let ok = request approval of m from owner timeout {timeout(rng)} else skip")
    prog.add("send ok")
    for a in after:
        prog.add(a)
    prog.close()


def header(name: str, about: str, policy: str, decls: list[str], trigger: str) -> Prog:
    prog = Prog(lines=[f"procedure {name} {{", f"  about \"{about}\"", f"  policy {policy}"]
                + [f"  {d}" for d in decls] + [f"  {trigger}", ""])
    return prog


def finish(prog: Prog) -> str:
    return prog.text() + "\n}"


def privacy_sentence(e: Entity, rng: random.Random) -> str:
    if not e.private:
        return ""
    return " " + pick(rng, [f"Never include their {e.private_noun}.", f"Don't mention the {e.private_noun}.",
                            f"Keep the {e.private_noun} out of the message."])


def trigger_schedule(rng: random.Random) -> tuple[str, str]:
    if rng.random() < 0.6:
        t = pick(rng, TIMES)
        return f"trigger every day at {t}", schedule_phrase(rng, "daily", t)
    t, w = pick(rng, TIMES), pick(rng, WEEKDAYS)
    return f"trigger every {w} at {t}", schedule_phrase(rng, "weekly", t, w)


# ---------- patterns

def reminder(d: Domain, rng: random.Random, batch: bool) -> Sample:
    e = d.entity
    days = pick(rng, [1, 1, 2, 3, 7])
    status = d.statuses[0]
    bound = pick(rng, [20, 30, 50, 100])
    trig, sched = trigger_schedule(rng)
    new_status = pick(rng, ["reminded", "notified"])
    update = rng.random() < 0.6
    name = camel(d.name, e.when_noun.replace(" ", "_"), "reminders")
    pol = base_policy(d, rng, [e.person, e.contact, e.when, e.status], [e.status] if update else [], batch, bound)
    prog = header(name, f"Remind each {e.noun} about their {e.when_noun}", pol.name, [entity_decl(e)], trig)
    prog.add(f"let all = fetch {e.sheet}")
    prog.add(f"let due = filter all where {when_eq(e, days)} and {e.status} == \"{status}\"")
    when_words = {1: "tomorrow", 2: "in two days", 3: "in three days", 7: "in a week"}[days]
    body = (f"Hi {name_slot(e, 'r', rng)}, a reminder from {d.owner_word}: your {e.when_noun} is {when_words}"
            + (f" at {when_text(e, 'r')}." if e.when_type == "DateTime" else "."))
    after = [f"update r set {e.status} = \"{new_status}\""] if update else []
    send_block(prog, e, "r", f"Your {e.when_noun} {when_words}", body, rng, batch, "due", bound, after)
    mark = f" Then mark them {new_status}." if update else ""
    sop = (f"{sched}, find every {e.noun} in the {e.sheet} sheet whose {e.when_noun} is {when_words} and "
           f"whose status is \"{status}\". Send each one a {('text' if e.channel == 'sms' else 'email')} reminder. "
           f"{approval_phrase(rng)}{mark}{privacy_sentence(e, rng)} At most {bound} per run.")
    return Sample("reminder", d.name, sop, pol.text(), finish(prog), {"batch": batch, "days": days})


def followup(d: Domain, rng: random.Random, batch: bool) -> Sample:
    e = d.entity
    missed = d.statuses[2]
    days = pick(rng, [1, 2, 3, 7])
    bound = pick(rng, [20, 30, 40])
    trig, sched = trigger_schedule(rng)
    new_status = pick(rng, ["followed-up", "contacted"])
    name = camel(d.name, missed.replace("-", "_"), "follow_up")
    pol = base_policy(d, rng, [e.person, e.contact, e.when, e.status], [e.status], batch, bound)
    prog = header(name, f"Follow up with {e.noun}s marked {missed}", pol.name, [entity_decl(e)], trig)
    prog.add(f"let all = fetch {e.sheet}")
    lhs = f"days_between({e.when}, today())"
    prog.add(f"let recent = filter all where {e.status} == \"{missed}\" and {lhs} <= {days} and {lhs} >= 0")
    prog.add("let n = summarize count of recent")
    prog.open("if n == 0")
    prog.add(f"stop \"no {missed} {e.noun}s\"")
    prog.close()
    prog.add(f"notify owner \"{missed.capitalize()} {e.noun}s to follow up: {{n}}\"")
    body = f"Hi {name_slot(e, 'r', rng)}, we're sorry we missed you. Reply to set up a new time."
    send_block(prog, e, "r", "Let's find a new time", body, rng, batch, "recent", bound,
               [f"update r set {e.status} = \"{new_status}\""])
    sop = (f"{sched}, look for {e.noun}s marked \"{missed}\" in the last {days} day{'s' if days > 1 else ''}. "
           f"If there are none, stop. Otherwise tell me how many, then send each one a note offering a new time. "
           f"{approval_phrase(rng)} Mark each one \"{new_status}\".{privacy_sentence(e, rng)}")
    return Sample("followup", d.name, sop, pol.text(), finish(prog), {"batch": batch})


def lapsed(d: Domain, rng: random.Random, batch: bool) -> Sample:
    e = d.entity
    days = pick(rng, [30, 42, 60, 90])
    top = pick(rng, [10, 15, 20])
    trig, sched = trigger_schedule(rng)
    skip_status = d.statuses[3]
    name = camel(d.name, "win_back")
    pol = base_policy(d, rng, [e.person, e.contact, e.when, e.status], [], batch, top)
    prog = header(name, f"Nudge {e.noun}s whose {e.when_noun} was long ago", pol.name, [entity_decl(e)], trig)
    prog.add(f"let all = fetch {e.sheet}")
    prog.add(f"let old = filter all where days_between({e.when}, today()) >= {days} and {e.status} != \"{skip_status}\"")
    prog.add(f"let oldest = sort old by {e.when} first {top}")
    body = f"Hi {name_slot(e, 'r', rng)}, it's been a while! We'd love to see you again at {d.owner_word}."
    send_block(prog, e, "r", "We miss you", body, rng, batch, "oldest", top, [])
    sop = (f"{sched}, find {e.noun}s whose {humanize(e.when)} was at least {days} days ago, skipping anyone marked "
           f"\"{skip_status}\". Start with the oldest and contact at most {top}. Send a friendly note inviting them "
           f"back. {approval_phrase(rng)}{privacy_sentence(e, rng)}")
    return Sample("lapsed", d.name, sop, pol.text(), finish(prog), {"batch": batch})


def summary(d: Domain, rng: random.Random, batch: bool) -> Sample | None:
    e = d.entity
    trig, sched = trigger_schedule(rng)
    status = pick(rng, d.statuses[:3])
    name = camel(d.name, "daily_summary")
    reads = [e.status] + ([e.money] if e.money else [])
    pol = base_policy(d, rng, reads + [e.person, e.contact], [], False, 1)
    prog = header(name, f"Tell the owner how many {e.noun}s are {status}", pol.name, [entity_decl(e)], trig)
    prog.add(f"let all = fetch {e.sheet}")
    prog.add(f"let these = filter all where {e.status} == \"{status}\"")
    prog.add("let n = summarize count of these")
    with_total = e.money is not None and rng.random() < 0.6
    if with_total:
        prog.add(f"let total = summarize sum {e.money} of these")
        prog.open("if n == 0")
        prog.add(f"stop \"no {status} {e.noun}s\"")
        prog.close()
        prog.add(f"notify owner \"{status.capitalize()} {e.noun}s: {{n}}, total {humanize(e.money)}: {{total}}\"")
        extra = f" and the total {e.money_noun}"
    else:
        prog.add(f"notify owner \"{status.capitalize()} {e.noun}s today: {{n}}\"")
        extra = ""
    sop = (f"{sched}, count the {e.noun}s in {e.sheet} whose status is \"{status}\"{extra}, and send the numbers "
           f"to me only. Don't message any {e.noun}s." + (" If there are none, don't bother me." if with_total else ""))
    return Sample("summary", d.name, sop, pol.text(), finish(prog), {"batch": False})


def reorder(d: Domain, rng: random.Random, batch: bool) -> Sample | None:
    s = d.stock
    if s is None:
        return None
    cap = pick(rng, [100, 150, 200, 250])
    bound = pick(rng, [2, 3, 4, 5])
    trig, sched = trigger_schedule(rng)
    p = Policy(camel(d.name, "stock_policy"))
    p.add(f"allow read {s.sheet}({s.item}, {s.qty}, {s.minimum}, {s.reorder}, {s.supplier}, {s.unit_cost})")
    p.add(f"allow supplier {s.sheet}.{s.supplier}")
    p.add(f"limit order ${cap} per action")
    p.add(f"limit order ${cap * bound} per day")
    name = camel(d.name, "reorder")
    decl = (f'sheet {s.sheet} "{s.sheet}" {{ {s.item}: Text, {s.qty}: Number, {s.minimum}: Number, '
            f'{s.reorder}: Number, {s.supplier}: Text, {s.unit_cost}: Money }}')
    prog = header(name, f"Reorder {s.noun} below their minimum", p.name, [decl], trig)
    prog.add(f"let all = fetch {s.sheet}")
    prog.add(f"let low = filter all where {s.qty} < {s.minimum}")
    prog.open(f"for each i in low up to {bound}")
    prog.add(f"let cost = i.{s.reorder} * i.{s.unit_cost}")
    prog.open(f"if cost > ${cap}.00")
    prog.add(f"notify owner \"Reorder of {{i.{s.item}}} would cost {{cost}}, over the ${cap} limit.\"")
    prog.add("skip")
    prog.close()
    prog.add(f"order \"{{i.{s.reorder}}} x {{i.{s.item}}}\" from i.{s.supplier} cost cost, ask owner first timeout "
             f"{timeout(rng)} else skip")
    prog.add(f"log \"ordered {{i.{s.item}}}\"")
    prog.close()
    sop = (f"{sched}, check {s.sheet}. For anything below its minimum, order the usual reorder amount from its "
           f"{humanize(s.supplier)}. Always ask me first. Never spend more than ${cap} on one order; if it would cost "
           f"more, just tell me. Handle at most {bound} items per run.")
    return Sample("reorder", d.name, sop, p.text(), finish(prog), {"batch": False})


def refund(d: Domain, rng: random.Random, batch: bool) -> Sample | None:
    e = d.entity
    if e.money is None:
        return None
    cap = pick(rng, [40, 50, 75, 100])
    auto = pick(rng, [0, 10, 15, 20])
    window = pick(rng, [14, 30, 60])
    p = Policy(camel(d.name, "refund_policy"))
    sheet = "RefundRequests"
    contact_t = "Phone" if e.channel == "sms" else "Email"
    p.add(f"allow read {sheet}(request_id, {e.person}, {e.contact}, amount, purchased)")
    p.add(f"allow write {sheet}(status)")
    p.add(f"allow contact {sheet}.{e.contact}")
    p.add(f"limit refund ${cap} per action")
    p.add(f"limit refund ${cap * pick(rng, [3, 5, 6])} per day")
    if auto:
        p.add(f"refund without approval up to ${auto}")
    p.add(f"limit sends {pick(rng, [30, 50, 80])} per day")
    win = pick(rng, WINDOWS)
    p.add(f"send only between {win[0]} and {win[1]}")
    decl = (f'sheet {sheet} "{sheet}" {{ request_id: Text, {e.person}: Text, {e.contact}: {contact_t}, '
            f'amount: Money, purchased: Date, status: Text }}')
    name = camel(d.name, "refunds")
    prog = header(name, "Handle refund requests within limits", p.name, [decl], f"trigger when new row r in {sheet}")
    prog.open(f"if days_between(r.purchased, today()) > {window}")
    prog.add(f"notify owner \"Refund request {{r.request_id}} is older than {window} days.\"")
    prog.add("stop \"outside refund window\"")
    prog.close()
    prog.open(f"if r.amount > ${cap}.00")
    prog.add(f"notify owner \"Refund request {{r.request_id}} is {{r.amount}}, over ${cap}. Please review.\"")
    prog.add("stop \"over refund limit\"")
    prog.close()
    t = timeout(rng)
    if auto:
        prog.open(f"if r.amount <= ${auto}.00")
        prog.add("refund r.amount for r.request_id reason \"refund request\"")
        prog.else_()
        prog.add(f"refund r.amount for r.request_id reason \"refund request\", ask owner first timeout {t} "
                 f"else stop \"refund not approved\"")
        prog.close()
    else:
        prog.add(f"refund r.amount for r.request_id reason \"refund request\", ask owner first timeout {t} "
                 f"else stop \"refund not approved\"")
    prog.add("update r set status = \"refunded\"")
    body = f"Hi {name_slot(e, 'r', rng)}, your refund of {{r.amount}} has been issued."
    prog.add(f"let m = {draft_line(e, 'r', 'Your refund', body)}")
    prog.add(f"let ok = request approval of m from owner timeout {t} else stop \"message not approved\"")
    prog.add("send ok")
    auto_txt = (f"Refunds of ${auto} or less can go through without me; anything bigger needs my OK." if auto
                else "Every refund needs my OK.")
    sop = (f"When a new refund request is added, check it. If the purchase was more than {window} days ago, tell "
           f"me and stop. If it's over ${cap}, I'll handle it myself. {auto_txt} After refunding, mark it refunded "
           f"and let the {e.noun} know (I approve that message too).")
    return Sample("refund", d.name, sop, p.text(), finish(prog), {"batch": False})
