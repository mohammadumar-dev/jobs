import "server-only";
import { headers } from "next/headers";
import type { JobDetail, JobFilters, JobPage, Meta, RunHistory, TaggingStats } from "./types";

const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8080";
const PROXY_SECRET = process.env.PROXY_SECRET ?? "";

export class ApiError extends Error {
  constructor(public status: number) {
    super(`API responded ${status}`);
  }
}

/**
 * Server-side read of the public API. No cookies are forwarded: these pages
 * only show public data. The visitor's IP is passed along (with the proxy
 * secret) so the API rate-limits the visitor, not this server.
 */
async function apiGet<T>(path: string): Promise<T> {
  const incoming = await headers();
  const outgoing: Record<string, string> = { Accept: "application/json" };
  const ip =
    incoming.get("x-real-ip") ?? incoming.get("x-forwarded-for")?.split(",")[0].trim();
  if (PROXY_SECRET && ip) {
    outgoing["x-proxy-secret"] = PROXY_SECRET;
    outgoing["x-client-ip"] = ip;
  }
  const response = await fetch(`${API_ORIGIN}${path}`, { headers: outgoing, cache: "no-store" });
  if (!response.ok) throw new ApiError(response.status);
  return (await response.json()) as T;
}

const FILTER_KEYS = ["q", "role", "city", "mode", "type", "exp", "page"] as const;

export function toQuery(filters: JobFilters): string {
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const value = filters[key]?.trim();
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export const getMeta = () => apiGet<Meta>("/api/meta");
export const getTaggingStats = () => apiGet<TaggingStats>("/api/meta/tagging");
export const getRunHistory = () => apiGet<RunHistory>("/api/meta/runs");
export const searchJobs = (filters: JobFilters) => apiGet<JobPage>(`/api/jobs${toQuery(filters)}`);
export const getJob = (id: string) => apiGet<JobDetail>(`/api/jobs/${encodeURIComponent(id)}`);
