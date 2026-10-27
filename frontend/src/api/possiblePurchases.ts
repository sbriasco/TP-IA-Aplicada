import { ApiRequestError, requestJson } from "./http";

export interface PossiblePurchases {
  availability: "available";
  visit_count: number;
  minimum_seconds: string;
  precision_uncommitted: true;
  track_ids: number[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isPossiblePurchases(value: unknown): value is PossiblePurchases {
  if (!isRecord(value)) return false;
  return (
    value.availability === "available" &&
    typeof value.visit_count === "number" &&
    typeof value.minimum_seconds === "string" &&
    value.precision_uncommitted === true &&
    Array.isArray(value.track_ids)
  );
}

export async function getPossiblePurchases(
  apiBaseUrl: string,
  sessionId: string,
): Promise<PossiblePurchases> {
  const body = await requestJson<unknown>(`${apiBaseUrl}/sessions/${sessionId}/possible-purchases`);
  if (!isPossiblePurchases(body)) {
    throw new ApiRequestError({
      status: 200,
      code: "unexpected_response",
      message: "La API respondió con una posible compra estimada inesperada.",
      extra: {},
    });
  }
  return body;
}
