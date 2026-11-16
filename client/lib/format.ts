import type { Tags } from "./types";

const LABELS: Record<string, string> = {
  full_time: "Full time",
  internship: "Internship",
  contract: "Contract",
  onsite: "On-site",
  hybrid: "Hybrid",
  remote: "Remote",
  hr: "HR",
  adzuna: "Adzuna",
  greenhouse: "Greenhouse",
  lever: "Lever",
  ashby: "Ashby",
  smartrecruiters: "SmartRecruiters",
};

export function label(value: string): string {
  return LABELS[value] ?? value.charAt(0).toUpperCase() + value.slice(1).replaceAll("_", " ");
}

export function experience(tags: Tags): string | null {
  const { experienceMin: lo, experienceMax: hi } = tags;
  if (lo === null && hi === null) return null;
  if (lo !== null && hi !== null) {
    if (lo === 0 && hi === 0) return "No experience needed";
    return lo === hi ? `${lo} yr` : `${lo}-${hi} yrs`;
  }
  return lo !== null ? `${lo}+ yrs` : `Up to ${hi} yrs`;
}

/** "3 days ago" style, computed against a caller-supplied "now" so server output is stable. */
export function timeAgo(iso: string | null, now: number): string | null {
  if (!iso) return null;
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  const units: [number, string][] = [
    [86400 * 30, "month"],
    [86400 * 7, "week"],
    [86400, "day"],
    [3600, "hour"],
    [60, "minute"],
  ];
  for (const [size, name] of units) {
    const n = Math.floor(seconds / size);
    if (n >= 1) return `${n} ${name}${n === 1 ? "" : "s"} ago`;
  }
  return "just now";
}

export function formatDate(iso: string | null): string {
  if (!iso) return "not yet";
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(iso));
}
