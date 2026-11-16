import Link from "next/link";
import { JobCard } from "@/components/job-card";
import { getMeta, searchJobs } from "@/lib/api";
import { formatDate, label } from "@/lib/format";
import type { JobPage, Meta } from "@/lib/types";

function StatTile({ value, text }: { value: string; text: string }) {
  return (
    <div className="card rounded-tile p-6 text-center">
      <p className="display text-3xl text-brand sm:text-4xl">{value}</p>
      <p className="mt-2 text-sm font-semibold text-muted-foreground">{text}</p>
    </div>
  );
}

async function loadHome(): Promise<{ meta: Meta | null; featured: JobPage | null; now: number }> {
  try {
    const [meta, featured] = await Promise.all([getMeta(), searchJobs({})]);
    return { meta, featured, now: Date.now() };
  } catch {
    // The API may be asleep or down; the page still renders with a clear message.
    return { meta: null, featured: null, now: Date.now() };
  }
}

export default async function HomePage() {
  const { meta, featured, now } = await loadHome();

  return (
    <div className="flex flex-col gap-12 sm:gap-[72px]">
      <section className="pt-6 text-center sm:pt-12">
        <h1 className="display mx-auto max-w-3xl text-[clamp(2.25rem,6vw,4rem)]">
          Your first job starts here
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground">
          Internships and entry-level roles across India, pulled from company career pages every
          day and sorted so you can find yours fast.
        </p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <Link href="/jobs" className="btn btn-primary">
            Browse jobs
          </Link>
          <Link href="/jobs?type=internship" className="btn btn-secondary">
            I&apos;m looking for an internship
          </Link>
        </div>
      </section>

      {meta ? (
        <section aria-label="At a glance" className="grid gap-4 sm:grid-cols-3">
          <StatTile value={meta.activeJobs.toLocaleString("en-IN")} text="active fresher jobs" />
          <StatTile value={meta.companies.toLocaleString("en-IN")} text="companies hiring" />
          <StatTile value={meta.lastRefresh ? "Daily" : "Soon"} text={`last refresh: ${formatDate(meta.lastRefresh)}`} />
        </section>
      ) : (
        <p role="status" className="card p-6 text-center">
          Jobs are loading slowly right now. Please refresh in a moment.
        </p>
      )}

      {meta && meta.roles.length > 0 && (
        <section aria-labelledby="categories">
          <h2 id="categories" className="display text-2xl">
            Pick your lane
          </h2>
          <ul className="mt-5 flex flex-wrap gap-2">
            {meta.roles.map((role) => (
              <li key={role.value}>
                <Link
                  href={`/jobs?role=${encodeURIComponent(role.value)}`}
                  className="inline-flex min-h-11 items-center gap-2 rounded-[10px] border bg-card px-4 text-[15px] font-semibold hover:bg-brand-soft"
                >
                  {label(role.value)}
                  <span className="text-sm font-medium text-muted-foreground">{role.count}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {featured && featured.items.length > 0 && (
        <section aria-labelledby="latest">
          <div className="flex items-end justify-between gap-4">
            <h2 id="latest" className="display text-2xl">
              Fresh today
            </h2>
            <Link href="/jobs" className="font-semibold text-brand underline-offset-4 hover:underline">
              See all jobs
            </Link>
          </div>
          <ul className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {featured.items.slice(0, 6).map((job) => (
              <li key={job.id}>
                <JobCard job={job} now={now} />
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-tile bg-foreground px-6 py-10 text-center text-white">
        <h2 className="display text-2xl sm:text-3xl">Keep your search in one place</h2>
        <p className="mx-auto mt-3 max-w-lg text-[#d4d4d4]">
          Save the roles you like and see every job you clicked apply on.
        </p>
        <Link href="/register" className="btn mt-6 bg-white text-foreground hover:bg-[#f3f3f0]">
          Create a free account
        </Link>
      </section>
    </div>
  );
}
