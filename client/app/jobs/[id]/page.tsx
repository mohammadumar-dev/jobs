import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ApplyButton, SaveButton } from "@/components/job-actions";
import { TagChips } from "@/components/job-card";
import { ApiError, getJob } from "@/lib/api";
import { label, timeAgo } from "@/lib/format";
import type { JobDetail } from "@/lib/types";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function load(id: string): Promise<JobDetail & { now: number }> {
  if (!UUID.test(id)) notFound();
  try {
    return { ...(await getJob(id)), now: Date.now() };
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 400)) notFound();
    throw error;
  }
}

export async function generateMetadata({ params }: PageProps<"/jobs/[id]">): Promise<Metadata> {
  const { id } = await params;
  try {
    const job = await load(id);
    return { title: `${job.title} at ${job.company}`, description: job.description.slice(0, 155) };
  } catch {
    return { title: "Job" };
  }
}

export default async function JobDetailPage({ params }: PageProps<"/jobs/[id]">) {
  const { id } = await params;
  const job = await load(id);
  const posted = timeAgo(job.postedAt ?? job.firstSeenAt, job.now);

  return (
    <article className="mx-auto max-w-3xl">
      <Link href="/jobs" className="text-sm font-semibold text-brand underline-offset-4 hover:underline">
        ← All jobs
      </Link>

      <header className="card mt-4 p-6">
        {!job.active && (
          <p role="status" className="mb-4 rounded-md bg-[#fdeceb] px-3 py-2 text-sm font-semibold text-destructive">
            This job is no longer listed by the employer. The apply link may not work.
          </p>
        )}
        <h1 className="display text-2xl sm:text-3xl">{job.title}</h1>
        <p className="mt-3 text-lg font-semibold">{job.company}</p>
        <p className="mt-1 text-muted-foreground">{job.location || "India"}</p>
        <div className="mt-4">
          <TagChips job={job} />
        </div>
        <p className="mt-4 text-sm text-muted-foreground">
          {posted && `Posted ${posted} · `}
          Source: <span className="font-semibold text-foreground">{label(job.sourceType)}</span>
        </p>
        <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-start">
          <ApplyButton jobId={job.id} applyUrl={job.applyUrl} />
          <SaveButton jobId={job.id} />
        </div>
      </header>

      <section aria-labelledby="description" className="card mt-4 p-6">
        <h2 id="description" className="text-lg font-bold">
          About the role
        </h2>
        {/* Plain text from the API, rendered as text. Never set as HTML. */}
        <div className="mt-3 whitespace-pre-line break-words leading-7">
          {job.description || "The employer did not provide a description. See the original posting."}
        </div>
      </section>
    </article>
  );
}
