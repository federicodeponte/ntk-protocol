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

_PROMPT = """You are the Need-to-Know hint checker. An agent is about to send REPLY to
{requester} (role {role}, purpose "{purpose}"). These facts are PRIVATE and must
not be stated, paraphrased, or inferable from the reply, alone or together with
the THREAD so far:
{private}

THREAD so far:
{thread}

REPLY:
{reply}

Answer with one line of JSON only: {{"leak": true|false, "fact_id": "...", "why": "..."}}"""

_KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_API_KEY")


def claude_judge(reply, facts, request, thread, timeout: int = 90) -> Optional[str]:
    """Return a reason string if the judge sees a leak, else None. Fails open to
    the deterministic result (returns None) if the CLI is missing or errors."""
    private = [f for f in facts if f.label.is_private]
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
        return f"'{verdict.get('fact_id', '?')}' {verdict.get('why', '')}".strip()
    return None


def default_judge():
    return claude_judge if os.environ.get("NTK_LLM") == "claude" else None
