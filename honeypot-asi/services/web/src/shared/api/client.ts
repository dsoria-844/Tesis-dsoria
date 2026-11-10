import { session } from "./session";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init: Omit<RequestInit, "body"> & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (session.token) headers.set("Authorization", `Bearer ${session.token}`);
  let body: string | undefined;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const r = await fetch(`/api/v1${path}`, { ...init, headers, body });
  if (r.status === 401 && !path.startsWith("/auth/login")) {
    session.clear();
    window.dispatchEvent(new Event("hp:logout"));
  }
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* sin cuerpo JSON */
    }
    throw new ApiError(r.status, msg);
  }
  return (await r.json()) as T;
}
