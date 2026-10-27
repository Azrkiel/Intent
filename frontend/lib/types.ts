export type Slot =
  "goal" | "core-flow" | "data" | "access" | "non-goals" | "success-criterion";
export type Lens =
  "data" | "identity" | "behaviour" | "contradictions" | "edges" | "done-ness";
export interface LedgerItem {
  id: string;
  type: string;
  text: string;
  status: "confirmed" | "inferred" | "open" | "conflict";
  source: string | null;
  slot: Slot | null;
  turn: number;
}
export interface Question {
  id: string;
  lens: Lens;
  targets: string[];
  question: string;
  options: string[];
  code_diff: string;
  divergence: number;
  uncertainty: number;
  cost_to_change: number;
  impact: number;
  slot: Slot | null;
}
export interface Gate {
  ready: boolean;
  percent: number;
  filled: Slot[];
  missing: Slot[];
  blockers: string[];
}
export interface Build {
  status: "idle" | "running" | "complete" | "failed";
  logs: string[];
  directory: string | null;
  preview_url: string | null;
  demo: boolean;
}
export interface Session {
  id: string;
  title: string;
  mode: "demo" | "live";
  revision: number;
  turns: {
    number: number;
    text: string;
    question_id: string | null;
    at: string;
  }[];
  ledger: LedgerItem[];
  questions: { question: Question; answer: string; turn: number }[];
  candidates: Question[];
  rejected_candidates: Question[];
  current_question: Question | null;
  gate: Gate;
  playback: { sentences: string[] } | null;
  playback_revision: number | null;
  approved_revision: number | null;
  brief: {
    markdown: string;
    lines: { section: string; text: string; ledger_ids: string[] }[];
  } | null;
  analysis_complete: boolean;
  warnings: string[];
  estimated_usd: number;
  usage: {
    role: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    estimated_usd: number;
    latency_ms: number;
  }[];
  build: Build;
}
export interface Health {
  mode: "demo" | "live";
  models_configured: boolean;
  build_enabled: boolean;
}
export type StreamEvent = {
  type: string;
  message?: string;
  session?: Session;
  lens?: Lens;
  count?: number;
  failed?: boolean;
};
