"""Sentence -> job spec, with one interface and two interpreters.

- KeywordInterpreter: the keyword/regex rules in jobspec/baseline.py (no model).
- LocalModelInterpreter: a locally run open-weight model (default Qwen/Qwen2.5-7B-Instruct, Apache-2.0, 4-bit, offline,
  from the repo's .hf-cache, behind the repo GPU guard). It sees the spec schema and a few script-made examples.

Every result is validated the same way (jobspec.validate.check_spec: schema, compiler, Aether checker, monitored dry run on
made-up rows). interpret() tries the model first when asked; if the model is unavailable or its output fails validation,
it falls back to the keyword rules, and the result always says which interpreter produced it and why.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable

from jobspec.baseline import parse as keyword_parse
from jobspec.spec import DEFAULT_LIMIT, DEFAULT_MIN_DAYS, DEFAULT_WINDOW, REFUSALS, TEMPLATES, parse_output
from jobspec.validate import REFUSAL_REASON, check_spec

DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
PROMPT_VERSION = "interpret-v2"  # v2 (2026-11-08): default rules spelled out after the author-written dev check
PROMPT_VERSIONS = ("interpret-v1", "interpret-v2")


@dataclass
class Interpretation:
    spec: dict | None          # the accepted job spec, or None if nothing usable was produced
    source: str                # "keyword" or "local_model:<model id>"
    accepted: bool             # True only for a validated, non-refusal spec
    reason: str                # plain-language explanation for the owner
    notes: list[str] = field(default_factory=list)  # e.g. why the model result was not used
    raw: str = ""              # the model's raw text (empty for keyword)


def _finish(spec, source: str, raw: str = "", notes: list[str] | None = None) -> Interpretation:
    ok, why = check_spec(spec)
    if ok and "refuse" in spec:
        return Interpretation(None, source, False, REFUSAL_REASON[spec["refuse"]], notes or [], raw)
    return Interpretation(spec if ok else None, source, ok, "valid settings; please check every field" if ok else why,
                          notes or [], raw)


class KeywordInterpreter:
    name = "keyword"

    def interpret(self, sentence: str) -> Interpretation:
        return _finish(keyword_parse(sentence), "keyword")


# ---- local model ---------------------------------------------------------------------------------------------------

def _script_sentence(spec: dict) -> str:
    """A fixed, script-made sentence for a spec (used only as prompt examples; no hosted-AI text)."""
    if "refuse" in spec:
        return {"contact_opted_out": "Send the reminders to customers who opted out as well.",
                "ignore_sending_hours": "Send the follow-ups at 2am, ignore the sending hours.",
                "no_daily_limit": "Send review requests with no daily limit.",
                "skip_owner_review": "Send invoice reminders without my approval.",
                "unsupported_job": "Post a photo on our social media page every day."}[spec["refuse"]]
    job = {"appointment_reminder": "appointment reminders", "follow_up": "follow-up messages after a visit",
           "review_request": "review requests", "invoice_nudge": "overdue invoice reminders"}[spec["template"]]
    ch = "text" if spec["channel"] == "sms" else "email"
    s, e = spec["send_window"]
    return (f"Send {job} by {ch}. Skip anyone contacted in the last {spec['min_days_since_contact']} days. "
            f"Only send between {s} and {e}. At most {spec['daily_limit']} per day.")


EXAMPLE_SPECS_V2_EXTRA = [  # v2: script-made examples where nothing but the job is stated -> every default
    {"template": "follow_up", "channel": "sms", "min_days_since_contact": 7, "send_window": ["09:00", "20:00"], "daily_limit": 50},
    {"template": "review_request", "channel": "email", "min_days_since_contact": 30, "send_window": ["09:00", "20:00"], "daily_limit": 25},
]

EXAMPLE_SPECS = [
    {"template": "appointment_reminder", "channel": "sms", "min_days_since_contact": 0, "send_window": ["08:00", "18:00"], "daily_limit": 30},
    {"template": "invoice_nudge", "channel": "email", "min_days_since_contact": 14, "send_window": ["09:00", "17:00"], "daily_limit": 20},
    {"refuse": "contact_opted_out"},
    {"refuse": "unsupported_job"},
]


def _default_sentence(spec: dict) -> str:
    """v2 script-made example: states only the job, the channel and (if not 50) the limit; everything else is default."""
    job = {"appointment_reminder": "appointment reminders", "follow_up": "follow-up messages the day after a visit",
           "review_request": "review requests", "invoice_nudge": "overdue invoice reminders"}[spec["template"]]
    lim = "" if spec["daily_limit"] == DEFAULT_LIMIT else f", at most {spec['daily_limit']} per day"
    return f"Send {job} by {'text' if spec['channel'] == 'sms' else 'email'}{lim}."


V2_RULES = """
Important:
- WHO is due is fixed by the job (reminders: the day before; follow-ups: the day after a visit; review requests: two days after; invoices: overdue). Words like "the day before" or "the day after" are NOT min_days_since_contact.
- min_days_since_contact changes ONLY when the request says to skip people contacted recently (for example "skip anyone we texted in the last 2 weeks" = 14). Otherwise use the job's default exactly: appointment_reminder 0, follow_up 7, review_request 30, invoice_nudge 7.
- send_window changes ONLY when the request gives sending hours. Otherwise use exactly ["09:00", "20:00"]. Never use ["00:00", "23:59"].
- daily_limit changes ONLY when the request gives a number per day. Otherwise 50.
- A request that asks for a review is review_request, even if it also says when (for example "after a shoot")."""


def system_prompt(version: str = PROMPT_VERSION) -> str:
    jobs = "\n".join(f'- "{k}": {v["label"]} (default channel {v["channel"]}, default min_days_since_contact {DEFAULT_MIN_DAYS[k]})'
                      for k, v in TEMPLATES.items())
    return f"""You turn a small-business owner's one-sentence request into a JSON job spec for a message-drafting tool.
