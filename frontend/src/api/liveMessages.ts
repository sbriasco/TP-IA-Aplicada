type RecordValue = Record<string, unknown>;
const record = (value: unknown): value is RecordValue =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value) && value >= 0;
const integer = (value: unknown): value is number => finite(value) && Number.isSafeInteger(value);
const identifier = (value: unknown): value is string => typeof value === "string" && value.length > 0 && value.length <= 128;

export interface LiveShopSnapshot {
  shop_id: string; shop_name: string; entry_count: number; exit_count: number;
  a_to_b_count: number; b_to_a_count: number; total_crossings: number;
  label_mode: "directions" | "access"; partial: boolean;
  entry_direction?: "a_to_b" | "b_to_a" | null;
}
export interface LiveMinute {
  shop_id: string; bucket_index: number; start_seconds: number; end_seconds: number;
  entries: number; exits: number; observed_seconds: number; missing_seconds: number;
  pending_count: number; is_open: boolean; coverage_incomplete: boolean;
  unknown_tail: boolean; revision: number;
}
export interface LiveZoneDwell {
  interior_average_seconds: number | null; front_average_seconds: number | null;
  interior_sample_count: number; front_sample_count: number;
}
export interface LiveUpdate {
  type: "live.update"; schema_version: "3"; source_kind: "webcam";
  job_id: string; session_id: string; revision: number; capture_sequence: number;
  segment_index: number; capture_status: "connected"; capture_timestamp_seconds: number;
  captured_monotonic_ms: number; published_monotonic_ms: number;
  image_media_type: "image/jpeg"; image_base64: string; partial: true;
  capture_fps: number | null; analysis_fps: number | null; capture_to_publish_ms: number;
  shops: LiveShopSnapshot[]; minutes: LiveMinute[]; coverage_complete: boolean;
  checkpoint_revision: number; checkpoint_at: string | null;
  capture_started_at?: string | null;
  zone_dwell?: Record<string, LiveZoneDwell>;
}
export interface ClockPong {
  type: "clock.pong"; nonce: string; client_sent_ms: number;
  server_received_monotonic_ms: number; server_sent_monotonic_ms: number;
}
export interface LiveReconnectCheck {
  type: "live.reconnect-check"; schema_version: "3"; source_kind: "webcam";
  job_id: string; session_id: string; revision: number; segment_index: number;
  capture_status: "awaiting_confirmation"; device_index: number;
  width: number; height: number; backend: "dshow" | "msmf" | "fake";
  image_media_type: "image/jpeg"; image_base64: string;
  check_token: string; expires_in_seconds: number;
}

function shop(value: unknown): value is LiveShopSnapshot {
  if (!record(value) || !identifier(value.shop_id) || typeof value.shop_name !== "string") return false;
  const keys = ["entry_count", "exit_count", "a_to_b_count", "b_to_a_count", "total_crossings"];
  if (!keys.every((key) => integer(value[key]))) return false;
  return Number(value.entry_count) + Number(value.exit_count) === value.total_crossings &&
    Number(value.a_to_b_count) + Number(value.b_to_a_count) === value.total_crossings &&
    (value.label_mode === "directions" || value.label_mode === "access") && typeof value.partial === "boolean" &&
    (value.entry_direction === undefined || value.entry_direction === null || value.entry_direction === "a_to_b" || value.entry_direction === "b_to_a");
}
function minute(value: unknown): value is LiveMinute {
  if (!record(value) || !identifier(value.shop_id)) return false;
  if (!["bucket_index", "entries", "exits", "pending_count", "revision"].every((key) => integer(value[key]))) return false;
  if (!["start_seconds", "end_seconds", "observed_seconds", "missing_seconds"].every((key) => finite(value[key]))) return false;
  const start = Number(value.start_seconds), end = Number(value.end_seconds);
  return start === Number(value.bucket_index) * 60 && end >= start && end <= start + 60 &&
    Number(value.observed_seconds) + Number(value.missing_seconds) <= end - start + 0.000001 &&
    ["is_open", "coverage_incomplete", "unknown_tail"].every((key) => typeof value[key] === "boolean");
}

