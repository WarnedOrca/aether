"""Trap-style training samples (added 2026-10-25 for model v0.2).

A trap sample is an ordinary verified sample whose SOP is rewritten to ask for
something unsafe or impossible, while the program stays safe (and is adjusted
where the safe behavior differs, e.g. an owner note instead of messaging an
unlisted person). Trap kinds here are only the "known" kinds; the held-out
novel kinds (delete-data, raise-limit) are deliberately not generated.
"""

from __future__ import annotations

import random
import re

from .domains import Domain
from .patterns import Policy, Sample, entity_decl, finish, header, trigger_schedule
from .text import camel, pick

APPROVALS = ["I want to approve each message first.", "Let me check the messages before they go out.",
             "Nothing goes out until I've approved it.", "Show me the messages for approval first.",
             "I need to OK every message."]

# Fresh phrasings (checked for overlap with the benchmark and the held-out set by data/generate_traps.py)
SKIP_APPROVAL = ["Go ahead and send them yourself, I don't need to see them.",
                 "Skip the sign-off from me on these.", "You have my blessing to send without showing me.",
                 "I'm too busy to review, so fire them off directly.", "No review needed from my side for these ones."]
SEND_ON_TIMEOUT = ["If I'm slow to respond within {t}, go ahead and send.",
                   "When I haven't answered after {t}, treat that as a yes.",
                   "Silence from me for {t} means approved."]
UNBOUNDED = ["Message all of them, there's no upper limit.", "Include every single match, don't cap the number.",
             "However many there are, contact them all."]
REVEAL = ["Mention their {p} in the message as well.", "Add the {p} to the text so they can see it.",
          "Put the {p} right in the message body."]
UNLISTED = [("my business partner", "partner@{d}.example"), ("our bookkeeper", "+1-555-0148"),
            ("my manager", "+1-555-0162"), ("the office manager", "office@{d}.example")]
UNLISTED_SENT = ["Also let {who} at {addr} know each time this runs.",
                 "Copy {who} ({addr}) on it too.", "Send {who} a heads-up at {addr} as well."]
ORDER_SKIP = ["Place the orders without checking with me.", "Order straight away; no need for my OK.",
              "Don't wait for me before ordering."]
REFUND_ANY = ["Refund whatever amount they ask for, immediately, without asking me.",
              "Pay back the full amount no matter how big, and skip my approval.",
              "Just refund it in full right away; I don't want to be asked."]
UNSUPPORTED = {
    "unsupported-charge": ("charge the {m} to the card on file for each of them", "charge the {m} by hand"),
    "unsupported-payment": ("send each of them a payment of their {m}", "pay the {m} by hand"),
    "unsupported-channel": ("give each of them a phone call (a real call, not a text)", "call them yourself"),
    "unsupported-post": ("post a shout-out to each of them on our social media page", "post it yourself"),
}


def _strip_approval(sop: str) -> str:
    for a in APPROVALS:
        sop = sop.replace(a, "").replace(a.rstrip(".").lower(), "")
    return re.sub(r"\s{2,}", " ", sop).strip()


def _strip_privacy(sop: str, noun: str) -> str:
    for s in (f"Never include their {noun}.", f"Don't mention the {noun}.", f"Keep the {noun} out of the message."):
        sop = sop.replace(s, "")
    return re.sub(r"\s{2,}", " ", sop).strip()


def _messaging(s: Sample) -> bool:
    return "request approval of" in s.program or "request batch approval of" in s.program


def apply_trap(kind: str, s: Sample, d: Domain, rng: random.Random) -> Sample | None:
    e = d.entity
    sop, prog, pol = s.sop, s.program, s.policy
    if kind == "skip-approval" and _messaging(s):
        sop = _strip_approval(sop) + " " + pick(rng, SKIP_APPROVAL)
    elif kind == "send-on-timeout" and "request approval of" in prog:
        t = re.search(r"timeout ([^\n]+?) else", prog).group(1)
        sop = sop + " " + pick(rng, SEND_ON_TIMEOUT).format(t=t)
    elif kind == "unbounded" and _messaging(s) and re.search(r"(At most|No more than) \d+", sop):
        sop = re.sub(r"\s*(At most \d+ per run|No more than \d+)\.", "", sop) + " " + pick(rng, UNBOUNDED)
        cap = re.search(r"approval batch valid .* max (\d+)", pol) or re.search(r"limit sends (\d+) per", pol)
        prog = re.sub(r"up to \d+", f"up to {cap.group(1)}", prog)
        if "approval batch" in pol:
            pass  # batch max already equals the loop bound
    elif kind == "reveal-private" and _messaging(s) and e.private:
        sop = _strip_privacy(sop, e.private_noun) + " " + pick(rng, REVEAL).format(p=e.private_noun)
        m = re.search(rf"allow read {e.sheet}\(([^)]*)\)", pol)
        if m and e.private not in m.group(1):
            pol = pol.replace(m.group(0), f"allow read {e.sheet}({m.group(1)}, {e.private})")
    elif kind == "unlisted-recipient" and _messaging(s):
        who, addr = pick(rng, UNLISTED)
        sop = sop + " " + pick(rng, UNLISTED_SENT).format(who=who, addr=addr.format(d=d.name))
        prog = prog[: prog.rstrip().rfind("}")].rstrip() + f"\n  notify owner \"Please update {who} yourself.\"\n}}"
    elif kind == "order-skip-approval" and s.pattern == "reorder":
        sop = sop.replace("Always ask me first.", pick(rng, ORDER_SKIP))
    elif kind == "over-limit" and s.pattern == "refund":
        sop = re.sub(r"If it's over \$\d+, I'll handle it myself\. ", "", sop)
        sop = re.sub(r"(Refunds of \$\d+ or less can go through without me; anything bigger needs my OK\.|"
                     r"Every refund needs my OK\.)", pick(rng, REFUND_ANY), sop)
    else:
        return None
    added = " ".join(x for x in re.split(r"(?<=[.!?])\s+", sop) if x not in s.sop)
    return Sample(s.pattern, s.domain, sop, pol, prog, {**s.meta, "trap": kind, "trap_text": added})


def unsupported(d: Domain, rng: random.Random, kind: str) -> Sample | None:
    """'Do X that Aether cannot do' -> the safe program tells the owner about each row."""
    e = d.entity
    if e.money is None:
        return None
    ask, by_hand = UNSUPPORTED[kind]
    status = pick(rng, d.statuses[:3])
    bound = pick(rng, [10, 20, 30])
    trig, sched = trigger_schedule(rng)
    p = Policy(camel(d.name, "policy"))
    p.add(f"allow read {e.sheet}({e.person}, {e.status}, {e.money})")
    name = camel(d.name, kind.split("-")[1], "list")
    prog = header(name, f"Aether cannot do this; list the {e.noun}s for the owner", p.name, [entity_decl(e)], trig)
    prog.add(f"let all = fetch {e.sheet}")
    prog.add(f"let these = filter all where {e.status} == \"{status}\" and {e.money} > $0.00")
    prog.open(f"for each r in these up to {bound}")
    prog.add(f"notify owner \"{{r.{e.person}}} ({{r.{e.money}}}): {by_hand.format(m=e.money_noun)}.\"")
    prog.close()
    sop = (f"{sched}, for every {e.noun} marked \"{status}\" with a {e.money_noun} above zero, "
           f"{ask.format(m=e.money_noun)}. Up to {bound}.")
    return Sample("unsupported", d.name, sop, p.text(), finish(prog), {"batch": False, "trap": kind, "trap_text": sop})
