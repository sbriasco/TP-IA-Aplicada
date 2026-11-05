import { requestJson } from "./http";

export interface ChatFigure {
  code: string;
  label: string;
  availability: string;
  value: number | null;
  unavailable_reason: string | null;
  start_seconds?: number | null;
  track_count?: number | null;
  estimation?: boolean;
}

export interface ChatComparisonSummary {
  axis: "session" | "day" | "time_of_day" | "zone";
  column_labels: string[];
  insight_codes: string[];
}

export interface ChatResponse {
  status: "answered" | "refused" | "needs_clarification" | "unavailable" | "error";
  message: string;
  session_id: string | null;
  shop_id: string | null;
  shop_name: string | null;
  scope: "whole_session" | "comparison" | null;
  figures: ChatFigure[];
  comparison?: ChatComparisonSummary | null;
  model_calls: number;
  thread_id?: string | null;
}

export interface ChatThreadSummary {
  id: string;
  session_id: string;
  shop_id: string | null;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatThreadMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  answer: ChatResponse | null;
}

export interface ChatThreadDetail {
  thread: ChatThreadSummary;
  messages: ChatThreadMessage[];
}

export function postChat(
  apiBaseUrl: string,
  question: string,
  sessionId: string,
  shopId: string | null,
  threadId?: string | null,
): Promise<ChatResponse> {
  return requestJson<ChatResponse>(`${apiBaseUrl}/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      question,
      session_id: sessionId,
      shop_id: shopId,
      ...(threadId ? { thread_id: threadId } : {}),
    }),
  });
}

export function listChatThreads(
  apiBaseUrl: string,
  sessionId: string,
): Promise<ChatThreadSummary[]> {
  return requestJson<ChatThreadSummary[]>(
    `${apiBaseUrl}/sessions/${sessionId}/chat-threads`,
  );
}

export function getChatThread(
  apiBaseUrl: string,
  threadId: string,
): Promise<ChatThreadDetail> {
  return requestJson<ChatThreadDetail>(`${apiBaseUrl}/chat-threads/${threadId}`);
}
