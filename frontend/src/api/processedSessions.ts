import { requestJson } from "./http";

export interface ProcessedSession {
  session_id: string;
  name: string;
  video_filename: string | null;
  video_availability: "available" | "missing" | "mismatch" | "not_configured" | null;
  job_id: string;
  status: "pending" | "processing" | "completed" | "failed" | "cancelled";
  finished_at: string | null;
  failure_code: string | null;
  failure_message: string | null;
  scene_version_id: string | null;
  version_number: number | null;
  result_complete: boolean;
}

export function listProcessedSessions(apiBaseUrl: string): Promise<ProcessedSession[]> {
  return requestJson<ProcessedSession[]>(`${apiBaseUrl}/processed-sessions`);
}
