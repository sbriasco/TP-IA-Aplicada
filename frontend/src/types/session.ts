export type SourceKind = "synthetic" | "video_file";

export type VideoAvailability = "available" | "missing" | "mismatch" | "not_configured";

export interface Camera {
  id: string;
  name: string;
  created_at: string;
}

export interface SessionSummary {
  id: string;
  name: string;
  source_kind: SourceKind;
  camera: Camera;
  created_at: string;
}

export interface VideoSource {
  relative_path: string;
  original_filename: string;
  size_bytes: number;
  sha256: string;
  origin_machine_id: string;
  width: number;
  height: number;
  fps: number;
  fps_is_estimated: boolean;
  frame_count: number;
  duration_seconds: number;
  registered_at: string;
  availability: VideoAvailability;
}

export interface ReferenceFrame {
  frame_index: number;
  video_timestamp_seconds: number;
  width: number;
  height: number;
  /** Ruta relativa a la API: `/sessions/{id}/reference-frame`. */
  url: string;
}

export interface SessionDetail extends SessionSummary {
  /** Texto de trazabilidad de specs/002; el UUID de la cámara es `camera.id`. */
  camera_id: string;
  video: VideoSource | null;
  reference_frame: ReferenceFrame | null;
  duplicate_session_ids: string[];
}

export interface ApiError {
  /** Código HTTP; 0 si no hubo respuesta de la API. */
  status: number;
  code: string;
  message: string;
  /** Campos adicionales de `detail`, p. ej. `existing_camera` en `camera_exists`. */
  extra: Record<string, unknown>;
}
