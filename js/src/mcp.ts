/**
 * `npx ntk-protocol mcp`: a Model Context Protocol server for Need-to-Know.
 * Same tools and JSON as the Python `ntk-mcp`. No dependencies.
 *
 * Speaks MCP over stdio (newline-delimited JSON-RPC 2.0) and exposes two tools:
 *   check_reply  run the three NTK checks on a draft before the agent sends it
 *   get_ledger   the disclosure ledger of this session
 *
 *   NTK_FACTS=/path/facts.json    facts (and optional policy) for check_reply
 *   NTK_LEDGER=/path/ledger.jsonl append every ledger entry to this file
 *   NTK_LLM=claude                optional `claude -p` judge (no API keys)
 */

import { appendFileSync, readFileSync } from "node:fs";
import { createInterface } from "node:readline";
import { checkReply, Fact, Judge, Ledger, Policy, pyJsonSorted } from "./core.js";
import { decisionToDict, loadFactsDoc, policyFromDict, requestFromDict } from "./loaders.js";
import { VERSION } from "./version.js";
import "./judge.js";

export const PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"];

export const CHECK_REPLY_TOOL = {
  name: "check_reply",
  title: "Need-to-Know check",
  description:
    "Call this BEFORE sending any reply to another agent or to someone other than your " +
    "owner. It runs the Need-to-Know checks: (1) who is asking and why: share only labels " +
    "the requester's role may hear and the purpose needs; (2) use it, don't say it: private " +
    "facts never appear verbatim, by number or by paraphrase; (3) hint check: no sentence " +
    "may let the requester infer a private fact, alone or with the thread so far. Send the " +
    "returned `send` text, not your draft, whenever `allowed` is false. Forward any " +
    "`consent_requests` to your owner instead of deciding yourself.",
  inputSchema: {
    type: "object",
    properties: {
      draft: { type: "string", description: "The reply you are about to send." },
      requester: { type: "string", description: "Who is asking, e.g. 'jun-agent'." },
      role: { type: "string", description: "The requester's role, e.g. 'collaborator'." },
      purpose: { type: "string", description: "Why they ask, e.g. 'plan a study'." },
      thread: { type: "array", items: { type: "string" },
        description: "Earlier messages already sent to this requester." },
      facts: { type: "array", items: { type: "object" },
        description: "Optional labelled facts; defaults to the NTK_FACTS file." },
    },
    required: ["draft", "requester", "role", "purpose"],
  },
  annotations: { readOnlyHint: true, openWorldHint: false },
};

export const GET_LEDGER_TOOL = {
  name: "get_ledger",
  title: "Need-to-Know disclosure ledger",
  description: "Return every reply checked in this session: what was said, to whom, " +
    "under which purpose, and which label allowed each disclosed fact.",
  inputSchema: { type: "object", properties: {
    requester: { type: "string", description: "Only entries for this requester." } } },
  annotations: { readOnlyHint: true, openWorldHint: false },
};

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

class ToolError extends Error {}

export class Server {
  ledger = new Ledger();

  constructor(public factsPath: string | null = null, public ledgerPath: string | null = null,
    public judge: Judge | "auto" | null = "auto") {}

  private facts(inline: unknown): [Fact[], Policy] {
    if (inline !== undefined && inline !== null) return loadFactsDoc(inline);
    if (!this.factsPath) throw new ToolError("no facts: set NTK_FACTS or pass `facts`");
    return loadFactsDoc(JSON.parse(readFileSync(this.factsPath, "utf8")));
  }

  toolCheckReply(args: Json): Json {
    let [facts, policy] = this.facts(args.facts);
    if ("policy" in args) policy = policyFromDict(args.policy);
    const [request] = requestFromDict(args);
    if (!("draft" in args)) throw new ToolError("'draft'");
    const thread = ((args.thread ?? []) as unknown[]).map((m) => (typeof m === "string" ? m : JSON.stringify(m)));
    const d = checkReply(String(args.draft), facts, request,
      { thread, policy, ledger: this.ledger, judge: this.judge });
    const entry = this.ledger.entries[this.ledger.entries.length - 1];
    if (this.ledgerPath) appendFileSync(this.ledgerPath, pyJsonSorted(entry) + "\n", "utf8");
    return decisionToDict(d, entry) as Json;
  }

