import { locale } from '../quizzes/i18n';
let csrfToken = "";
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fields: Record<string, string[] | string> = {},
    public code = "",
  ) {
    super(message);
  }
}
export async function csrf() {
  const r = await fetch("/api/csrf/", { credentials: "same-origin" });
  const data = await r.json();
  csrfToken = data.csrfToken;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  if (method !== "GET" && !csrfToken) await csrf();
  const headers: Record<string, string> = {};
  if (method !== "GET") headers["X-CSRFToken"] = csrfToken;
  if (body && !(body instanceof FormData))
    headers["Content-Type"] = "application/json";
  let response: Response;
  try {
    response = await fetch("/api/" + path, {
      method,
      credentials: "same-origin",
      headers,
      body:
        body instanceof FormData
          ? body
          : body
            ? JSON.stringify(body)
            : undefined,
    });
  } catch {
    throw new ApiError(
      0,
      "Le serveur est injoignable. Vérifiez votre connexion puis réessayez.",
    );
  }
  const data =
    response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401)
      window.dispatchEvent(new Event("session-expired"));
    throw new ApiError(
      response.status,
      data?.error?.message || "La demande a échoué.",
      data?.error?.fields || {},
      data?.error?.code || "",
    );
  }
  if (data?.csrfToken) csrfToken = data.csrfToken;
  return data as T;
}
export const date = (value: string) =>
  new Intl.DateTimeFormat(locale(), {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Africa/Tunis",
  }).format(new Date(value));
export function localDateTime(value: string) {
  const d = new Date(value);
  return new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Africa/Tunis",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
    .format(d)
    .replace(" ", "T");
}
// Tunis currently uses UTC+01 year round. API accepts explicit offsets; browser zone is irrelevant.
export const iso = (value: string) =>
  new Date(value + ":00+01:00").toISOString();
export const query = (values: Record<string, string | number>) =>
  new URLSearchParams(
    Object.entries(values)
      .filter(([, v]) => v !== "")
      .map(([k, v]) => [k, String(v)]),
  ).toString();
export async function allPages<T>(path: string): Promise<T[]> {
  let page = 1,
    result: T[] = [];
  for (;;) {
    const data = await api<import("./types").Page<T>>(
      path + (path.includes("?") ? "&" : "?") + "page=" + page,
    );
    result.push(...data.results);
    if (result.length >= data.count) return result;
    page++;
  }
}
