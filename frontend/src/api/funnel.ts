import { ApiRequestError, requestJson } from "./http";

export interface FunnelStage {
  stage: string;
  count: number | null;
  availability: string;
  label: string;
  unavailable_reason: string | null;
}

export interface FunnelRate {
  code: string;
  value: string | null;
  availability: string;
  unavailable_reason: string | null;
}

export interface ShopFunnel {
  session_id: string;
  shop_id: string;
  stop_threshold_seconds: string;
  attention_threshold_seconds: string;
  excluded_window_only: number;
  precision_uncommitted: true;
  stages: FunnelStage[];
  rates: FunnelRate[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFunnel(value: unknown): value is ShopFunnel {
  if (!isRecord(value) || !Array.isArray(value.stages) || !Array.isArray(value.rates)) return false;
  return value.precision_uncommitted === true && value.stages.length === 5 && value.rates.length === 4;
}

export async function getShopFunnel(
  apiBaseUrl: string,
  sessionId: string,
  shopId: string,
): Promise<ShopFunnel> {
  const body = await requestJson<unknown>(
    `${apiBaseUrl}/sessions/${sessionId}/shops/${shopId}/funnel`,
  );
  if (!isFunnel(body)) {
    throw new ApiRequestError({
      status: 200,
      code: "unexpected_response",
      message: "La API respondió con un funnel inesperado.",
      extra: {},
    });
  }
  return body;
}
