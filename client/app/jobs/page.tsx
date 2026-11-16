import type { Metadata } from "next";
import Link from "next/link";
import { JobCard } from "@/components/job-card";
import { JobFilters } from "@/components/job-filters";
import { ApiError, getMeta, searchJobs, toQuery } from "@/lib/api";
import type { JobFilters as Filters, JobPage, Meta } from "@/lib/types";

export const metadata: Metadata = {
  title: "Fresher jobs and internships",
  description: "Search entry-level jobs and internships in India by role, city, work mode and experience.",
};

const KEYS = ["q", "role", "city", "mode", "type", "exp", "page"] as const;

function readFilters(params: Record<string, string | string[] | undefined>): Filters {
  const filters: Filters = {};
  for (const key of KEYS) {
    const raw = params[key];
    const value = (Array.isArray(raw) ? raw[0] : raw)?.trim();
    if (value) filters[key] = value.slice(0, 100);
  }
  return filters;
}

function Pagination({ filters, page, totalPages }: { filters: Filters; page: number; totalPages: number }) {
  if (totalPages <= 1) return null;
  const href = (target: number) => `/jobs${toQuery({ ...filters, page: target > 1 ? String(target) : undefined })}`;
  return (
    <nav aria-label="Pagination" className="mt-8 flex items-center justify-center gap-3">
      {page > 1 ? (
        <Link href={href(page - 1)} className="btn btn-secondary btn-sm" rel="prev">
          Previous
        </Link>
      ) : (
        <span className="btn btn-secondary btn-sm opacity-50" aria-disabled="true">
          Previous
        </span>
      )}
      <p className="text-sm font-semibold" aria-current="page">
        Page {page} of {totalPages}
      </p>
      {page < totalPages ? (
        <Link href={href(page + 1)} className="btn btn-secondary btn-sm" rel="next">
          Next
        </Link>
      ) : (
        <span className="btn btn-secondary btn-sm opacity-50" aria-disabled="true">
          Next
        </span>
      )}
    </nav>
  );
}

type Loaded =
  | { ok: true; meta: Meta; page: JobPage; now: number }
  | { ok: false; status: number };

async function load(filters: Filters): Promise<Loaded> {
  try {
    const [meta, page] = await Promise.all([getMeta(), searchJobs(filters)]);
    return { ok: true, meta, page, now: Date.now() };
  } catch (error) {
    return { ok: false, status: error instanceof ApiError ? error.status : 0 };
  }
}

const ERRORS: Record<number, [string, string]> = {
  400: ["That search is not valid", "One of the filters in the address is not recognised."],
  429: ["Too many searches in a short time", "Please wait a minute and try again."],
};

export default async function JobsPage({ searchParams }: PageProps<"/jobs">) {
  const filters = readFilters(await searchParams);
  const result = await load(filters);

  if (!result.ok) {
    const [title, text] = ERRORS[result.status] ?? [
      "Jobs could not be loaded",
      "The job service is not responding. Please try again shortly.",
    ];
    return (
      <>
        <h1 className="display mb-6 text-3xl sm:text-4xl">Find your first role</h1>
        <div role="alert" className="card mt-6 p-8 text-center">
          <h2 className="text-lg font-bold">{title}</h2>
          <p className="mt-2 text-muted-foreground">{text}</p>
          <Link href="/jobs" className="btn btn-primary mt-5">
            Reset search
          </Link>
        </div>
      </>
    );
  }

  const { meta, page, now } = result;
  return (
    <>
      <h1 className="display mb-6 text-3xl sm:text-4xl">Find your first role</h1>
      <JobFilters filters={filters} meta={meta} />
      {page.items.length === 0 ? (
        <div className="card mt-6 p-8 text-center">
          <h2 className="text-lg font-bold">No jobs match these filters</h2>
          <p className="mt-2 text-muted-foreground">
            Try a broader search, or remove a filter. New jobs are added every day.
          </p>
          <Link href="/jobs" className="btn btn-primary mt-5">
            Show all jobs
          </Link>
        </div>
      ) : (
        <>
          <p className="mt-6 text-sm font-semibold text-muted-foreground" role="status">
            {page.total.toLocaleString("en-IN")} {page.total === 1 ? "job" : "jobs"} found
          </p>
          <ul className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {page.items.map((job) => (
              <li key={job.id}>
                <JobCard job={job} now={now} />
              </li>
            ))}
          </ul>
          <Pagination filters={filters} page={page.page} totalPages={page.totalPages} />
        </>
      )}
    </>
  );
}
