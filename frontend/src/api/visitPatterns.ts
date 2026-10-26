import { ApiRequestError, requestJson } from "./http";

export interface AreaRef {
  shop_id: string;
  zone_role: "front" | "interior" | "window";
}

export interface AreaTransition {
  from_shop_id: string;
  from_zone_role: AreaRef["zone_role"];
  to_shop_id: string;
  to_zone_role: AreaRef["zone_role"];
  track_count: number;
}

export interface VisitSequence {
  areas: AreaRef[];
  track_count: number;
}

export interface ShopTransition {
  from_shop_id: string;
  to_shop_id: string;
  track_count: number;
}

export interface VisitGroup {
  ordinal: number;
  started_video_timestamp_seconds: string;
  ended_video_timestamp_seconds: string;
  label: "group_estimate";
  track_ids: number[];
}

export interface VisitPatterns {
  patterns_availability: "available" | "unavailable";
  patterns_unavailable_reason: "no_areas" | null;
  groups_availability: "available" | "unavailable";
  group_count: number;
  proximity_width_fraction: string;
  direction_degrees: string;
  minimum_seconds: string;
  area_transitions: AreaTransition[];
  sequences: VisitSequence[];
  shop_transitions: ShopTransition[];
  groups: VisitGroup[];
  precision_uncommitted: true;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isVisitPatterns(value: unknown): value is VisitPatterns {
  if (!isRecord(value)) return false;
  const availability = value.patterns_availability === "available" || value.patterns_availability === "unavailable";
  const groups = value.groups_availability === "available" || value.groups_availability === "unavailable";
  return (
    availability &&
    groups &&
    typeof value.group_count === "number" &&
    typeof value.proximity_width_fraction === "string" &&
    typeof value.direction_degrees === "string" &&
    typeof value.minimum_seconds === "string" &&
    Array.isArray(value.area_transitions) &&
    Array.isArray(value.sequences) &&
    Array.isArray(value.shop_transitions) &&
    Array.isArray(value.groups) &&
    value.precision_uncommitted === true
  );
}

export async function getVisitPatterns(apiBaseUrl: string, sessionId: string): Promise<VisitPatterns> {
  const body = await requestJson<unknown>(`${apiBaseUrl}/sessions/${sessionId}/visit-patterns`);
  if (!isVisitPatterns(body)) {
    throw new ApiRequestError({
      status: 200,
      code: "unexpected_response",
      message: "La API respondió con patrones de visita inesperados.",
      extra: {},
    });
  }
  return body;
}
