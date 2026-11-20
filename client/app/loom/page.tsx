import type { Metadata } from "next";
import Link from "next/link";
import { BRAND } from "@/lib/brand";
import { LOOM_NOTE_DATE, LOOM_SHARE_URL, loomEmbedUrl } from "@/lib/loom";

export const metadata: Metadata = {
  title: "Video walkthrough",
  description: `A 5-minute video tour of ${BRAND.name}: the site, how jobs are collected and tagged, and what it costs.`,
};

/** What the video covers, in order. Each line links to the page shown at that point. */
const CHAPTERS: [string, string, string, string][] = [
  ["0:00", "Hello", "What the project is and who it is for.", "/"],
  ["0:20", "Home page", "Live job and company counts from the API.", "/"],
  ["0:40", "Search and filters", "Role, city, work mode, job type and experience. Filters live in the link.", "/jobs"],
  ["1:30", "A job page", "AI tags, the source, and Apply going to the employer's own page.", "/jobs"],
  ["2:05", "Saved and applied jobs", "Log in, save a job, see it on the dashboard.", "/dashboard"],
  ["2:35", "On a phone", "Filters fold behind one button.", "/jobs"],
  ["2:50", "How it is built", "Architecture, the nightly run, the AI fallback chain and the prompt.", "/docs#architecture"],
  ["3:40", "Cost and real runs", "Tokens counted on every call, and the live run history.", "/docs#cost"],
  ["4:15", "What I found", "Three findings, with proof.", "/docs#findings"],
  ["4:45", "Next steps", "More job APIs and the accuracy check.", "/docs#next"],
];

/** Everything the video shows is already on the site, so point visitors to it. */
const MEANWHILE: [string, string, string][] = [
  ["/docs", "Project docs", "Architecture and system diagrams, the prompts, cost, run history and what broke."],
  ["/docs#screens", "Screenshots", "Every page of the site, on a laptop and on a phone, in an image viewer."],
  ["/jobs", "Try the live site", "Search real fresher jobs collected last night."],
  ["/about", "Sources and method", "Where jobs come from, how tagging works and the live tagging cost."],
];

export default function LoomPage() {
  const embed = loomEmbedUrl(LOOM_SHARE_URL);

  return (
    <div className="mx-auto grid max-w-3xl gap-8">
      <header className="pt-2">
        <p className="text-sm font-semibold tracking-wide text-brand uppercase">Video walkthrough</p>
        <h1 className="display mt-2 text-3xl sm:text-4xl">{BRAND.name} in 5 minutes</h1>
        <p className="mt-3 text-lg text-muted-foreground">
          A short screen recording of the site and how it works behind the scenes.
        </p>
      </header>

      {embed ? (
        <section aria-label="Video" className="grid gap-3">
          <div className="relative aspect-video overflow-hidden rounded-lg border bg-muted">
            <iframe
              src={embed}
              title={`${BRAND.name} video walkthrough`}
              allow="fullscreen; picture-in-picture"
              allowFullScreen
              loading="lazy"
              referrerPolicy="strict-origin-when-cross-origin"
              className="absolute inset-0 h-full w-full"
            />
          </div>
          <a
            href={LOOM_SHARE_URL ?? embed}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center text-sm font-semibold text-brand underline underline-offset-4"
          >
            Watch on Loom<span aria-hidden="true">&nbsp;↗</span>
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        </section>
      ) : (
        <section role="status" aria-labelledby="pending-h" className="card overflow-hidden">
          <div className="flex items-center gap-3 border-b bg-[#fff6cc] px-5 py-3 sm:px-6">
            <span className="pulse-ring relative inline-flex h-2.5 w-2.5 rounded-full bg-[#c99a00]" aria-hidden="true" />
            <p className="text-sm font-semibold text-[#7a5b00]">Video coming soon</p>
          </div>
          <div className="grid gap-3 p-5 leading-7 sm:p-6">
            <h2 id="pending-h" className="text-xl font-bold">
              Sorry, the video is late
            </h2>
            <p>
              Screen recording is not working on my machine right now, so I could not record the walkthrough in
              time. I am fixing it, and I will put the video on this page as soon as it is recorded.
            </p>
            <p>
              Nothing in the project is waiting on the video. The site, the nightly job run and the docs are all
              live, and everything the video will show is already on the pages linked below.
            </p>
            <p className="text-sm text-muted-foreground">Note added on {LOOM_NOTE_DATE}.</p>
          </div>
        </section>
      )}

      <section aria-labelledby="chapters-h">
        <h2 id="chapters-h" className="text-xl font-bold">
          {embed ? "What the video covers" : "What the video will cover"}
        </h2>
        <ol className="mt-4 grid gap-2">
          {CHAPTERS.map(([time, title, text, href]) => (
            <li key={time}>
              <Link
                href={href}
                className="card grid grid-cols-[3.5rem_1fr] items-baseline gap-3 p-4 transition-shadow hover:shadow-hover"
              >
                <span className="font-mono text-sm font-semibold text-brand tabular-nums">{time}</span>
                <span>
                  <span className="font-semibold">{title}</span>
                  <span className="mt-0.5 block text-sm text-muted-foreground">{text}</span>
                </span>
              </Link>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="meanwhile-h">
        <h2 id="meanwhile-h" className="text-xl font-bold">
          {embed ? "See it for yourself" : "In the meantime"}
        </h2>
        <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          {MEANWHILE.map(([href, title, text]) => (
            <li key={href}>
              <Link href={href} className="card block h-full p-5 transition-shadow hover:shadow-hover">
                <span className="font-bold text-brand">{title} →</span>
                <span className="mt-1 block text-[15px] leading-6 text-muted-foreground">{text}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
