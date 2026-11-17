"""Optional LLM judge for checks 2 and 3.

Runs only when env NTK_LLM=claude. It shells out to the local `claude -p` CLI
(your Claude subscription login). It never uses an API key: ANTHROPIC_API_KEY
and friends are removed from the child environment.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Optional

_PROMPT = """You are the Need-to-Know checker. An agent is about to send REPLY to
{requester} (role {role}) for this purpose: "{purpose}".

Facts NOT for this requester (private, or limited to another role):
{private}

THREAD so far (what was already said to this requester):
{thread}

REPLY:
{reply}

Flag the reply only if one of these holds:
1. secret: it states, paraphrases or lets the reader infer a listed fact, alone or with the THREAD,
   and the purpose does not need that fact.
2. contradiction: it gives a date, number, status or commitment that conflicts with, or silently
   replaces, what the THREAD already told this requester.
3. unneeded: it volunteers something the purpose does not need that a careful sender keeps to
   himself: internal process or tooling, how the message was made, rebuttals to doubts the reader
   never raised, own weaknesses, or other people's private matters.
Do not flag ordinary content the purpose needs.

Answer with one line of JSON only: {{"leak": true|false, "kind": "secret|contradiction|unneeded", "fact_id": "...", "why": "..."}}"""

_KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_API_KEY")


def claude_judge(reply, facts, request, thread, timeout: int = 90) -> Optional[str]:
    """Return a reason string if the judge sees a leak, else None. Fails open to
    the deterministic result (returns None) if the CLI is missing or errors."""
    private = [f for f in facts if not f.label.visible_to(request.role)]
    if not private or not shutil.which("claude"):
        return None
    prompt = _PROMPT.format(
        requester=request.requester, role=request.role, purpose=request.purpose,
        private="\n".join(f"- {f.id}: {f.text}" for f in private),
        thread="\n".join(m if isinstance(m, str) else str(m.get("text", "")) for m in thread) or "(empty)",
        reply=reply)
    env = {k: v for k, v in os.environ.items() if k not in _KEY_VARS}
    try:
        out = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True,
                             timeout=timeout, env=env).stdout
        line = next(l for l in out.splitlines()[::-1] if l.strip().startswith("{"))
        verdict = json.loads(line)
    except Exception:
        return None
    if verdict.get("leak"):
        kind = verdict.get("kind") or "secret"
        return f"{kind} '{verdict.get('fact_id', '?')}' {verdict.get('why', '')}".strip()
    return None


def default_judge():
    return claude_judge if os.environ.get("NTK_LLM") == "claude" else None
