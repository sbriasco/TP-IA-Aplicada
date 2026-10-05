export interface LiveSource {
  machine_id: string;
  device_index: number;
  capture_backend: string;
  width: number;
  height: number;
  reported_fps: number | null;
  label_mode: "directions" | "access";
  prepared_at: string;
  frame_checked_at: string | null;
}

export interface LiveDevices {
  machine_id: string;
  worker_available: boolean;
  candidates: { device_index: number; label: string; verified: false }[];
}

export interface LiveCheck {
  check_token: string;
  expires_in_seconds: number;
  width: number;
  height: number;
  backend: string;
  image_media_type: "image/jpeg";
  image_base64: string;
}

export interface LiveJobCreated {
  id: string;
  kind: "live_analysis";
  status: "pending";
}

export interface LiveResults {
  job_id: string; session_id: string; source_kind: "webcam";
  status: "pending" | "processing" | "completed" | "failed" | "cancelled";
  capture_status: string; result_complete: boolean; coverage_complete: boolean;
  unknown_tail: boolean; elapsed_capture_seconds: number; revision: number;
  checkpoint_at: string | null; selected_shop_id: string | null;
  shops: { shop_id: string; shop_name: string }[];
  summary: import("../api/liveMessages").LiveShopSnapshot | null;
  minutes: import("../api/liveMessages").LiveMinute[];
  next_bucket_cursor: number | null;
  interruptions: { id: string; start_seconds: number; end_seconds: number | null; end_known: boolean; reason: string }[];
  observed_seconds: number; missing_seconds: number; unconfirmed_crossings: number;
  sampling: { time_basis: "capture"; sample_count: number; candidate_count: number; capacity: number };
}
