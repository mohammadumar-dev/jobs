import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    agentFeedback: true,
  },
  // Cache Components / Partial Prerendering are OFF on purpose: the strict,
  // nonce-based Content-Security-Policy set in proxy.ts needs every page to be
  // rendered per request (a prerendered shell cannot carry a per-request nonce).
  cacheComponents: false,
  poweredByHeader: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // /api/*, /oauth2/* and /login/oauth2/* are forwarded to the Spring Boot API
  // by proxy.ts (not by `rewrites` here) so the forwarded request can carry the
  // shared proxy secret and the real client IP.
};

export default nextConfig;
