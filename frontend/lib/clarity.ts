export type NorthStarField = "who-when" | "job" | "ambition" | "today" | "good" | "fails-if";

export const NORTH_STAR_ORDER: NorthStarField[] = ["who-when", "job", "ambition", "today", "good", "fails-if"];

export const FIELD_LABELS: Record<NorthStarField, string> = {
  "who-when": "Who & when", job: "Job", ambition: "Ambition",
  today: "Today", good: "Good looks like", "fails-if": "Fails if",
};

export interface FieldState {
  field: NorthStarField;
  text: string;
  text_hash: string;
  judgement: { readback: string } | null;
  alpha: number | null;
  failing: string[];
  passed: boolean;
}

export interface Claim {
  id: string;
  text: string;
  tags: string[];
  status: "confirmed" | "derived" | "proposal" | "excluded";
  spans: { item_id: string; quote: string }[];
  flags: string[];
}

export interface Scenario {
  id: string;
  title: string;
  given: string;
  when: string;
  then: string;
  claims: string[];
  kind: "journey" | "failure" | "exclusion";
}

export interface Decision {
  id: string;
  status: "open" | "decided" | "delegated" | "deferred" | "excluded";
  question: string;
  options: string[];
  outcome: string | null;
  because: string | null;
  reversibility: "one-way" | "two-way";
  due_phase: string | null;
}

export interface ClarityState {
  revision: number;
  source_hash: string;
  mode: "demo" | "live";
  fields: FieldState[];
  fatigued: boolean;
  claims: Claim[];
  scenarios: Scenario[];
  decisions: Decision[];
  review: { canaries: unknown[]; caught: string[]; trusted: boolean } | null;
  downstream_complete: boolean;
}

export interface ClarityReadout {
  statements: number;
  unmapped_words: number;
  choices_made: number;
  decisions_open: number;
  scenarios: number;
}
