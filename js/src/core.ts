/**
 * Need-to-Know core: labels, requests, policy, consent, ledger and checkReply.
 * A line-for-line port of ntk/core.py. conformance/cases.json keeps the two in step.
 */

export const CANT_SHARE = "I can't share that.";

// ---------------------------------------------------------------- labels

export type LabelKind = "public" | "role" | "private";

/** `public`, `role:<name>` or `private`. */
export class Label {
  readonly kind: LabelKind;
  readonly role: string | null;

  constructor(kind: LabelKind, role: string | null = null) {
    this.kind = kind;
    this.role = role;
  }

  static parse(text: string | Label): Label {
    if (text instanceof Label) return text;
    if (typeof text !== "string") throw new TypeError(`unknown label: ${JSON.stringify(text)}`);
    const t = text.trim();
    if (t === "public") return new Label("public");
    if (t === "private") return new Label("private");
    if (t.startsWith("role:") && t.length > 5) return new Label("role", t.slice(5));
    throw new Error(`unknown label: '${t}'`);
  }

  get isPrivate(): boolean {
    return this.kind === "private";
  }

  visibleTo(role: string): boolean {
    if (this.kind === "public") return true;
    if (this.kind === "role") return this.role === role;
    return false;
  }

  toString(): string {
    return this.kind === "role" ? `role:${this.role}` : this.kind;
  }
}

// ---------------------------------------------------------------- text helpers
// Python's str regexes are Unicode-aware; these classes match its \w and \d.

const W = "[\\p{L}\\p{N}_]";
const D = "\\p{Nd}";
const NUM = new RegExp(
  `(?<!${W.slice(0, -1)}.:,])([$€£]?)(${D}+(?:[.,]${D}+)*)(?![${D.slice(0)}:])` +
    `(?:\\s?(k|thousand|m|mn|mio|million|bn|b|billion|%|pp|percent)(?!${W}))?`,
  "giu",
);
const UNIT: Record<string, string> = { thousand: "k", mn: "m", mio: "m", million: "m", bn: "b", billion: "b", percent: "%" };
const SENT = /(?<=[.!?])\s+/u;

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

type Num = [cur: string, value: string, unit: string];

/** A fact number distinctive enough to count as saying the fact: a currency or unit, a decimal,
 *  or 3+ digits that are not a bare year. "2022" or "20" alone match too much ordinary text. */
function specific(n: Num): boolean {
  const [cur, num, unit] = n;
  if (cur || unit || num.includes(".")) return true;
  return num.length >= 3 && !/^(19|20)\d\d$/.test(num);
}

/** Numbers as [currency, value, unit], so '$10m' is not '10' and '10:30' is a time, not two numbers. */
function numbers(text: string): Num[] {
  const out = new Map<string, Num>();
  for (const m of text.matchAll(NUM)) {
    const cur = m[1] ?? "";
    const num = m[2];
    let unit = (m[3] ?? "").toLowerCase();
    unit = UNIT[unit] ?? unit;
    if (cur || unit || num.includes(".") || num.includes(",") || num.length >= 2) {
      const n: Num = [cur, num.replace(/,/g, "."), unit];
      out.set(n.join("\u0000"), n);
    }
  }
  return [...out.values()];
}

/** Same value; currencies agree when both given; units agree unless one side omits the unit and the value is specific. */
function numMatch(a: Num, b: Num): boolean {
  if (a[1] !== b[1] || (a[0] && b[0] && a[0] !== b[0])) return false;
  const specific = a[1].includes(".") || a[1].length >= 3;
  if (a[2] === b[2]) return !(a[0] !== b[0] && !a[2] && !specific);
  if (a[2] && b[2]) return false;
  return specific;
}

function phraseIn(phrase: string, text: string): boolean {
  const re = new RegExp(`(?<!${W})${escapeRegExp(phrase.toLowerCase())}(?!${W})`, "u");
  return re.test(text.toLowerCase());
}

const sortStr = (xs: Iterable<string>): string[] =>
  [...xs].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));

// ---------------------------------------------------------------- facts

export interface FactInit {
  id: string;
  text: string;
  label: string | Label;
  /** Paraphrases that count as *saying* the fact (check 2). */
  aliases?: readonly string[];
  /** Cues that let a reader *infer* the fact (check 3), flagged alone. */
  hints?: readonly string[];
  /** Cues harmless alone that leak when two meet across draft and thread (check 3). */
  weak_hints?: readonly string[];
  /** What to say instead when a sentence leaks this fact. */
  safe_say?: string | null;
  /** What the fact is about, matched against a purpose's needs. */
  topics?: readonly string[];
  owner?: string;
}

/** One item the agent knows, with exactly one label. */
export class Fact {
  id: string;
  text: string;
  label: Label;
  aliases: string[];
  hints: string[];
  weak_hints: string[];
  safe_say: string | null;
  topics: string[];
  owner: string;

