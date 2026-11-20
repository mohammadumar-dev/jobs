import Link from "next/link";
import { experience, label, timeAgo } from "@/lib/format";
import type { JobCard as Job } from "@/lib/types";

export function TagChips({ job }: { job: Job }) {
  const tags = job.tags;
  if (!tags) return null;
  const exp = experience(tags);
  return (
    <ul className="flex flex-wrap gap-2" aria-label="Job details">
      <li className="chip">{label(tags.jobType)}</li>
      <li className="chip">{label(tags.workMode)}</li>
      {exp && <li className="chip">{exp}</li>}
      <li className="chip">{label(tags.roleCategory)}</li>
    </ul>
  );
}

export function JobCard({ job, now, note }: { job: Job; now: number; note?: string }) {
  const posted = timeAgo(job.postedAt ?? job.firstSeenAt, now);
  const when = note ?? (posted ? `Posted ${posted}` : "");
  const place = job.tags && job.tags.city !== "Other" ? job.tags.city : job.location;
  return (
    <article className="card relative flex h-full flex-col gap-3 p-4 transition-shadow hover:shadow-hover">
      <div>
        <h3 className="text-base font-bold leading-snug">
          <Link href={`/jobs/${job.id}`} className="rounded-sm text-brand underline-offset-4 after:absolute after:inset-0 after:rounded-[8px] after:content-[''] hover:underline">
            {job.title}
          </Link>
        </h3>
        <p className="mt-1 text-[15px] font-medium">{job.company}</p>
        <p className="mt-1 text-sm text-muted-foreground">{place || "India"}</p>
      </div>
      <TagChips job={job} />
      <p className="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
        {!job.active && <span className="font-semibold text-destructive">No longer listed.</span>}
        {when && (
          <>
            <span>{when}</span>
            <span aria-hidden="true">·</span>
          </>
        )}
        <span>
          via <span className="font-semibold text-foreground">{label(job.sourceType)}</span>
        </span>
      </p>
    </article>
  );
}
