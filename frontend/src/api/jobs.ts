export interface JobState {
  id: string;
  session_id: string;
  status: "pending" | "processing" | "completed" | "failed";
}

export interface PreviewMessage {
  type: "preview.update";
  frame_index: number;
  video_timestamp_seconds: number;
  progress_percent: number;
  image_media_type: "image/jpeg";
  image_base64: string;
}

export interface TerminalMessage {
  type: "job.terminal";
  status: "completed" | "failed";
}

export async function getJob(apiBaseUrl: string, jobId: string): Promise<JobState> {
  const response = await fetch(`${apiBaseUrl}/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(response.status === 404 ? "job_not_found" : "api_unavailable");
  }
  return (await response.json()) as JobState;
}

export function previewUrl(apiBaseUrl: string, jobId: string): string {
  const url = new URL(apiBaseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `/ws/jobs/${jobId}/preview`;
  return url.toString();
}