  constructor(init: FactInit) {
    this.id = init.id;
    this.text = init.text;
    this.label = Label.parse(init.label);
    this.aliases = [...(init.aliases ?? [])];
    this.hints = [...(init.hints ?? [])];
    this.weak_hints = [...(init.weak_hints ?? [])];
    this.safe_say = init.safe_say ?? null;
    this.topics = [...(init.topics ?? [])];
    this.owner = init.owner ?? "owner";
  }

  numbers(): Num[] {
    const out = numbers(this.text);
    for (const a of this.aliases) out.push(...numbers(a));
    return out.filter(specific);
  }

  /** Why `text` says this fact outright, or null. */
  saidIn(text: string): string | null {
    if (phraseIn(this.text, text)) return "verbatim";
    const said = numbers(text);
    const nums = [...new Set(this.numbers().filter((f) => said.some((t) => numMatch(f, t))).map((f) => f[1]))];
    if (nums.length) return "number " + sortStr(nums).join(",");
    for (const a of this.aliases) if (phraseIn(a, text)) return `paraphrase '${a}'`;
    return null;
  }

  hintedIn(text: string): string | null {
    for (const h of this.hints) if (phraseIn(h, text)) return `hint '${h}'`;
    return null;
  }

  weakHits(text: string): string[] {
    return this.weak_hints.filter((h) => phraseIn(h, text));
  }
}

// ---------------------------------------------------------------- requests, consent, policy

export interface Request {
  requester: string;
  role: string;
  purpose: string;
}

/** A one-tap ask to the owner: may `requester` hear `fact_id` for `purpose`? */
export interface ConsentRequest {
  fact_id: string;
  owner: string;
  requester: string;
  role: string;
  purpose: string;
  reason: string;
}

export function consentToString(c: ConsentRequest): string {
  return `ask ${c.owner}: share '${c.fact_id}' with ${c.requester} (${c.role}) for ` +
    `'${c.purpose}'? [${c.reason}]`;
}

export class Grant {
  constructor(
    public fact_id: string,
    public requester: string,
    public purpose: string,
    public expires_at: number,
    public revoked = false,
  ) {}

  active(now: number): boolean {
    return !this.revoked && now < this.expires_at;
  }
}

export interface PolicyInit {
  purpose_needs?: Record<string, readonly string[]>;
  grants?: Grant[];
  grant_ttl?: number;
}

/**
 * Check 1: which labels a role may hear, and which topics a purpose needs.
 * A purpose that is not listed in purpose_needs is not minimised.
 */
export class Policy {
  purpose_needs: Record<string, string[]>;
  grants: Grant[];
  grant_ttl: number;

  constructor(init: PolicyInit = {}) {
    this.purpose_needs = {};
    for (const [k, v] of Object.entries(init.purpose_needs ?? {})) this.purpose_needs[k] = [...v];
    this.grants = init.grants ?? [];
    this.grant_ttl = init.grant_ttl ?? 24 * 3600;
  }

  grant(consent: ConsentRequest, now?: number, ttl?: number): Grant {
    const t = now ?? Date.now() / 1000;
    const g = new Grant(consent.fact_id, consent.requester, consent.purpose,
      t + (ttl ?? this.grant_ttl));
    this.grants.push(g);
    return g;
  }

  revoke(factId: string, requester: string): void {
    for (const g of this.grants) if (g.fact_id === factId && g.requester === requester) g.revoked = true;
  }

  hasGrant(fact: Fact, req: Request, now: number): boolean {
    return this.grants.some((g) => g.fact_id === fact.id && g.requester === req.requester &&
      g.purpose === req.purpose && g.active(now));
  }

  /** [allowed, reason]. Private facts are never allowed, grant or not. */
  allows(fact: Fact, req: Request, now: number): [boolean, string] {
    if (fact.label.isPrivate) return [false, "private"];
    if (this.hasGrant(fact, req, now)) return [true, "owner grant"];
    if (!fact.label.visibleTo(req.role)) {
      return [false, `label ${fact.label} not visible to role ${req.role}`];
    }
    if (fact.label.kind === "public") return [true, "public"];
    const needs = Object.prototype.hasOwnProperty.call(this.purpose_needs, req.purpose)
      ? this.purpose_needs[req.purpose] : undefined;
    if (needs !== undefined && !needs.some((t) => fact.topics.includes(t))) {
      return [false, `purpose '${req.purpose}' does not need it`];
    }
    return [true, String(fact.label)];
  }
}

// ---------------------------------------------------------------- ledger

export interface LedgerEntry {
  ts: number;
  requester: string;
  role: string;
  purpose: string;
  said: string;
  /** fact_id -> label or grant that allowed it */
  disclosed: Record<string, string>;
  blocked: string[];
  allowed_as_drafted: boolean;
}

/** Python json.dumps(obj, sort_keys=True): ", " and ": " separators, sorted keys. */
export function pyJsonSorted(v: unknown): string {
  if (Array.isArray(v)) return "[" + v.map(pyJsonSorted).join(", ") + "]";
  if (v !== null && typeof v === "object") {
    const o = v as Record<string, unknown>;
    return "{" + sortStr(Object.keys(o)).map((k) => JSON.stringify(k) + ": " + pyJsonSorted(o[k]))
      .join(", ") + "}";
  }
  return JSON.stringify(v);
}

