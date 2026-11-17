"""Need-to-Know core: labels, requests, policy, consent, ledger and check_reply."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Callable, Iterable, Optional, Sequence

CANT_SHARE = "I can't share that."


# ---------------------------------------------------------------- labels

@dataclass(frozen=True)
class Label:
    """`public`, `role:<name>` or `private`."""

    kind: str  # "public" | "role" | "private"
    role: Optional[str] = None

    @classmethod
    def parse(cls, text: "str | Label") -> "Label":
        if isinstance(text, Label):
            return text
        text = text.strip()
        if text == "public":
            return cls("public")
        if text == "private":
            return cls("private")
        if text.startswith("role:") and len(text) > 5:
            return cls("role", text[5:])
        raise ValueError(f"unknown label: {text!r}")

    @property
    def is_private(self) -> bool:
        return self.kind == "private"

    def visible_to(self, role: str) -> bool:
        if self.kind == "public":
            return True
        if self.kind == "role":
            return self.role == role
        return False

    def __str__(self) -> str:
        return f"role:{self.role}" if self.kind == "role" else self.kind


# ---------------------------------------------------------------- facts

_NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?!\d)")


def _numbers(text: str) -> set[str]:
    return {n for n in _NUM.findall(text) if "." in n or len(n) >= 2}


def _phrase_in(phrase: str, text: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)", text.lower()) is not None


@dataclass
class Fact:
    """One item the agent knows, with exactly one label.

    aliases:  paraphrases that count as *saying* the fact (check 2).
    hints:    cues that let a reader *infer* the fact (check 3), flagged alone.
    weak_hints: cues that are harmless alone but leak when two of them meet
              across the draft and the thread so far (check 3).
    safe_say: what to say instead when a sentence leaks this fact.
    topics:   what the fact is about, matched against a purpose's needs.
    """

    id: str
    text: str
    label: Label
    aliases: Sequence[str] = ()
    hints: Sequence[str] = ()
    weak_hints: Sequence[str] = ()
    safe_say: Optional[str] = None
    topics: Sequence[str] = ()
    owner: str = "owner"

    def __post_init__(self) -> None:
        self.label = Label.parse(self.label)

    def numbers(self) -> set[str]:
        out = _numbers(self.text)
        for a in self.aliases:
            out |= _numbers(a)
        return out

    def said_in(self, text: str) -> Optional[str]:
        """Return why `text` says this fact outright, or None."""
        if _phrase_in(self.text, text):
            return "verbatim"
        nums = self.numbers() & _numbers(text)
        if nums:
            return "number " + ",".join(sorted(nums))
        for a in self.aliases:
            if _phrase_in(a, text):
                return f"paraphrase '{a}'"
        return None

    def hinted_in(self, text: str) -> Optional[str]:
        for h in self.hints:
            if _phrase_in(h, text):
                return f"hint '{h}'"
        return None

    def weak_hits(self, text: str) -> list[str]:
        return [h for h in self.weak_hints if _phrase_in(h, text)]


# ---------------------------------------------------------------- requests, consent, policy

@dataclass(frozen=True)
class Request:
    requester: str
    role: str
    purpose: str


@dataclass
class ConsentRequest:
    """A one-tap ask to the owner: may `requester` hear `fact_id` for `purpose`?"""

    fact_id: str
    owner: str
    requester: str
    role: str
    purpose: str
    reason: str

    def __str__(self) -> str:
        return (f"ask {self.owner}: share '{self.fact_id}' with {self.requester} "
                f"({self.role}) for '{self.purpose}'? [{self.reason}]")


@dataclass
class Grant:
    fact_id: str
    requester: str
    purpose: str
    expires_at: float
    revoked: bool = False

    def active(self, now: float) -> bool:
        return not self.revoked and now < self.expires_at


@dataclass
class Policy:
    """Check 1: which labels a role may hear, and which topics a purpose needs.

    purpose_needs maps a purpose to the topics it needs. A purpose that is not
    listed is not minimised (every label the role can see is fine).
    """

    purpose_needs: dict = field(default_factory=dict)
    grants: list = field(default_factory=list)
    grant_ttl: float = 24 * 3600

    def grant(self, consent: ConsentRequest, now: Optional[float] = None,
              ttl: Optional[float] = None) -> Grant:
        now = time.time() if now is None else now
        g = Grant(consent.fact_id, consent.requester, consent.purpose,
                  now + (self.grant_ttl if ttl is None else ttl))
        self.grants.append(g)
        return g

    def revoke(self, fact_id: str, requester: str) -> None:
        for g in self.grants:
            if g.fact_id == fact_id and g.requester == requester:
                g.revoked = True

    def has_grant(self, fact: Fact, req: Request, now: float) -> bool:
        return any(g.fact_id == fact.id and g.requester == req.requester
                   and g.purpose == req.purpose and g.active(now) for g in self.grants)

    def allows(self, fact: Fact, req: Request, now: float) -> tuple[bool, str]:
        """(allowed, reason). Private facts are never allowed, grant or not."""
        if fact.label.is_private:
            return False, "private"
        if self.has_grant(fact, req, now):
            return True, "owner grant"
        if not fact.label.visible_to(req.role):
            return False, f"label {fact.label} not visible to role {req.role}"
        if fact.label.kind == "public":
            return True, "public"
        needs = self.purpose_needs.get(req.purpose)
        if needs is not None and not (set(needs) & set(fact.topics)):
            return False, f"purpose '{req.purpose}' does not need it"
        return True, str(fact.label)


# ---------------------------------------------------------------- ledger

@dataclass
class LedgerEntry:
    ts: float
    requester: str
    role: str
    purpose: str
    said: str
    disclosed: dict  # fact_id -> label/grant that allowed it
    blocked: list
    allowed_as_drafted: bool


class Ledger:
    """Append-only log of every reply: what was said, to whom, why, under which label."""

    def __init__(self) -> None:
        self.entries: list[LedgerEntry] = []

    def record(self, entry: LedgerEntry) -> None:
        self.entries.append(entry)

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(asdict(e), sort_keys=True) for e in self.entries)

    def disclosed_to(self, requester: str) -> set[str]:
        return {f for e in self.entries if e.requester == requester for f in e.disclosed}


# ---------------------------------------------------------------- check_reply

@dataclass
class Decision:
    allowed: bool          # True only when the draft may be sent unchanged
    rewritten: str         # what to send (== draft when allowed)
    reasons: list = field(default_factory=list)
    consent_requests: list = field(default_factory=list)


_SENT = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list[str]:
    return [s for s in _SENT.split(text.strip()) if s]


def _thread_text(thread: Iterable) -> str:
    parts = []
    for m in thread or ():
        parts.append(m if isinstance(m, str) else str(m.get("text", "")))
    return "\n".join(parts)


def check_reply(draft: str, facts: Sequence[Fact], request: Request,
                thread: Sequence = (), policy: Optional[Policy] = None,
                ledger: Optional[Ledger] = None, now: Optional[float] = None,
                judge: "Optional[Callable] | str" = "auto") -> Decision:
    """Run the three Need-to-Know checks on one outbound draft.

    1. Who's asking: role + purpose decide which labels may be said; the rest
       becomes a ConsentRequest to the owner.
    2. Use, don't say: private facts never appear, verbatim, by number or by alias.
    3. Hint check: no sentence may let the requester infer a private fact,
       alone or together with the thread so far.
    Then the optional LLM judge reviews the result. judge="auto" uses the local
    `claude -p` CLI only when env NTK_LLM=claude; pass None to disable or a
    callable(reply, facts, request, thread) -> str|None to supply your own.
    """
    if judge == "auto":
        from .judge import default_judge
        judge = default_judge()
    policy = policy or Policy()
    now = time.time() if now is None else now
    history = _thread_text(thread)
    reasons: list[str] = []
    consents: list[ConsentRequest] = []
    disclosed: dict[str, str] = {}
    kept: list[str] = []
    replaced: list[str] = []

    for sentence in _sentences(draft):
        problem = None
        for f in facts:
            said = f.said_in(sentence)
            if f.label.is_private:
                if said:
                    problem = (f, f"check2 use-don't-say: '{f.id}' ({said})")
                elif f.hinted_in(sentence):
                    problem = (f, f"check3 hint: '{f.id}' ({f.hinted_in(sentence)})")
                else:
                    here = f.weak_hits(sentence)
                    before = f.weak_hits(history)
                    if here and len(set(here) | set(before)) >= 2:
                        problem = (f, f"check3 hint with thread: '{f.id}' "
                                      f"({', '.join(sorted(set(here) | set(before)))})")
            elif said:
                ok, why = policy.allows(f, request, now)
                if ok:
                    disclosed[f.id] = why
                else:
                    problem = (f, f"check1 who's asking: '{f.id}' {why} -> consent request")
                    consents.append(ConsentRequest(f.id, f.owner, request.requester,
                                                   request.role, request.purpose, why))
            if problem:
                break
        if problem:
            f, why = problem
            reasons.append(why)
            if f.safe_say and f.safe_say not in replaced:
                replaced.append(f.safe_say)
                kept.append(f.safe_say)
        else:
            kept.append(sentence)

    rewritten = " ".join(kept).strip() or CANT_SHARE
    allowed = not reasons

    if judge is not None:
        verdict = judge(rewritten, facts, request, thread)
        if verdict:
            reasons.append(f"llm judge: {verdict}")
            rewritten, allowed = CANT_SHARE, False
            disclosed = {}

    if ledger is not None:
        ledger.record(LedgerEntry(now, request.requester, request.role, request.purpose,
                                  rewritten, disclosed, list(reasons), allowed))
    return Decision(allowed, draft if allowed else rewritten, reasons, consents)
