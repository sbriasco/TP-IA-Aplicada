import { requestJson } from "./http";

export interface MetricValue {
  code: string;
  availability: string;
  value: number | null;
  label: string;
  unavailable_reason: string | null;
}

export interface TrafficBucket {
  bucket_index: number;
  start_seconds: number;
  track_count: number;
}

export interface ShopMetrics {
  session_id: string;
  shop_id: string;
  metrics: MetricValue[];
  flow: TrafficBucket[];
  peak: TrafficBucket;
}

export interface SceneEvent {
  kind: string;
  zone_role: string | null;
  track_id: number;
  shop_id: string;
  video_timestamp_seconds: number;
  duration_seconds: number | null;
}

export interface AnalysisMeasure {
  shop_id: string;
  shop_name: string;
  code: string;
  value: number | null;
  availability: string;
  partial: boolean;
}

export interface SceneShop {
  shop_id: string;
  name: string;
}

export interface PositionSamples {
  job_id: string;
  availability: "available" | "unavailable";
  samples: { video_timestamp_seconds: number; foot: [number, number] }[];
}

export function getShopMetrics(
  apiBaseUrl: string,
  sessionId: string,
  shopId: string,
): Promise<ShopMetrics> {
  return requestJson<ShopMetrics>(
    `${apiBaseUrl}/sessions/${encodeURIComponent(sessionId)}/shops/${encodeURIComponent(shopId)}/metrics`,
  );
}

export function getSessionEvents(
  apiBaseUrl: string,
  sessionId: string,
  shopId: string,
  fromSeconds: number,
  toSeconds: number,
): Promise<SceneEvent[]> {
  const url = new URL(`${apiBaseUrl}/sessions/${encodeURIComponent(sessionId)}/events`);
  url.searchParams.set("shop_id", shopId);
  url.searchParams.set("from_seconds", String(fromSeconds));
  url.searchParams.set("to_seconds", String(toSeconds));
  return requestJson<SceneEvent[]>(url.toString());
}

export function getJobMeasures(apiBaseUrl: string, jobId: string): Promise<AnalysisMeasure[]> {
  return requestJson<AnalysisMeasure[]>(`${apiBaseUrl}/jobs/${encodeURIComponent(jobId)}/measures`);
}

export function getSceneShops(apiBaseUrl: string, sceneVersionId: string): Promise<SceneShop[]> {
  return requestJson<{ shops: SceneShop[] }>(
    `${apiBaseUrl}/scene-versions/${encodeURIComponent(sceneVersionId)}`,
  ).then((version) => version.shops);
}

export function getPositionSamples(apiBaseUrl: string, jobId: string): Promise<PositionSamples> {
  return requestJson<PositionSamples>(
    `${apiBaseUrl}/jobs/${encodeURIComponent(jobId)}/position-samples`,
  );
}