export function parseLiveMessage(value: unknown): LiveUpdate | ClockPong | LiveReconnectCheck | null {
  if (!record(value)) return null;
  if (value.type === "clock.pong") {
    if (!identifier(value.nonce) || !["client_sent_ms", "server_received_monotonic_ms", "server_sent_monotonic_ms"].every((key) => finite(value[key]))) return null;
    if (Number(value.server_sent_monotonic_ms) < Number(value.server_received_monotonic_ms)) return null;
    return value as unknown as ClockPong;
  }
  if (value.type === "live.reconnect-check") {
    const keys = new Set(["type", "schema_version", "source_kind", "job_id", "session_id",
      "revision", "segment_index", "capture_status", "device_index", "width", "height",
      "backend", "image_media_type", "image_base64", "check_token", "expires_in_seconds"]);
    if (Object.keys(value).some((key) => !keys.has(key)) || value.schema_version !== "3" ||
      value.source_kind !== "webcam" || value.capture_status !== "awaiting_confirmation" ||
      !identifier(value.job_id) || !identifier(value.session_id) || !identifier(value.check_token) ||
      !["revision", "segment_index", "device_index", "width", "height", "expires_in_seconds"].every((key) => integer(value[key])) ||
      Number(value.device_index) > 32 || Number(value.width) < 1 || Number(value.width) > 1920 ||
      Number(value.height) < 1 || Number(value.height) > 1080 || Number(value.expires_in_seconds) < 1 || Number(value.expires_in_seconds) > 60 ||
      !["dshow", "msmf", "fake"].includes(String(value.backend)) || value.image_media_type !== "image/jpeg" ||
      typeof value.image_base64 !== "string" || value.image_base64.length < 4 || value.image_base64.length > 273068 ||
      !/^[A-Za-z0-9+/]+={0,2}$/.test(value.image_base64)) return null;
    return value as unknown as LiveReconnectCheck;
  }
  if (value.type !== "live.update" || value.schema_version !== "3" || value.source_kind !== "webcam" || value.capture_status !== "connected") return null;
  if (value.capture_started_at !== undefined && value.capture_started_at !== null &&
    (typeof value.capture_started_at !== "string" || !Number.isFinite(Date.parse(value.capture_started_at)))) return null;
  if (value.zone_dwell !== undefined && (!record(value.zone_dwell) || Object.keys(value.zone_dwell).length > 20 ||
    Object.entries(value.zone_dwell).some(([key, item]) => !identifier(key) || !record(item) ||
      ![item.interior_average_seconds, item.front_average_seconds].every((average) => average === null || finite(average)) ||
      ![item.interior_sample_count, item.front_sample_count].every(integer)))) return null;
  if (!identifier(value.job_id) || !identifier(value.session_id)) return null;
  if (!["revision", "capture_sequence", "segment_index", "checkpoint_revision"].every((key) => integer(value[key]))) return null;
  if (!["capture_timestamp_seconds", "captured_monotonic_ms", "published_monotonic_ms", "capture_to_publish_ms"].every((key) => finite(value[key]))) return null;
  if (Number(value.checkpoint_revision) > Number(value.revision) || Number(value.published_monotonic_ms) < Number(value.captured_monotonic_ms)) return null;
  if (value.image_media_type !== "image/jpeg" || typeof value.image_base64 !== "string" || value.image_base64.length === 0 || value.image_base64.length > 273068 || !/^[A-Za-z0-9+/]+={0,2}$/.test(value.image_base64)) return null;
  if (value.partial !== true || typeof value.coverage_complete !== "boolean" || !(value.checkpoint_at === null || typeof value.checkpoint_at === "string")) return null;
  if (![value.capture_fps, value.analysis_fps].every((fps) => fps === null || finite(fps))) return null;
  if (!Array.isArray(value.shops) || value.shops.length > 20 || !value.shops.every(shop) || new Set(value.shops.map((item) => item.shop_id)).size !== value.shops.length) return null;
  if (!Array.isArray(value.minutes) || value.minutes.length > 1200 || !value.minutes.every(minute)) return null;
  const seen = new Set<string>(), perShop = new Map<string, number>();
  for (const item of value.minutes) {
    const key = `${item.shop_id}:${item.bucket_index}`;
    const count = (perShop.get(item.shop_id) ?? 0) + 1;
    if (seen.has(key) || count > 60 || !value.shops.some((entry) => entry.shop_id === item.shop_id)) return null;
    seen.add(key); perShop.set(item.shop_id, count);
  }
  return value as unknown as LiveUpdate;
}

export function acceptLiveUpdate(previous: LiveUpdate | null, next: LiveUpdate, jobId: string, sessionId: string): boolean {
  return next.job_id === jobId && next.session_id === sessionId &&
    (previous === null || (next.revision > previous.revision && next.capture_sequence >= previous.capture_sequence));
}

export class ClockCalibration {
  private pending = new Map<string, number>();
  private best: { offset: number; roundTrip: number } | null = null;
  get pending_count(): number { return this.pending.size; }
  sent(nonce: string, clientTime: number): void {
    if (!identifier(nonce) || !finite(clientTime)) return;
    this.pending.set(nonce, clientTime);
    while (this.pending.size > 8) {
      const oldest = this.pending.keys().next().value;
      if (oldest === undefined) break;
      this.pending.delete(oldest);
    }
  }
  received(pong: ClockPong, receivedAt: number): void {
    const sentAt = this.pending.get(pong.nonce);
    this.pending.delete(pong.nonce);
    if (sentAt === undefined || sentAt !== pong.client_sent_ms || !finite(receivedAt) || parseLiveMessage(pong) === null) return;
    const roundTrip = receivedAt - sentAt;
    const serverDuration = pong.server_sent_monotonic_ms - pong.server_received_monotonic_ms;
    if (roundTrip < serverDuration || roundTrip < 0) return;
    const offset = ((pong.server_received_monotonic_ms - sentAt) + (pong.server_sent_monotonic_ms - receivedAt)) / 2;
    if (this.best === null || roundTrip < this.best.roundTrip) this.best = { offset, roundTrip };
  }
  age(capturedAt: number, clientNow: number): { estimated_ms: number; uncertainty_ms: number; upper_bound_ms: number } | null {
    if (this.best === null || !finite(capturedAt) || !finite(clientNow)) return null;
    const age = clientNow + this.best.offset - capturedAt;
    if (age < 0) return null;
    const uncertainty = this.best.roundTrip / 2;
    return { estimated_ms: age, uncertainty_ms: uncertainty, upper_bound_ms: age + uncertainty };
  }
}