/** Append-only log of every reply: what was said, to whom, why, under which label. */
export class Ledger {
  entries: LedgerEntry[] = [];

  record(entry: LedgerEntry): void {
    this.entries.push(entry);
  }

  toJsonl(): string {
    return this.entries.map(pyJsonSorted).join("\n");
  }

  disclosedTo(requester: string): Set<string> {
    const out = new Set<string>();
    for (const e of this.entries) if (e.requester === requester) for (const f of Object.keys(e.disclosed)) out.add(f);
    return out;
  }
}

// ---------------------------------------------------------------- checkReply

export interface Decision {
  /** True only when the draft may be sent unchanged. */
  allowed: boolean;
  /** What to send (=== draft when allowed). */
  rewritten: string;
  reasons: string[];
  consent_requests: ConsentRequest[];
}

export type ThreadMessage = string | { text?: unknown };
/** Return a reason string when the reply leaks, else null/undefined. */
export type Judge = (reply: string, facts: readonly Fact[], request: Request,
  thread: readonly ThreadMessage[]) => string | null | undefined;

export interface CheckOptions {
  thread?: readonly ThreadMessage[];
  policy?: Policy;
  ledger?: Ledger;
  now?: number;
  /** "auto" (default) = local `claude -p` only when env NTK_LLM=claude; null = off. */
  judge?: Judge | "auto" | null;
}

function sentences(text: string): string[] {
  return text.trim().split(SENT).filter((s) => s);
}

function threadText(thread: readonly ThreadMessage[] | undefined): string {
  return (thread ?? []).map((m) => (typeof m === "string" ? m : String(m?.text ?? ""))).join("\n");
}

let autoJudge: () => Judge | null = () => null;
/** @internal set by judge.ts so core stays free of node: imports. */
export function _setAutoJudge(f: () => Judge | null): void {
  autoJudge = f;
}

/**
 * Run the three Need-to-Know checks on one outbound draft.
 *
 * 1. Who's asking: role + purpose decide which labels may be said; the rest
 *    becomes a ConsentRequest to the owner.
 * 2. Use, don't say: private facts never appear, verbatim, by number or by alias.
 * 3. Hint check: no sentence may let the requester infer a private fact,
 *    alone or together with the thread so far.
 */
export function checkReply(draft: string, facts: readonly Fact[], request: Request,
  opts: CheckOptions = {}): Decision {
  let judge = opts.judge === undefined ? "auto" : opts.judge;
  if (judge === "auto") judge = autoJudge();
  const policy = opts.policy ?? new Policy();
  const now = opts.now ?? Date.now() / 1000;
  const thread = opts.thread ?? [];
  const history = threadText(thread);
  const reasons: string[] = [];
  const consents: ConsentRequest[] = [];
  let disclosed: Record<string, string> = {};
  const kept: string[] = [];
  const replaced: string[] = [];

  for (const sentence of sentences(draft)) {
    let problem: [Fact, string] | null = null;
    for (const f of facts) {
      const said = f.saidIn(sentence);
      if (f.label.isPrivate) {
        const hint = said ? null : f.hintedIn(sentence);
        if (said) {
          problem = [f, `check2 use-don't-say: '${f.id}' (${said})`];
        } else if (hint) {
          problem = [f, `check3 hint: '${f.id}' (${hint})`];
        } else {
          const here = f.weakHits(sentence);
          const all = new Set([...here, ...f.weakHits(history)]);
          if (here.length && all.size >= 2) {
            problem = [f, `check3 hint with thread: '${f.id}' (${sortStr(all).join(", ")})`];
          }
        }
      } else if (said) {
        const [ok, why] = policy.allows(f, request, now);
        if (ok) {
          disclosed[f.id] = why;
        } else {
          problem = [f, `check1 who's asking: '${f.id}' ${why} -> consent request`];
          consents.push({ fact_id: f.id, owner: f.owner, requester: request.requester,
            role: request.role, purpose: request.purpose, reason: why });
        }
      }
      if (problem) break;
    }
    if (problem) {
      const [f, why] = problem;
      reasons.push(why);
      if (f.safe_say && !replaced.includes(f.safe_say)) {
        replaced.push(f.safe_say);
        kept.push(f.safe_say);
      }
    } else {
      kept.push(sentence);
    }
  }

  let rewritten = kept.join(" ").trim() || CANT_SHARE;
  let allowed = reasons.length === 0;

  if (judge) {
    const verdict = judge(rewritten, facts, request, thread);
    if (verdict) {
      reasons.push(`llm judge: ${verdict}`);
      rewritten = CANT_SHARE;
      allowed = false;
      disclosed = {};
    }
  }

  opts.ledger?.record({ ts: now, requester: request.requester, role: request.role,
    purpose: request.purpose, said: rewritten, disclosed, blocked: [...reasons],
    allowed_as_drafted: allowed });
  return { allowed, rewritten: allowed ? draft : rewritten, reasons, consent_requests: consents };
}
