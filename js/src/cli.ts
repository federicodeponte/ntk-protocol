#!/usr/bin/env node
/**
 * `ntk-protocol` command line. Same JSON and exit codes as the Python `ntk` CLI.
 *
 *   npx ntk-protocol check --facts facts.json --request request.json "draft reply"
 *   echo "draft reply" | npx ntk-protocol check --facts facts.json --request request.json
 *   npx ntk-protocol mcp     # MCP server over stdio (tools check_reply, get_ledger)
 *
 * Exit code 0 = send the draft unchanged, 1 = send "send" instead, 2 = bad input.
 */

import { appendFileSync, readFileSync } from "node:fs";
import { checkReply, Ledger } from "./core.js";
import "./judge.js";
import { decisionToDict, loadFactsDoc, policyFromDict, requestFromDict } from "./loaders.js";
import { mcpMain } from "./mcp.js";
import { VERSION } from "./version.js";

const USAGE = `usage: ntk-protocol [-h] [--version] {check,mcp} ...

Need-to-Know: check what an agent may say to another agent.

  check --facts F --request R [--policy P] [--ledger L] [--now T] [--no-judge] [draft]
        run the three checks on one draft reply (draft from stdin when omitted)
  mcp   run the MCP server over stdio (env NTK_FACTS, NTK_LEDGER, NTK_LLM)
`;

class UsageError extends Error {}

interface CheckArgs {
  facts?: string; request?: string; policy?: string; ledger?: string; now?: number;
  noJudge: boolean; draft?: string;
}

function parseCheck(argv: string[]): CheckArgs {
  const a: CheckArgs = { noJudge: false };
  const valued: Record<string, keyof CheckArgs> = {
    "--facts": "facts", "--request": "request", "--policy": "policy", "--ledger": "ledger", "--now": "now" };
  for (let i = 0; i < argv.length; i++) {
    let tok = argv[i];
    let val: string | undefined;
    if (tok.startsWith("--") && tok.includes("=")) [tok, val] = [tok.slice(0, tok.indexOf("=")), tok.slice(tok.indexOf("=") + 1)];
    if (tok in valued) {
      if (val === undefined) {
        if (i + 1 >= argv.length) throw new UsageError(`argument ${tok}: expected one argument`);
        val = argv[++i];
      }
      if (tok === "--now") {
        const n = Number(val);
        if (!Number.isFinite(n)) throw new UsageError(`argument --now: invalid float value: '${val}'`);
        a.now = n;
      } else {
        (a as unknown as Record<string, string>)[valued[tok]] = val;
      }
    } else if (tok === "--no-judge") {
      a.noJudge = true;
    } else if (tok === "--") {
      if (i + 1 < argv.length) a.draft = argv.slice(i + 1).join(" ");
      break;
    } else if (tok.startsWith("-") && tok.length > 1 && a.draft === undefined && !/^-\d/.test(tok)) {
      throw new UsageError(`unrecognized arguments: ${tok}`);
    } else if (a.draft === undefined) {
      a.draft = tok;
    } else {
      throw new UsageError(`unrecognized arguments: ${tok}`);
    }
  }
  const missing = (["facts", "request"] as const).filter((k) => a[k] === undefined).map((k) => `--${k}`);
  if (missing.length) throw new UsageError(`the following arguments are required: ${missing.join(", ")}`);
  return a;
}

const readJson = (p: string): unknown => JSON.parse(readFileSync(p, "utf8"));

export function runCheck(argv: string[], io = {
  stdout: (s: string) => void process.stdout.write(s),
  stderr: (s: string) => void process.stderr.write(s),
  stdin: () => readFileSync(0, "utf8"),
}): number {
  let a: CheckArgs;
  try {
    a = parseCheck(argv);
  } catch (e) {
    io.stderr(USAGE + `ntk-protocol check: error: ${(e as Error).message}\n`);
    return 2;
  }
  let facts, policy, request, thread;
  try {
    [facts, policy] = loadFactsDoc(readJson(a.facts!));
    if (a.policy) policy = policyFromDict(readJson(a.policy));
    [request, thread] = requestFromDict(readJson(a.request!));
  } catch (e) {
    io.stderr(JSON.stringify({ error: String((e as Error).message ?? e) }) + "\n");
    return 2;
  }
  const draft = a.draft !== undefined ? a.draft : io.stdin();
  if (!draft.trim()) {
    io.stderr(JSON.stringify({ error: "empty draft" }) + "\n");
    return 2;
  }
  const ledger = new Ledger();
  const d = checkReply(draft, facts, request,
    { thread, policy, ledger, now: a.now, judge: a.noJudge ? null : "auto" });
  const entry = ledger.entries[ledger.entries.length - 1];
  if (a.ledger) appendFileSync(a.ledger, ledger.toJsonl() + "\n", "utf8");
  io.stdout(JSON.stringify(decisionToDict(d, entry), null, 2) + "\n");
  return d.allowed ? 0 : 1;
}

export async function main(argv: string[] = process.argv.slice(2)): Promise<number> {
  const [cmd, ...rest] = argv;
  if (cmd === "-h" || cmd === "--help") { process.stdout.write(USAGE); return 0; }
  if (cmd === "--version") { process.stdout.write(`ntk ${VERSION}\n`); return 0; }
  if (cmd === "check") return runCheck(rest);
  if (cmd === "mcp") return mcpMain(rest);
  process.stderr.write(USAGE + (cmd ? `ntk-protocol: error: invalid choice: '${cmd}'\n`
    : "ntk-protocol: error: the following arguments are required: cmd\n"));
  return 2;
}

main().then((code) => { process.exitCode = code; });
