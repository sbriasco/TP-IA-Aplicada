import { ApiRequestError, requestJson } from "./http";

export type ComparisonAxis = "session" | "day" | "time_of_day" | "zone";

export interface ComparisonRequest {
  session_ids: string[];
  zone_name: string;
  axis: ComparisonAxis;
}

export interface ComparisonCell {
  availability: "available" | "unavailable";
  value: number | null;
  unavailable_reason: string | null;
  start_seconds?: number | null;
}

export interface ComparableColumn {
  key: string;
  label: string;
  session_ids: string[];
  camera_label: string | null;
  resolved_shop_id: string | null;
}

export interface ContrastedFigure {
  family: "shop_metrics" | "peak" | "funnel" | "visit_patterns" | "possible_purchase";
  code: string;
  label: string;
  cells: ComparisonCell[];
  relation: "greater" | "less" | "equal" | "unavailable";
  delta: number | null;
}

export interface DerivedInsight {
  code: string;
  message: string;
  figure_code: string | null;
  estimation: boolean;
}

export interface ComparisonResponse {
  axis: ComparisonAxis;
  zone_name: string;
  columns: ComparableColumn[];
  figures: ContrastedFigure[];
  insights: DerivedInsight[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isComparisonResponse(value: unknown): value is ComparisonResponse {
  if (!isRecord(value)) return false;
  return (
    typeof value.axis === "string" &&
    typeof value.zone_name === "string" &&
    Array.isArray(value.columns) &&
    Array.isArray(value.figures) &&
    Array.isArray(value.insights)
  );
}

export async function createComparison(
  apiBaseUrl: string,
  request: ComparisonRequest,
): Promise<ComparisonResponse> {
  const body = await requestJson<unknown>(`${apiBaseUrl}/comparisons`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!isComparisonResponse(body)) {
    throw new ApiRequestError({
      status: 200,
      code: "unexpected_response",
      message: "La API respondió con una comparación inesperada.",
      extra: {},
    });
  }
  return body;
}
