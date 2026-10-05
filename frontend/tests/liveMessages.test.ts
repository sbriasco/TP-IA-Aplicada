import { expect, it } from "vitest";
import { ClockCalibration, acceptLiveUpdate, parseLiveMessage } from "../src/api/liveMessages";

function message(revision = 1, sequence = 1) {
  return { type: "live.update", schema_version: "3", source_kind: "webcam",
    job_id: "job-1", session_id: "session-1", revision, capture_sequence: sequence,
    segment_index: 0, capture_status: "connected", capture_timestamp_seconds: 1,
    captured_monotonic_ms: 1000, published_monotonic_ms: 1100,
    image_media_type: "image/jpeg", image_base64: "eA==", partial: true,
    capture_fps: 30, analysis_fps: 10, capture_to_publish_ms: 100,
    shops: [{ shop_id: "shop-1", shop_name: "Paso", entry_count: 2, exit_count: 1,
      a_to_b_count: 2, b_to_a_count: 1, total_crossings: 3, label_mode: "directions", partial: true,
      entry_direction: "a_to_b" }], minutes: [], coverage_complete: true,
    checkpoint_revision: 0, checkpoint_at: null };
}

it("valida la comprobación neutral sin aceptar métricas ni TTL o dimensiones inválidos", () => {
  const neutral = { type: "live.reconnect-check", schema_version: "3", source_kind: "webcam",
    job_id: "job-1", session_id: "session-1", revision: 2, segment_index: 1,
    capture_status: "awaiting_confirmation", device_index: 0, width: 320, height: 180,
    backend: "dshow", image_media_type: "image/jpeg", image_base64: "eA==",
    check_token: "fresh", expires_in_seconds: 60 };
  expect(parseLiveMessage(neutral)?.type).toBe("live.reconnect-check");
  expect(parseLiveMessage({ ...neutral, shops: [] })).toBeNull();
  expect(parseLiveMessage({ ...neutral, expires_in_seconds: 61 })).toBeNull();
  expect(parseLiveMessage({ ...neutral, width: 1921 })).toBeNull();
  expect(parseLiveMessage({ ...neutral, check_token: "" })).toBeNull();
});

it("acepta una revisión nueva del mismo frame sin sumar deltas", () => {
  const first = parseLiveMessage(message(2, 5));
  const next = parseLiveMessage(message(3, 5));
  expect(first?.type).toBe("live.update"); expect(next?.type).toBe("live.update");
  if (first?.type !== "live.update" || next?.type !== "live.update") throw new Error("fixture");
  expect(acceptLiveUpdate(first, next, "job-1", "session-1")).toBe(true);
  expect(next.shops[0].total_crossings).toBe(3);
  expect(acceptLiveUpdate(next, first, "job-1", "session-1")).toBe(false);
  expect(acceptLiveUpdate(null, next, "other-job", "session-1")).toBe(false);
  const backward = parseLiveMessage(message(4, 4));
  if (backward?.type !== "live.update") throw new Error("fixture");
  expect(acceptLiveUpdate(next, backward, "job-1", "session-1")).toBe(false);
});

it("rechaza NaN, cifras incompatibles, imágenes excesivas y métricas sin su frame", () => {
  expect(parseLiveMessage({ ...message(), capture_timestamp_seconds: Number.NaN })).toBeNull();
  expect(parseLiveMessage({ ...message(), image_base64: "x".repeat(300000) })).toBeNull();
  expect(parseLiveMessage({ ...message(), image_base64: undefined })).toBeNull();
  const badCounts = message(); badCounts.shops[0].total_crossings = 4;
  expect(parseLiveMessage(badCounts)).toBeNull();
});

it("lee los buckets del contrato backend sin cambiar su cobertura", () => {
  const value = { ...message(), minutes: [{ shop_id: "shop-1", bucket_index: 0,
    start_seconds: 0, end_seconds: 1, entries: 2, exits: 1, observed_seconds: 0.8,
    missing_seconds: 0.2, pending_count: 0, is_open: true,
    coverage_incomplete: true, unknown_tail: false, revision: 1 }] };
  const parsed = parseLiveMessage(value);
  expect(parsed?.type).toBe("live.update");
  if (parsed?.type !== "live.update") throw new Error("fixture");
  expect(parsed.minutes[0]).toMatchObject({ bucket_index: 0, coverage_incomplete: true });
});

it("calibra épocas diferentes con el menor RTT y no fabrica latencia sin calibración", () => {
  const clock = new ClockCalibration();
  expect(clock.age(100, 50)).toBeNull();
  clock.sent("one", 100);
  clock.received({ type: "clock.pong", nonce: "one", client_sent_ms: 100,
    server_received_monotonic_ms: 1105, server_sent_monotonic_ms: 1105 }, 110);
  expect(clock.age(1090, 100)).toEqual({ estimated_ms: 10, uncertainty_ms: 5, upper_bound_ms: 15 });
  clock.sent("slow", 120);
  clock.received({ type: "clock.pong", nonce: "slow", client_sent_ms: 120,
    server_received_monotonic_ms: 1150, server_sent_monotonic_ms: 1150 }, 180);
  expect(clock.age(1090, 100)?.uncertainty_ms).toBe(5);
  expect(clock.age(2000, 100)).toBeNull();
});

it("ignora respuestas de reloj no solicitadas y mantiene ocho pings como máximo", () => {
  const clock = new ClockCalibration();
  clock.received({ type: "clock.pong", nonce: "unknown", client_sent_ms: 100,
    server_received_monotonic_ms: 1000, server_sent_monotonic_ms: 1001 }, 110);
  expect(clock.age(100, 100)).toBeNull();
  for (let index = 0; index < 100; index++) clock.sent(String(index), index);
  expect(clock.pending_count).toBeLessThanOrEqual(8);
});
