import type { SessionSummary } from "./session";

export type AnalysisStatus = "unanalysed" | "loading" | "unavailable" | "pending" | "processing" | "completed" | "incomplete" | "failed" | "cancelled";

export interface AnalysisItem {
  session: SessionSummary;
  status: AnalysisStatus;
  busy: boolean;
  ready: boolean;
  href: string;
  action: string;
  durationSeconds: number | null;
}
