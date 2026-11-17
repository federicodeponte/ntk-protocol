/**
 * Optional LLM judge for checks 2 and 3, same contract as ntk/judge.py.
 *
 * Runs only when env NTK_LLM=claude. It shells out to the local `claude -p` CLI
 * (your Claude subscription login). It never uses an API key: ANTHROPIC_API_KEY
 * and friends are removed from the child environment.
 */

import { spawnSync } from "node:child_process";
import { _setAutoJudge, Fact, Judge, Request, ThreadMessage } from "./core.js";

const KEY_VARS = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_API_KEY"];

function prompt(reply: string, facts: readonly Fact[], r: Request, thread: readonly ThreadMessage[]) {
  const priv = facts.filter((f) => !f.label.visibleTo(r.role)).map((f) => `- ${f.id}: ${f.text}`).join("\n");
  const th = thread.map((m) => (typeof m === "string" ? m : String(m?.text ?? ""))).join("\n") || "(empty)";
  return `You are the Need-to-Know hint checker. An agent is about to send REPLY to
${r.requester} (role ${r.role}, purpose "${r.purpose}"). These facts are NOT for this requester (private, or limited to
another role) and must not be stated, paraphrased, or inferable from the reply, alone or together with
the THREAD so far:
${priv}

THREAD so far:
${th}

REPLY:
${reply}

Answer with one line of JSON only: {"leak": true|false, "fact_id": "...", "why": "..."}`;
}

/** Child environment with every API-key variable removed. */
export function judgeEnv(env: NodeJS.ProcessEnv = process.env): NodeJS.ProcessEnv {
  const out: NodeJS.ProcessEnv = {};
  for (const [k, v] of Object.entries(env)) if (!KEY_VARS.includes(k)) out[k] = v;
  return out;
}

/** Fails open to the deterministic result (returns null) if the CLI is missing or errors. */
export const claudeJudge: Judge = (reply, facts, request, thread) => {
  if (!facts.some((f) => !f.label.visibleTo(request.role))) return null;
  try {
    const p = spawnSync("claude", ["-p", prompt(reply, facts, request, thread)],
      { encoding: "utf8", timeout: 90_000, env: judgeEnv() });
    if (p.error || typeof p.stdout !== "string") return null;
    const line = p.stdout.split("\n").reverse().find((l) => l.trim().startsWith("{"));
    if (!line) return null;
    const v = JSON.parse(line);
    if (v.leak) return `'${v.fact_id ?? "?"}' ${v.why ?? ""}`.trim();
  } catch {
    return null;
  }
  return null;
};

export function defaultJudge(): Judge | null {
  return process.env.NTK_LLM === "claude" ? claudeJudge : null;
}

_setAutoJudge(defaultJudge);
