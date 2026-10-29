export type FrameworkArea =
  | "purpose" | "journeys" | "structure" | "data" | "access"
  | "failure-recovery" | "verification" | "scope";

export const FRAMEWORK_AREAS: Record<FrameworkArea, string> = {
  purpose: "Purpose & users",
  journeys: "End-to-end journeys",
  structure: "Components & connections",
  data: "Data & lifecycle",
  access: "Access & permissions",
  "failure-recovery": "Failure & recovery",
  verification: "Acceptance & checks",
  scope: "Scope & exclusions",
};

export interface FrameworkQuestion {
  area: FrameworkArea;
  question: string;
  options: string[];
  code_diff: string;
  targets: string[];
}

export interface FrameworkReview {
  revision: number;
  source_hash: string;
  mode: "demo" | "live";
  framework: {
    sections: {
      area: FrameworkArea;
      entries: {
        aspect: string;
        text: string;
        status: "confirmed" | "proposal" | "unresolved";
        ledger_ids: string[];
      }[];
    }[];
    questions: FrameworkQuestion[];
  };
  assessment: {
    reviewed_entry_ids: string[];
    reviewed_areas: FrameworkArea[];
    issues: { area: FrameworkArea; detail: string }[];
    questions: FrameworkQuestion[];
  } | null;
}
