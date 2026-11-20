"use client";

import Link from "next/link";
import { useState } from "react";
import { label } from "@/lib/format";
import type { Facet, JobFilters as Filters, Meta } from "@/lib/types";

const EXPERIENCE = [
  { value: "0", text: "No experience" },
  { value: "1", text: "Up to 1 year" },
  { value: "2", text: "Up to 2 years" },
];

function Select({
  name,
  text,
  value,
  options,
}: {
  name: string;
  text: string;
  value?: string;
  options: { value: string; text: string }[];
}) {
  return (
    <div className="min-w-0">
      <label htmlFor={`filter-${name}`} className="mb-1 block text-sm font-semibold">
        {text}
      </label>
      <select
        id={`filter-${name}`}
        name={name}
        defaultValue={value ?? ""}
        className="field"
        // Filters apply immediately; the Search button covers no-JS and keyboard users.
        onChange={(event) => event.currentTarget.form?.requestSubmit()}
      >
        <option value="">Any</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.text}
          </option>
        ))}
      </select>
    </div>
  );
}

const facetOptions = (facets: Facet[]) =>
  facets.map((f) => ({ value: f.value, text: `${label(f.value)} (${f.count})` }));

const FILTER_KEYS = ["role", "city", "mode", "type", "exp"] as const;

/**
 * A plain GET form: the URL is the single source of truth for filters, so
 * results are shareable, the back button works, and it works without JS.
 */
export function JobFilters({ filters, meta }: { filters: Filters; meta: Meta }) {
  const active = Object.entries(filters).some(([key, value]) => key !== "page" && value);
  const chosen = FILTER_KEYS.filter((key) => filters[key]).length;
  // Phones: the five dropdowns fold away so the results start on the first screen.
  const [open, setOpen] = useState(false);
  return (
    <form
      action="/jobs"
      method="get"
      role="search"
      aria-label="Search jobs"
      key={JSON.stringify(filters)}
      className="card grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-6"
    >
      <div className="sm:col-span-2 lg:col-span-6">
        <label htmlFor="filter-q" className="mb-1 block text-sm font-semibold">
          Title, company or skill
        </label>
        <div className="flex gap-2">
          <input
            id="filter-q"
            type="search"
            name="q"
            defaultValue={filters.q ?? ""}
            maxLength={100}
            placeholder="e.g. software intern, marketing, Paytm"
            className="field"
          />
          <button type="submit" className="btn btn-primary">
            Search
          </button>
        </div>
      </div>
      <div className="flex gap-2 sm:hidden">
        <button
          type="button"
          className="btn btn-secondary flex-1"
          aria-expanded={open}
          aria-controls="filter-fields"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Hide filters" : "Filters"}
          {chosen > 0 && (
            <span className="grid size-6 place-items-center rounded-full bg-brand text-xs text-white">{chosen}</span>
          )}
        </button>
        {active && (
          <Link href="/jobs" className="btn btn-secondary">
            Clear
          </Link>
        )}
      </div>
      <div id="filter-fields" className={`${open ? "grid" : "hidden"} gap-4 sm:contents`}>
        <Select name="role" text="Role" value={filters.role} options={facetOptions(meta.roles)} />
        <Select name="city" text="City" value={filters.city} options={facetOptions(meta.cities)} />
        <Select name="mode" text="Work mode" value={filters.mode} options={facetOptions(meta.workModes)} />
        <Select name="type" text="Job type" value={filters.type} options={facetOptions(meta.jobTypes)} />
        <Select name="exp" text="Experience" value={filters.exp} options={EXPERIENCE} />
        <div className="hidden items-end sm:flex">
          {active && (
            <Link href="/jobs" className="btn btn-secondary w-full">
              Clear filters
            </Link>
          )}
        </div>
      </div>
    </form>
  );
}
