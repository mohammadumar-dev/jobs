import { NextRequest, NextResponse } from "next/server";

const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8080";
const PROXY_SECRET = process.env.PROXY_SECRET ?? "";

const API_PREFIXES = ["/api/", "/oauth2/", "/login/oauth2/"];

/** Real client address as reported by the hosting edge (Vercel sets both headers). */
function clientIp(request: NextRequest): string | null {
  const real = request.headers.get("x-real-ip");
  if (real) return real.trim();
  const forwarded = request.headers.get("x-forwarded-for");
  return forwarded ? forwarded.split(",")[0].trim() : null;
}

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  // 1. Same-origin API: the browser only ever talks to this origin, so the
  //    session and CSRF cookies are first-party. Forward to Spring Boot.
  if (API_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    const headers = new Headers(request.headers);
    // Never let a browser supply these two itself.
    headers.delete("x-proxy-secret");
    headers.delete("x-client-ip");
    const ip = clientIp(request);
    if (PROXY_SECRET && ip) {
      headers.set("x-proxy-secret", PROXY_SECRET);
      headers.set("x-client-ip", ip);
    }
    return NextResponse.rewrite(new URL(pathname + search, API_ORIGIN), {
      request: { headers },
    });
  }

  // 2. Pages: strict CSP with a per-request nonce. No inline script runs
  //    without it; Next.js adds the nonce to its own scripts automatically.
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const isDev = process.env.NODE_ENV === "development";
  const isHttps =
    (request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.replace(":", "")) === "https";
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    `style-src-elem 'self' 'nonce-${nonce}'${isDev ? " 'unsafe-inline'" : ""}`,
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    `connect-src 'self'${isDev ? " ws: wss:" : ""}`,
    // The /loom page embeds the walkthrough video from Loom; no other frames.
    "frame-src https://www.loom.com",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    ...(isHttps ? ["upgrade-insecure-requests"] : []),
  ].join("; ");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("X-Frame-Options", "DENY");
  if (isHttps) {
    response.headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  }
  return response;
}

export const config = {
  matcher: [
    // API paths are always proxied, prefetch or not.
    "/api/:path*",
    "/oauth2/:path*",
    "/login/oauth2/:path*",
    {
      source: "/((?!_next/static|_next/image|favicon.ico|icon.svg).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
