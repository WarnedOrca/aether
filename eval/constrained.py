"""Grammar-constrained decoding: only allow next tokens that keep the program a valid
prefix of the Aether grammar (checked with Lark's incremental LALR parser).

At each step the top-K candidate tokens are checked in score order; the best one that
keeps a valid prefix is kept and all other tokens are masked. If none of the K is valid,
the step is left unconstrained (counted as a fallback). Once the program parses as a
complete file, constraints stop so the closing fence and end-of-text can be emitted.

Usage:
  uv run --group ml python -m eval.constrained --adapter outputs/ft-coder1.5b-v0.2/epoch2 --label v0.2 \
      [--tasks-dir eval/benchmark] [--k 8]
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date
from pathlib import Path

from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedToken

from checker.parser import _lark

from .baseline import RESULTS, Generator, score_row, summarize
from .bench import load_tasks
from .prompt import ROOT, chat_messages, extract_program

FENCE = "```aether\n"
_PARTIAL = {"NAME": r"[A-Za-z_][A-Za-z0-9_]*", "INT": r"[0-9]+", "NUMBER": r"[0-9]+(\.[0-9]*)?",
            "MONEY": r"\$([0-9]+(\.[0-9]{0,2})?)?", "TIME": r"[0-9]{1,2}(:[0-9]{0,2})?",
            "TYPE": r"[A-Za-z]+", "TUNIT": r"[a-z]+"}


def _literal(term_name: str) -> str | None:
    for t in _lark().terminals:
        if t.name == term_name and t.pattern.type == "str":
            return t.pattern.value
    return None


def _alternatives(term_name: str) -> list[str]:
    """Words of a terminal defined as alternatives, e.g. WEEKDAY: "monday" | "tuesday" | ..."""
    for t in _lark().terminals:
        if t.name == term_name and t.pattern.type == "re":
            value = t.pattern.value
            if re.fullmatch(r"\(\?:[A-Za-z_|]+\)", value.replace("\\", "")):
                return re.findall(r"[A-Za-z_]+", value[3:])
    return []


def _could_continue(rest: str, allowed: set[str]) -> bool:
    """Is `rest` (the unfinished last token) the start of some allowed terminal?"""
    if not rest:
        return True
    if rest.startswith('"'):
        return "STRING" in allowed and "\n" not in rest
    for name in allowed:
        lit = _literal(name)
        if lit is not None and lit.startswith(rest):
            return True
        if any(w.startswith(rest) for w in _alternatives(name)):
            return True
        pat = _PARTIAL.get(name)
        if pat and re.fullmatch(pat, rest):
            return True
        if name in ("CMPOP", "ADDOP", "MULOP") and rest in ("=", "!", "<", ">"):
            return True
    return False


def _accepts_after(head: str) -> set[str] | None:
    """Terminals the parser accepts after `head` (None if `head` itself is invalid)."""
    ip = _lark().parse_interactive(head, start="start")
    try:
        for _ in ip.iter_parse():
            pass
    except Exception:  # noqa: BLE001
        return None
    return set(ip.accepts())


_WORD = re.compile(r"[A-Za-z0-9_$:]+$")


def valid_prefix(text: str) -> bool:
    """True if `text` can still be extended into a complete Aether file."""
    m = _WORD.search(text)
    if m and m.start() > 0:  # an unfinished word at the end: is it the start of an allowed token?
        acc = _accepts_after(text[:m.start()])
        if acc is not None and _could_continue(m.group(), acc):
            return True
    ip = _lark().parse_interactive(text, start="start")
    try:
        for _ in ip.iter_parse():
            pass
        return True
    except UnexpectedToken as e:
        tok = e.token
        if tok.type == "$END":
            return True
        end = tok.end_pos if tok.end_pos is not None else len(text)
        if text[end:].strip():
            return False  # the bad token is not the last one
        allowed = set(e.expected or ()) | set(getattr(e, "accepts", None) or ())
        return _could_continue(str(tok), allowed)
    except UnexpectedCharacters as e:
        return _could_continue(text[e.pos_in_stream:], set(e.allowed or ()))
    except UnexpectedEOF:
        return True


def complete(text: str) -> bool:
    try:
        _lark().parse(text, start="start")
        return True
    except Exception:  # noqa: BLE001
        return False


class GrammarProcessor:
    """transformers LogitsProcessor for batch size 1."""

    def __init__(self, tok, prompt_len: int, k: int):
        self.tok, self.prompt_len, self.k = tok, prompt_len, k
        self.fallbacks = 0
        self.steps = 0

    def __call__(self, input_ids, scores):
        import torch

        text = self.tok.decode(input_ids[0, self.prompt_len:], skip_special_tokens=True)
        if FENCE not in text:
            return scores  # still writing the opening fence
        program = text.split(FENCE, 1)[1]
        if "```" in program or complete(program.strip()):
            return scores  # finished: allow the closing fence / end of text
        self.steps += 1
        top = torch.topk(scores[0], self.k).indices.tolist()
        for tid in top:
            piece = self.tok.decode(input_ids[0, self.prompt_len:].tolist() + [tid], skip_special_tokens=True)
            cand = piece.split(FENCE, 1)[1]
            if valid_prefix(cand):
                masked = torch.full_like(scores, float("-inf"))
                masked[0, tid] = scores[0, tid]
                return masked
        self.fallbacks += 1
        return scores


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-1.5B-Instruct")
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--label", required=True)
    ap.add_argument("--tasks-dir", default="eval/benchmark")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--fewshot", type=int, default=0)
    args = ap.parse_args()
    from transformers import LogitsProcessorList

    gen = Generator(args.model, args.adapter)
    tasks = load_tasks(ROOT / args.tasks_dir)
    rows, started, total_fallbacks, total_steps = [], time.time(), 0, 0
    for i, t in enumerate(tasks):
        prompt = gen.prompt_text(chat_messages(t.policy, t.sheets, t.sop, fewshot=bool(args.fewshot)))
        enc = gen.tok([prompt], return_tensors="pt").to("cuda")
        proc = GrammarProcessor(gen.tok, enc["input_ids"].shape[1], args.k)
        out = gen.model.generate(**enc, max_new_tokens=700, do_sample=False, pad_token_id=gen.tok.pad_token_id,
                                 logits_processor=LogitsProcessorList([proc]))
        raw = gen.tok.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True)
        total_fallbacks += proc.fallbacks
        total_steps += proc.steps
        rows.append(score_row("benchmark", t, raw, extract_program(raw)))
        if (i + 1) % 10 == 0:
            print(f"{i + 1}/{len(tasks)} done, {time.time() - started:.0f}s", flush=True)
    base = RESULTS / f"constrained-{args.label}-{Path(args.tasks_dir).name}-{date.today().isoformat()}"
    with open(f"{base}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    summary = {"label": args.label, "adapter": args.adapter, "tasks": args.tasks_dir, "k": args.k,
               "decoding": "greedy + grammar prefix constraint", "seconds": round(time.time() - started),
               "constrained_steps": total_steps, "fallback_steps": total_fallbacks,
               "monitor_problems_total": sum(len(r["monitor_problems"]) for r in rows), **summarize(rows)}
    Path(f"{base}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("seconds", "constrained_steps", "fallback_steps", "benchmark",
                                              "benchmark_traps")}, indent=2))


if __name__ == "__main__":
    main()
