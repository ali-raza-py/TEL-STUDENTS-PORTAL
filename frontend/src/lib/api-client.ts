import type { ApiErrorBody } from "./types";

/**
 * The single place the browser talks to the API.
 *
 * Cookies are `HttpOnly` and therefore never touched by JavaScript. Unsafe
 * requests echo the CSRF cookie in a header, which the backend verifies with
 * Django's own CSRF machinery. Every failure is normalised into `ApiError` so
 * pages can render one consistent error state.
 */

const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly traceId: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {},
    traceId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.traceId = traceId;
  }

  get isAuth(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  /** Field level messages for inline form errors. */
  get fieldErrors(): Record<string, string[]> {
    const out: Record<string, string[]> = {};
    for (const [key, value] of Object.entries(this.details)) {
      if (Array.isArray(value)) out[key] = value.map(String);
    }
    return out;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(
    new RegExp(`(?:^|;\\s*)${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}=([^;]*)`),
  );
  return match ? decodeURIComponent(match[1]) : null;
}

export async function primeCsrfCookie(): Promise<void> {
  if (typeof document === "undefined") return;
  if (readCookie("tel_csrftoken")) return;
  try {
    await fetch(`${BASE}/api/auth/csrf/`, { credentials: "include" });
  } catch {
    // A failure here surfaces on the first real request with a clear message.
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  query?: Record<string, string | number | boolean | null | undefined>;
  formData?: FormData;
}

export function buildQuery(
  query: RequestOptions["query"] = {},
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === "") continue;
    params.set(key, String(value));
  }
  const serialised = params.toString();
  return serialised ? `?${serialised}` : "";
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal, query, formData } = options;
  const url = `${BASE}${path}${buildQuery(query)}`;

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  if (method !== "GET") {
    if (!readCookie("tel_csrftoken")) await primeCsrfCookie();
    const token = readCookie("tel_csrftoken");
    if (token) headers["X-TEL-CSRFToken"] = token;
  }

  const init: RequestInit = {
    method,
    headers,
    credentials: "include",
    cache: "no-store",
    signal,
  };
  if (formData) init.body = formData;
  else if (body !== undefined) init.body = JSON.stringify(body);

  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (cause) {
    if ((cause as Error)?.name === "AbortError") throw cause;
    throw new ApiError(
      0,
      "network_error",
      "We could not reach the TEL portal service. Check your connection and try again.",
    );
  }

  if (response.status === 204) return undefined as T;

  const raw = await response.text();
  let payload: unknown = null;
  if (raw) {
    try {
      payload = JSON.parse(raw);
    } catch {
      payload = { raw };
    }
  }

  if (!response.ok) {
    const body = payload as ApiErrorBody | null;
    const error = body?.error;
    const isProxyOrGatewayFailure =
      !error && (response.status === 502 || response.status === 503 || response.status === 504);
    throw new ApiError(
      response.status,
      error?.code ?? (isProxyOrGatewayFailure ? "service_unavailable" : "server_error"),
      error?.message ??
        (isProxyOrGatewayFailure
          ? "The TEL portal service is unavailable. Please try again in a moment."
          : "Something went wrong. Please try again."),
      error?.details ?? {},
      error?.trace_id ?? null,
    );
  }

  return payload as T;
}

export const api = {
  get: <T>(path: string, options: Omit<RequestOptions, "method" | "body"> = {}) =>
    apiFetch<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options: Omit<RequestOptions, "method" | "body"> = {}) =>
    apiFetch<T>(path, { ...options, method: "POST", body }),
  patch: <T>(path: string, body?: unknown, options: Omit<RequestOptions, "method" | "body"> = {}) =>
    apiFetch<T>(path, { ...options, method: "PATCH", body }),
  postForm: <T>(path: string, formData: FormData, options: Omit<RequestOptions, "method" | "body" | "formData"> = {}) =>
    apiFetch<T>(path, { ...options, method: "POST", formData }),
};
