"""More procedure patterns: new-row confirmation, wait-and-follow-up, escalation, on-request outreach."""

from __future__ import annotations

import random

from .domains import Domain
from .patterns import (Policy, Sample, base_policy, draft_line, entity_decl, finish, header, name_slot,
                       privacy_sentence, send_block, timeout, trigger_schedule)
from .text import approval_phrase, camel, humanize, pick


def confirm_new(d: Domain, rng: random.Random, batch: bool) -> Sample | None:
    e = d.entity
    if d.calendar is None or e.when_type != "DateTime":
        return None
    length = pick(rng, [30, 45, 60, 90])
    p = base_policy(d, rng, [e.person, e.contact, e.when, e.status] + ([e.money] if e.money else []),
                    [e.status], False, 1)
    p.add(f"allow calendar {d.calendar}")
    name = camel(d.name, "confirm_new", e.when_noun.replace(" ", "_"))
    prog = header(name, f"Confirm a new {e.when_noun} and add it to the calendar", p.name,
                  [entity_decl(e), f'calendar {d.calendar} "{d.calendar}"'], f"trigger when new row r in {e.sheet}")
    hours = pick(rng, [2, 12, 24])
    prog.open(f"if r.{e.when} < now() + {hours} hours")
    prog.add(f"notify owner \"Short-notice {e.when_noun} for {{r.{e.person}}} at {{r.{e.when}}}. Please handle it.\"")
    prog.add("stop \"short notice goes to owner\"")
    prog.close()
    body = f"Hi {name_slot(e, 'r', rng)}, your {e.when_noun} with {d.owner_word} is confirmed for {{r.{e.when}}}."
    t = timeout(rng)
    prog.add(f"let m = {draft_line(e, 'r', 'Confirmed', body)}")
    prog.add(f"let ok = request approval of m from owner timeout {t} else stop \"confirmation not approved\"")
    prog.add("send ok")
    prog.add(f"let ev = book {d.calendar} {{ title: \"{{r.{e.person}}}\", at: r.{e.when}, length: {length} minutes }}")
    prog.add(f"update r set {e.status} = \"confirmed\"")
    sop = (f"When a new {e.when_noun} is added to {e.sheet}: if it's less than {hours} hours away, tell me and stop. "
           f"Otherwise send a confirmation ({approval_phrase(rng).rstrip('.').lower()}), put it on the "
           f"{d.calendar} calendar for {length} minutes, and mark it confirmed.{privacy_sentence(e, rng)}")
    return Sample("confirm_new", d.name, sop, p.text(), finish(prog), {"batch": False})


def wait_followup(d: Domain, rng: random.Random, batch: bool) -> Sample:
    e = d.entity
    days = pick(rng, [2, 3, 5, 7])
    done = d.statuses[1]
    gone = d.statuses[3]
    p = base_policy(d, rng, [e.person, e.contact, e.status], [e.status], False, 1)
    name = camel(d.name, "follow_up_after_wait")
    prog = header(name, f"Contact a new {e.noun}, then follow up once", p.name, [entity_decl(e)],
                  f"trigger when new row r in {e.sheet}")
    t = timeout(rng)
    body1 = f"Hi {name_slot(e, 'r', rng)}, thanks for choosing {d.owner_word}! Reply with any questions."
    prog.add(f"let first = {draft_line(e, 'r', 'Welcome', body1)}")
    prog.add(f"let ok1 = request approval of first from owner timeout {t} else stop \"first message not approved\"")
    prog.add("send ok1")
    prog.add(f"update r set {e.status} = \"contacted\"")
    prog.add(f"wait {days} days")
    prog.add(f"let all = fetch {e.sheet}")
    prog.add(f"let now_r = find all where {e.contact} == r.{e.contact} else stop \"row was removed\"")
    prog.open(f"if now_r.{e.status} == \"{done}\" or now_r.{e.status} == \"{gone}\"")
    prog.add("stop \"already handled\"")
    prog.close()
    body2 = f"Hi {name_slot(e, 'now_r', rng)}, just checking in. Is there anything we can help with?"
    prog.add(f"let second = {draft_line(e, 'now_r', 'Checking in', body2)}")
    prog.add(f"let ok2 = request approval of second from owner timeout {t} else stop \"follow-up not approved\"")
    prog.add("send ok2")
    sop = (f"When a new {e.noun} is added to {e.sheet}, send a welcome note and mark them \"contacted\". Wait "
           f"{days} days. If by then they're marked \"{done}\" or \"{gone}\", stop. Otherwise send one check-in "
           f"message. {approval_phrase(rng)}{privacy_sentence(e, rng)}")
    return Sample("wait_followup", d.name, sop, p.text(), finish(prog), {"batch": False})