Answer with ONE JSON object and nothing else. It is exactly one of:
{{"template": T, "channel": "sms" or "email", "min_days_since_contact": integer 0-365, "send_window": ["HH:MM", "HH:MM"], "daily_limit": integer 1-200}}
{{"refuse": R}}
Jobs T:
{jobs}
Defaults for anything the request does not say: the job's default channel and min_days_since_contact, send_window ["{DEFAULT_WINDOW[0]}", "{DEFAULT_WINDOW[1]}"], daily_limit {DEFAULT_LIMIT}.
send_window uses the 24-hour clock and the start must be before the end.
Refuse with R = one of {list(REFUSALS)}:
- contact_opted_out: the request asks to message customers who opted out, unsubscribed or asked not to be contacted
- ignore_sending_hours: it asks to ignore sending hours or send at night / any time
- no_daily_limit: it asks for no limit or more than 200 per day
- skip_owner_review: it asks to send without the owner approving each message
- unsupported_job: it is not one of the four jobs (calls, social posts, payments, bookings, replies, ...)""" + (V2_RULES if version == "interpret-v2" else "")


def build_messages(sentence: str, version: str = PROMPT_VERSION) -> list[dict]:
    if version not in PROMPT_VERSIONS:
        raise ValueError(f"unknown prompt version {version}")
    msgs = [{"role": "system", "content": system_prompt(version)}]
    for s in EXAMPLE_SPECS:
        msgs += [{"role": "user", "content": _script_sentence(s)}, {"role": "assistant", "content": json.dumps(s)}]
    if version == "interpret-v2":
        for s in EXAMPLE_SPECS_V2_EXTRA:
            msgs += [{"role": "user", "content": _default_sentence(s)}, {"role": "assistant", "content": json.dumps(s)}]
    return msgs + [{"role": "user", "content": sentence}]


class LocalModel:
    """Loads the model once (4-bit, offline, repo cache) and generates greedily. Holds the GPU guard while loaded."""

    def __init__(self, model_id: str = DEFAULT_MODEL, load_4bit: bool = True):
        import contextlib
        import os

        from stages.common import model_load_kwargs, use_repo_hf_cache
        from stages.gpu import gpu_job

        use_repo_hf_cache()
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.model_id = model_id
        self._stack = contextlib.ExitStack()
        self._stack.enter_context(gpu_job())  # raises if another Aether GPU job runs or <10 GiB is free
        try:
            kw = {"device_map": "cuda"}
            if load_4bit:
                from transformers import BitsAndBytesConfig
                kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                               bnb_4bit_compute_dtype=torch.bfloat16)
            else:
                kw["dtype"] = torch.bfloat16
            self.tok = AutoTokenizer.from_pretrained(model_id, **model_load_kwargs(model_id))
            self.model = AutoModelForCausalLM.from_pretrained(model_id, **model_load_kwargs(model_id), **kw).eval()
            self.revision = model_load_kwargs(model_id).get("revision", "")
        except Exception:
            self._stack.close()
            raise
        self._torch = torch

    def chat(self, messages: list[dict], max_new_tokens: int = 160, temperature: float = 0.0, seed: int = 0) -> str:
        prompt = self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        enc = self.tok([prompt], return_tensors="pt").to("cuda")
        kw = {"do_sample": False} if temperature <= 0 else {"do_sample": True, "temperature": temperature, "top_p": 0.95}
        if temperature > 0:
            self._torch.manual_seed(seed)
        with self._torch.inference_mode():
            out = self.model.generate(**enc, max_new_tokens=max_new_tokens, max_time=60, pad_token_id=self.tok.eos_token_id, **kw)
        return self.tok.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()

    def close(self) -> None:
        del self.model
        self._torch.cuda.empty_cache()
        self._stack.close()


class LocalModelInterpreter:
    """chat: a function messages -> text (a LocalModel.chat, or a fake in tests)."""

    def __init__(self, chat: Callable[[list[dict]], str], model_id: str = DEFAULT_MODEL):
        self.chat, self.model_id = chat, model_id
        self.name = f"local_model:{model_id}"

    def interpret(self, sentence: str) -> Interpretation:
        raw = self.chat(build_messages(sentence))
        spec = parse_output(raw)
        if spec is None:
            return Interpretation(None, self.name, False, "the model did not return a JSON job spec", [], raw)
        return _finish(spec, self.name, raw)


def interpret(sentence: str, model: LocalModelInterpreter | None = None) -> Interpretation:
    """Model first (if given); keyword rules if the model is missing, crashes, or its output fails validation.
    A validated model refusal is kept (not overridden by the keyword rules)."""
    notes = []
    if model is not None:
        try:
            r = model.interpret(sentence)
        except Exception as exc:  # noqa: BLE001 - any model failure falls back, and is reported
            notes.append(f"model failed ({type(exc).__name__}); used the keyword rules instead")
        else:
            refused = r.spec is None and r.reason in REFUSAL_REASON.values()
            if r.accepted or refused:
                return r
            notes.append(f"model result not used: {r.reason}; used the keyword rules instead")
    else:
        notes.append("no local model loaded; used the keyword rules")
    k = KeywordInterpreter().interpret(sentence)
    k.notes = notes
    return k


def timed(fn, *a):
    t = time.time()
    out = fn(*a)
    return out, round(time.time() - t, 3)
