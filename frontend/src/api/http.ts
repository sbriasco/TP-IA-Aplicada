import type { ApiError } from "../types/session";

export class ApiRequestError extends Error {
  readonly error: ApiError;

  constructor(error: ApiError) {
    super(error.message);
    this.name = "ApiRequestError";
    this.error = error;
  }
}

export const NETWORK_ERROR: Omit<ApiError, "extra"> = {
  status: 0,
  code: "api_unavailable",
  message: "No se pudo conectar con la API. Verificá que esté en ejecución.",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Traduce el cuerpo de un error de la API a `ApiError`. Acepta
 * `{"detail": {code, message, ...}}` (errores HTTP) y `{code, message}` (422 de validación).
 */
export function parseApiError(status: number, body: unknown): ApiError {
  const payload = isRecord(body) && isRecord(body.detail) ? body.detail : body;
  if (isRecord(payload) && typeof payload.code === "string" && typeof payload.message === "string") {
    const { code, message, ...extra } = payload;
    return { status, code, message, extra };
  }
  return {
    status,
    code: "unexpected_response",
    message: `La API respondió con un error inesperado (HTTP ${status}).`,
    extra: {},
  };
}

export function parseJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return undefined;
  }
}

export async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new ApiRequestError({ ...NETWORK_ERROR, extra: {} });
  }
  const body = parseJson(await response.text());
  if (!response.ok) {
    throw new ApiRequestError(parseApiError(response.status, body));
  }
  return body as T;
}
