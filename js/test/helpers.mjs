import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadFactsDoc, Policy } from "../dist/index.js";

export const JS = join(dirname(fileURLToPath(import.meta.url)), "..");
export const ROOT = join(JS, "..");
export const FACTS = join(ROOT, "examples", "maya_facts.json");
export const REQUEST = join(ROOT, "examples", "jun_request.json");
export const CLI = join(JS, "dist", "cli.js");

export const readJson = (p) => JSON.parse(readFileSync(p, "utf8"));
export const mayaFacts = () => loadFactsDoc(readJson(FACTS))[0];
export const mayaPolicy = () => new Policy({ purpose_needs: { "plan a study": ["paper", "methods"] } });
