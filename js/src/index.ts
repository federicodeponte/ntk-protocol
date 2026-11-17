/** Need-to-Know (NTK): HCP decides what your agent can know. NTK decides what it can say. */
export {
  CANT_SHARE, Label, Fact, Grant, Policy, Ledger, checkReply, consentToString, pyJsonSorted,
} from "./core.js";
export type {
  LabelKind, FactInit, Request, ConsentRequest, PolicyInit, LedgerEntry, Decision,
  ThreadMessage, Judge, CheckOptions,
} from "./core.js";
export { factFromDict, policyFromDict, loadFactsDoc, requestFromDict, decisionToDict } from "./loaders.js";
export type { DecisionDict } from "./loaders.js";
export { claudeJudge, defaultJudge } from "./judge.js";
export { Server, CHECK_REPLY_TOOL, GET_LEDGER_TOOL, PROTOCOL_VERSIONS } from "./mcp.js";
export { VERSION } from "./version.js";
