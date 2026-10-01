import { requestJson } from "./http";

export interface ChatFigure {
  code: string;
  label: string;
  availability: string;
  value: number | null;
  unavailable_reason: string | null;
  start_seconds?: number | null;
  track_count?: number | null;
}

export interface ChatResponse {
  status: "answered" | "refused" | "needs_clarification" | "unavailable" | "error";
  message: string;
  session_id: string | null;
  shop_id: string | null;
  shop_name: string | null;
  scope: "whole_session" | null;
  figures: ChatFigure[];
  model_calls: number;
}

export function postChat(
  apiBaseUrl: string,
  question: string,
  sessionId: string,
  shopId: string | null,
): Promise<ChatResponse> {
  return requestJson<ChatResponse>(`${apiBaseUrl}/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      question,
      session_id: sessionId,
      shop_id: shopId,
    }),
  });
}
