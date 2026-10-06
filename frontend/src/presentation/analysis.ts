import type { ProcessedSession } from "../api/processedSessions";
import type { AnalysisItem } from "../types/analysis";
import type { SessionSummary } from "../types/session";

export function analysisItem(session: SessionSummary, job: ProcessedSession | undefined, jobsLoaded: boolean, jobsUnavailable: boolean): AnalysisItem {
  const busy = job?.status === "pending" || job?.status === "processing";
  const ready = job?.status === "completed" && job.result_complete;
  const path = "/sessions/" + encodeURIComponent(session.id);
  const live = session.source_kind === "webcam";
  const duration = live ? job?.live_duration_seconds : null;
  return { session, busy, ready,
    status: !jobsLoaded ? "loading" : jobsUnavailable ? "unavailable" : !job ? "unanalysed" : job.status === "completed" && !ready ? "incomplete" : job.status,
    href: live && job ? `/live/jobs/${encodeURIComponent(job.job_id)}${busy ? "" : "/results"}` : busy && job ? "/?job=" + encodeURIComponent(job.job_id) : ready ? path + "/results" : path,
    action: live && job ? busy ? "Ver en vivo" : "Ver resultados" : busy ? "Ver avance" : ready ? "Ver resultados" : "Continuar",
    durationSeconds: duration != null && Number.isFinite(duration) && duration >= 0 ? duration : null,
  };
}

export function analysisDuration(seconds: number | null): string {
  return seconds === null ? "Sin datos" : [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, Math.floor(seconds) % 60]
    .map(value => String(value).padStart(2, "0")).join(":");
}
