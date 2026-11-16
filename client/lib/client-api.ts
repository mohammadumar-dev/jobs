"use client";

/**
 * Browser-side calls to our own origin (/api/* is forwarded to Spring Boot).
 * Auth is a server-side session in an HttpOnly cookie: this file never sees,
 * stores or sends a token. The only cookie JavaScript reads is XSRF-TOKEN,
 * which exists to be echoed back in the X-XSRF-TOKEN header.
 */

function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  for (const part of document.cookie.split("; ")) {
    if (part.startsWith(prefix)) return decodeURIComponent(part.slice(prefix.length));
  }
  return null;
}

async function csrfToken(): Promise<string> {
  let token = readCookie("XSRF-TOKEN");
  if (!token) {
    // The token is rotated on login/logout; this asks the API to set a fresh one.
    await fetch("/api/csrf", { credentials: "same-origin" });
    token = readCookie("XSRF-TOKEN");
  }
  return token ?? "";
}

export class HttpError extends Error {
  constructor(
    public status: number,
    public detail: string | null,
  ) {
    super(detail ?? `Request failed (${status})`);
  }
}

async function parse<T>(response: Response): Promise<T> {
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) throw new HttpError(response.status, body?.detail ?? null);
  return body as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return parse<T>(
    await fetch(path, { credentials: "same-origin", headers: { Accept: "application/json" } }),
  );
}

export async function apiSend<T>(
  method: "POST" | "DELETE",
  path: string,
  body?: unknown,
  options: { keepalive?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-XSRF-TOKEN": await csrfToken(),
  };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  return parse<T>(
    await fetch(path, {
      method,
      credentials: "same-origin",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      keepalive: options.keepalive,
    }),
  );
}
