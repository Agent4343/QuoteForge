import { ApiError } from "../api/client";

interface FastApiValidationItem {
  loc?: (string | number)[];
  msg?: string;
}

/** Turn any thrown error into a readable, user-facing message. Handles FastAPI's
 * 422 validation shape (a list of {loc, msg}) and plain string details. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    const d = e.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return (d as FastApiValidationItem[])
        .map((item) => {
          const field = item.loc?.[item.loc.length - 1];
          return field && field !== "body" ? `${field}: ${item.msg ?? "invalid"}` : item.msg ?? "invalid";
        })
        .join("; ");
    }
    if (d && typeof d === "object" && "msg" in d) return String((d as { msg: unknown }).msg);
    return `Request failed (${e.status})`;
  }
  return "Something went wrong — please try again.";
}