  toolGetLedger(args: Json): Json {
    const who = args.requester;
    return { entries: this.ledger.entries.filter((e) => !who || e.requester === who).map((e) => ({ ...e })) };
  }

  handle(msg: Json): Json | null {
    const mid = msg.id, method = msg.method, params = msg.params ?? {};
    if (mid === undefined || mid === null) return null; // notification
    let result: Json;
    try {
      if (method === "initialize") {
        const asked = params.protocolVersion;
        result = {
          protocolVersion: PROTOCOL_VERSIONS.includes(asked) ? asked : PROTOCOL_VERSIONS[0],
          capabilities: { tools: { listChanged: false } },
          serverInfo: { name: "ntk-mcp", title: "Need-to-Know", version: VERSION },
          instructions: "Before replying to another agent, call check_reply with " +
            "your draft and send its `send` field.",
        };
      } else if (method === "ping") {
        result = {};
      } else if (method === "tools/list") {
        result = { tools: [CHECK_REPLY_TOOL, GET_LEDGER_TOOL] };
      } else if (method === "tools/call") {
        result = this.call(params.name, params.arguments ?? {});
      } else {
        return rpcError(mid, -32601, `method not found: ${method}`);
      }
    } catch (e) { // never crash the stdio loop
      return rpcError(mid, -32603, String((e as Error).message ?? e));
    }
    return { jsonrpc: "2.0", id: mid, result };
  }

  private call(name: string, args: Json): Json {
    const tools: Record<string, (a: Json) => Json> = {
      check_reply: (a) => this.toolCheckReply(a), get_ledger: (a) => this.toolGetLedger(a) };
    if (!(name in tools)) throw new Error(`unknown tool: ${name}`);
    let out: Json;
    try {
      out = tools[name](args);
    } catch (e) {
      return { content: [{ type: "text", text: `ntk error: ${(e as Error).message ?? e}` }], isError: true };
    }
    return { content: [{ type: "text", text: JSON.stringify(out) }], structuredContent: out, isError: false };
  }

  serve(input: NodeJS.ReadableStream = process.stdin,
    output: NodeJS.WritableStream = process.stdout): Promise<void> {
    const rl = createInterface({ input, crlfDelay: Infinity });
    rl.on("line", (raw) => {
      const line = raw.trim();
      if (!line) return;
      let reply: Json | null;
      try {
        const msg = JSON.parse(line);
        reply = msg !== null && typeof msg === "object" && !Array.isArray(msg)
          ? this.handle(msg) : rpcError(null, -32600, "batch requests are not supported");
      } catch {
        reply = rpcError(null, -32700, "parse error");
      }
      if (reply !== null) output.write(JSON.stringify(reply) + "\n");
    });
    return new Promise((resolve) => rl.on("close", () => resolve()));
  }
}

function rpcError(mid: unknown, code: number, message: string): Json {
  return { jsonrpc: "2.0", id: mid, error: { code, message } };
}

export const MCP_HELP = `npx ntk-protocol mcp: Need-to-Know MCP server over stdio.

Tools: check_reply, get_ledger (same as the Python ntk-mcp).

  NTK_FACTS=/path/facts.json    facts (and optional policy) for check_reply
  NTK_LEDGER=/path/ledger.jsonl append every ledger entry to this file
  NTK_LLM=claude                optional \`claude -p\` judge (no API keys)
`;

export function mcpMain(argv: string[] = []): Promise<number> | number {
  if (argv[0] === "-h" || argv[0] === "--help") {
    process.stdout.write(MCP_HELP);
    return 0;
  }
  if (argv[0] === "--version") {
    process.stdout.write(`ntk-mcp ${VERSION}\n`);
    return 0;
  }
  return new Server(process.env.NTK_FACTS || null, process.env.NTK_LEDGER || null).serve().then(() => 0);
}
