import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./client";
import { session } from "./session";

const resp = (status: number, body?: unknown, statusText = "") =>
  new Response(body === undefined ? null : JSON.stringify(body), { status, statusText });

const rejected = (p: Promise<unknown>) =>
  p.then(
    () => {
      throw new Error("expected the request to reject");
    },
    (e: ApiError) => e,
  );

let fetchMock: ReturnType<typeof vi.fn>;
let onLogout: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  onLogout = vi.fn();
  window.addEventListener("hp:logout", onLogout);
});
afterEach(() => {
  window.removeEventListener("hp:logout", onLogout);
  vi.unstubAllGlobals();
});

const lastInit = () => fetchMock.mock.calls[0][1] as RequestInit & { headers: Headers };

describe("api client", () => {
  it("prefixes /api/v1 and sends the Bearer token from the session", async () => {
    session.set("tok123");
    fetchMock.mockResolvedValue(resp(200, { ok: true }));
    await expect(api("/auth/me")).resolves.toEqual({ ok: true });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/auth/me");
    expect(lastInit().headers.get("Authorization")).toBe("Bearer tok123");
  });

  it("sends no Authorization header without a session", async () => {
    fetchMock.mockResolvedValue(resp(200, {}));
    await api("/x");
    expect(lastInit().headers.has("Authorization")).toBe(false);
  });

  it("serialises json bodies with a JSON content type", async () => {
    fetchMock.mockResolvedValue(resp(200, {}));
    await api("/x", { method: "POST", json: { a: 1 } });
    expect(lastInit().body).toBe('{"a":1}');
    expect(lastInit().headers.get("Content-Type")).toBe("application/json");
  });

  it("turns a string detail into an ApiError message", async () => {
    fetchMock.mockResolvedValue(resp(400, { detail: "Algo salió mal" }));
    const err = await rejected(api("/x"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.message).toBe("Algo salió mal");
  });

  it("stringifies a non-string detail (validation errors)", async () => {
    const detail = [{ loc: ["body", "correo"], msg: "inválido" }];
    fetchMock.mockResolvedValue(resp(422, { detail }));
    const err = await rejected(api("/x"));
    expect(err.message).toBe(JSON.stringify(detail));
  });

  it("falls back to statusText when the body is not JSON", async () => {
    fetchMock.mockResolvedValue(new Response("<html>", { status: 502, statusText: "Bad Gateway" }));
    const err = await rejected(api("/x"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(502);
    expect(err.message).toBe("Bad Gateway");
  });

  it("on 401 clears the session and dispatches hp:logout", async () => {
    session.set("tok");
    fetchMock.mockResolvedValue(resp(401, { detail: "Token inválido" }));
    const err = await rejected(api("/alertas"));
    expect(err.status).toBe(401);
    expect(session.token).toBeNull();
    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  it("on 401 from /auth/login keeps the session and does not dispatch hp:logout", async () => {
    session.set("tok");
    fetchMock.mockResolvedValue(resp(401, { detail: "Credenciales inválidas" }));
    const err = await rejected(api("/auth/login", { method: "POST", json: {} }));
    expect(err.message).toBe("Credenciales inválidas");
    expect(session.token).toBe("tok");
    expect(onLogout).not.toHaveBeenCalled();
  });
});
