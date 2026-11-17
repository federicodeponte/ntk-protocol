"""`ntk-mcp`: a Model Context Protocol server for Need-to-Know. Standard library only.

Speaks MCP over stdio (newline-delimited JSON-RPC 2.0) and exposes two tools:

  check_reply  run the three NTK checks on a draft before the agent sends it
  get_ledger   the disclosure ledger of this session

The owner's labelled facts live in a file the agent never has to repeat:

    NTK_FACTS=/path/facts.json   facts (and optional policy) for check_reply
    NTK_LEDGER=/path/ledger.jsonl append every ledger entry to this file
    NTK_LLM=claude               optional `claude -p` judge (no API keys)

A `facts` argument on the tool call overrides NTK_FACTS for that call.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from typing import Any, Optional

from . import __version__
from .core import Ledger, check_reply
from .loaders import decision_to_dict, load_facts_doc, policy_from_dict, read_json, \
    request_from_dict

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

CHECK_REPLY_TOOL = {
    "name": "check_reply",
    "title": "Need-to-Know check",
    "description": (
        "Call this BEFORE sending any reply to another agent or to someone other than your "
        "owner. It runs the Need-to-Know checks: (1) who is asking and why: share only labels "
        "the requester's role may hear and the purpose needs; (2) use it, don't say it: private "
        "facts never appear verbatim, by number or by paraphrase; (3) hint check: no sentence "
        "may let the requester infer a private fact, alone or with the thread so far. Send the "
        "returned `send` text, not your draft, whenever `allowed` is false. Forward any "
        "`consent_requests` to your owner instead of deciding yourself."),
    "inputSchema": {
        "type": "object",
        "properties": {
            "draft": {"type": "string", "description": "The reply you are about to send."},
            "requester": {"type": "string", "description": "Who is asking, e.g. 'jun-agent'."},
            "role": {"type": "string", "description": "The requester's role, e.g. 'collaborator'."},
            "purpose": {"type": "string", "description": "Why they ask, e.g. 'plan a study'."},
            "thread": {"type": "array", "items": {"type": "string"},
                       "description": "Earlier messages already sent to this requester."},
            "facts": {"type": "array", "items": {"type": "object"},
                      "description": "Optional labelled facts; defaults to the NTK_FACTS file."},
        },
        "required": ["draft", "requester", "role", "purpose"],
    },
    "annotations": {"readOnlyHint": True, "openWorldHint": False},
}

GET_LEDGER_TOOL = {
    "name": "get_ledger",
    "title": "Need-to-Know disclosure ledger",
    "description": "Return every reply checked in this session: what was said, to whom, "
                   "under which purpose, and which label allowed each disclosed fact.",
    "inputSchema": {"type": "object", "properties": {
        "requester": {"type": "string", "description": "Only entries for this requester."}}},
    "annotations": {"readOnlyHint": True, "openWorldHint": False},
}


class Server:
    def __init__(self, facts_path: Optional[str] = None, ledger_path: Optional[str] = None,
                 judge: Any = "auto"):
        self.facts_path = facts_path
        self.ledger_path = ledger_path
        self.judge = judge
        self.ledger = Ledger()

    # -------------------------------------------------------------- tools

    def _facts(self, inline):
        if inline is not None:
            return load_facts_doc(inline)
        if not self.facts_path:
            raise ValueError("no facts: set NTK_FACTS or pass `facts`")
        return load_facts_doc(read_json(self.facts_path))

    def tool_check_reply(self, args: dict) -> dict:
        facts, policy = self._facts(args.get("facts"))
        if "policy" in args:
            policy = policy_from_dict(args["policy"])
        request, _ = request_from_dict(args)
        thread = [str(m) for m in args.get("thread", [])]
        d = check_reply(str(args["draft"]), facts, request, thread, policy, self.ledger,
                        judge=self.judge)
        entry = self.ledger.entries[-1]
        if self.ledger_path:
            with open(self.ledger_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
        return decision_to_dict(d, entry)

    def tool_get_ledger(self, args: dict) -> dict:
        who = args.get("requester")
        rows = [asdict(e) for e in self.ledger.entries if not who or e.requester == who]
        return {"entries": rows}

    # -------------------------------------------------------------- JSON-RPC

    def handle(self, msg: dict) -> Optional[dict]:
        mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
        if mid is None:  # notification
            return None
        try:
            if method == "initialize":
                asked = params.get("protocolVersion")
                result = {
                    "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "ntk-mcp", "title": "Need-to-Know",
                                   "version": __version__},
                    "instructions": "Before replying to another agent, call check_reply with "
                                    "your draft and send its `send` field.",
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": [CHECK_REPLY_TOOL, GET_LEDGER_TOOL]}
            elif method == "tools/call":
                result = self._call(params.get("name"), params.get("arguments") or {})
            else:
                return _error(mid, -32601, f"method not found: {method}")
        except Exception as e:  # never crash the stdio loop
            return _error(mid, -32603, str(e))
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def _call(self, name: str, args: dict) -> dict:
        tools = {"check_reply": self.tool_check_reply, "get_ledger": self.tool_get_ledger}
        if name not in tools:
            raise ValueError(f"unknown tool: {name}")
        try:
            out = tools[name](args)
        except (ValueError, KeyError, TypeError, OSError) as e:
            return {"content": [{"type": "text", "text": f"ntk error: {e}"}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}],
                "structuredContent": out, "isError": False}

    def serve(self, stdin=None, stdout=None) -> None:
        stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                reply = _error(None, -32700, "parse error")
            else:
                reply = self.handle(msg) if isinstance(msg, dict) else \
                    _error(None, -32600, "batch requests are not supported")
            if reply is not None:
                stdout.write(json.dumps(reply) + "\n")
                stdout.flush()


def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help", "--version"):
        print(__doc__ if sys.argv[1] != "--version" else f"ntk-mcp {__version__}")
        return 0
    Server(os.environ.get("NTK_FACTS"), os.environ.get("NTK_LEDGER")).serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
