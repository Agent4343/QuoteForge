import { useAuth } from "../stores/auth";
import type { TokenResponse } from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

async function rawFetch(path: string, method: Method, body?: unknown, auth = true): Promise<Response> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = useAuth.getState().accessToken;
  if (auth && token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

async function tryRefresh(): Promise<boolean> {
  const refresh = useAuth.getState().refreshToken;
  if (!refresh) return false;
  const res = await rawFetch("/api/auth/refresh", "POST", { refresh_token: refresh }, false);
  if (!res.ok) {
    useAuth.getState().logout();
    return false;
  }
  const tokens = (await res.json()) as TokenResponse;
  useAuth.getState().setTokens(tokens);
  return true;
}

async function request<T>(path: string, method: Method, body?: unknown, auth = true): Promise<T> {
  let res = await rawFetch(path, method, body, auth);
  if (res.status === 401 && auth) {
    if (await tryRefresh()) res = await rawFetch(path, method, body, auth);
  }
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, "GET"),
  post: <T>(path: string, body?: unknown, auth = true) => request<T>(path, "POST", body, auth),
  patch: <T>(path: string, body?: unknown) => request<T>(path, "PATCH", body),
  del: <T>(path: string) => request<T>(path, "DELETE"),
};

/** Fetch a PDF as an object URL (for in-browser preview). */
export async function fetchPdf(path: string): Promise<string> {
  let res = await rawFetch(path, "GET");
  if (res.status === 401 && (await tryRefresh())) res = await rawFetch(path, "GET");
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return URL.createObjectURL(await res.blob());
}