def escalation(d: Domain, rng: random.Random, batch: bool) -> Sample | None:
    e = d.entity
    if e.money is None or e.when_type != "Date":
        return None
    k1, k2 = pick(rng, [(3, 14), (5, 14), (7, 21), (5, 30)])
    bound = pick(rng, [20, 30, 40])
    trig, sched = trigger_schedule(rng)
    p = base_policy(d, rng, [e.person, e.contact, e.when, e.money], [], False, bound)
    name = camel(d.name, "late_balance")
    prog = header(name, f"Remind late {e.noun}s; escalate very late ones", p.name, [entity_decl(e)], trig)
    prog.add(f"let all = fetch {e.sheet}")
    prog.add(f"let late = filter all where {e.money} > $0.00 and days_between({e.when}, today()) > {k1}")
    prog.open(f"for each r in late up to {bound}")
    prog.open(f"if days_between(r.{e.when}, today()) > {k2}")
    prog.add(f"notify owner \"{{r.{e.person}}} is very late ({{r.{e.money}}}). Please call.\"")
    prog.else_()
    body = f"Hello {name_slot(e, 'r', rng)}, our records show a {humanize(e.money)} of {{r.{e.money}}}. Questions? Just reply."
    prog.add(f"let m = {draft_line(e, 'r', 'A friendly reminder', body)}")
    prog.add(f"let ok = request approval of m from owner timeout {timeout(rng)} else skip")
    prog.add("send ok")
    prog.close()
    prog.close()
    sop = (f"{sched}: for {e.noun}s with a {e.money_noun} above zero whose {e.when_noun} passed more than {k1} days "
           f"ago, send a polite reminder with the amount. {approval_phrase(rng)} If it's more than {k2} days late, "
           f"don't message them; tell me so I can call.{privacy_sentence(e, rng)} At most {bound} per run.")
    return Sample("escalation", d.name, sop, p.text(), finish(prog), {"batch": False})


def outreach(d: Domain, rng: random.Random, batch: bool) -> Sample:
    e = d.entity
    bound = pick(rng, [50, 100])
    expired = d.statuses[1] if d.name in ("gym", "yoga") else d.statuses[3]
    p = base_policy(d, rng, [e.person, e.contact, e.when, e.status], [], batch, bound)
    p.add("allow append Outreach")
    name = camel(d.name, "outreach_campaign")
    decls = [entity_decl(e), 'sheet Outreach "Outreach" { day: Date, campaign: Text, targeted: Number }']
    prog = header(name, f"On request, contact recent {expired} {e.noun}s", p.name, decls,
                  "trigger when requested(days: Number)")
    prog.add(f"let all = fetch {e.sheet}")
    prog.add(f"let targets = filter all where {e.status} == \"{expired}\" and days_between({e.when}, today()) <= days")
    prog.add("let n = summarize count of targets")
    prog.add("append Outreach { day: today(), campaign: \"comeback\", targeted: n }")
    code = pick(rng, ["WELCOME10", "COMEBACK15", "RETURN20"])
    body = f"Hi {name_slot(e, 'r', rng)}, come back to {d.owner_word}! Use code {code} on your next visit."
    send_block(prog, e, "r", "We'd love to see you", body, rng, batch, "targets", bound, [])
    sop = (f"When I ask, and give a number of days, find {e.noun}s marked \"{expired}\" whose "
           f"{humanize(e.when)} was within that many days. Write down in my Outreach sheet how many you found, "
           f"then send each one the code {code}. {approval_phrase(rng)}{privacy_sentence(e, rng)} "
           f"No more than {bound}.")
    return Sample("outreach", d.name, sop, p.text(), finish(prog), {"batch": batch})
