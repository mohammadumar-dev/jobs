import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import { getTaggingStats } from "@/lib/api";
import { EVAL_RESULTS as R } from "@/lib/eval-results";
import type { TaggingStats } from "@/lib/types";

export const metadata: Metadata = {
  title: "Sources and method",
  description: "Where the jobs come from, how they are tagged, what tagging costs and how accurate it is.",
};

const SOURCES = [
  ["Adzuna", "India job search API. We link out through Adzuna's own redirect link."],
  ["Greenhouse", "Public job board API of each listed company."],
  ["Lever", "Public postings API of each listed company."],
  ["Ashby", "Public job posting API of each listed company."],
  ["SmartRecruiters", "Public posting API of each listed company."],
];

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="card p-5 sm:p-6">
      <h2 id={id} className="text-xl font-bold">
        {title}
      </h2>
      <div className="mt-3 grid gap-3 leading-7">{children}</div>
    </section>
  );
}

export default async function AboutPage() {
  let stats: TaggingStats | null = null;
  try {
    stats = await getTaggingStats();
  } catch {
    // API asleep or down: the cost section says so and the rest of the page still renders.
  }
  return (
    <div className="mx-auto grid max-w-3xl gap-4">
      <h1 className="display mb-2 text-3xl sm:text-4xl">How {BRAND.name} works</h1>

      <Section id="sources" title="Where the jobs come from">
        <p>
          Only official, public job APIs. No scraping of login-walled pages and no CAPTCHA
          bypass. Our fetcher identifies itself, makes at most one request per second per site,
          and always sends you to the employer&apos;s own apply page.
        </p>
        <dl className="grid gap-2">
          {SOURCES.map(([name, text]) => (
            <div key={name} className="grid gap-1 sm:grid-cols-[10rem_1fr]">
              <dt className="font-semibold">{name}</dt>
              <dd className="text-muted-foreground">{text}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section id="pipeline" title="What happens every day">
        <ol className="grid list-decimal gap-2 pl-5">
          <li>Fetch every source. One failing source never stops the others.</li>
          <li>Keep only jobs in India that show an entry-level signal.</li>
          <li>Remove duplicates of the same role, company and city across sources.</li>
          <li>Tag new or changed jobs with a language model; unchanged jobs are skipped.</li>
          <li>Hide jobs that have been missing from their source for two runs in a row.</li>
        </ol>
      </Section>

      <Section id="tagging" title="How tagging works">
        <p>
          Each job is labelled with a role category, city, work mode, job type, experience range
          and whether a fresher can apply. The model must answer in a fixed JSON format using a
          fixed list of values; anything else is rejected and retried once.
        </p>
      </Section>

      <Section id="cost" title="Tagging cost">
        <CostSection stats={stats} />
      </Section>

      <Section id="accuracy" title="Accuracy">
        {R.sampleSize === null ? (
          <p>
            Not yet checked by a person. The check compares the model&apos;s tags on 50 random jobs
            with labels from a person who has not seen the model&apos;s answers; the results will be
            published here once it has been done.
          </p>
        ) : (
          <>
            <p>
              Checked on {R.measuredOn} against {R.sampleSize} random jobs labelled by a person who
              did not see the model&apos;s answers. Model: {R.model}, prompt {R.promptVersion}.
            </p>
            {R.method && <p className="text-[15px] text-muted-foreground">{R.method}</p>}
            <table className="w-full text-left">
              <thead>
                <tr className="border-b">
                  <th scope="col" className="py-2 font-semibold">
                    Field
                  </th>
                  <th scope="col" className="py-2 text-right font-semibold">
                    Correct
                  </th>
                </tr>
              </thead>
              <tbody>
                {R.accuracy.map((row) => (
                  <tr key={row.field} className="border-b">
                    <td className="py-2">{row.field}</td>
                    <td className="py-2 text-right tabular-nums">{row.percent.toFixed(0)}%</td>
                  </tr>
                ))}
                {R.tagsCorrectPercent !== null && (
                  <tr className="border-b">
                    <td className="py-2 font-semibold">All tags (average)</td>
                    <td className="py-2 text-right font-semibold tabular-nums">
                      {R.tagsCorrectPercent.toFixed(0)}%
                    </td>
                  </tr>
                )}
                <tr>
                  <td className="py-2 font-semibold">Jobs with every field correct</td>
                  <td className="py-2 text-right font-semibold tabular-nums">
                    {R.allFieldsCorrectPercent?.toFixed(0)}%
                  </td>
                </tr>
              </tbody>
            </table>
            {R.strictAllFieldsCorrectPercent !== null && (
              <p className="text-[15px] text-muted-foreground">
                Before the review, the model matched the hand labels exactly on every field for{" "}
                {R.strictAllFieldsCorrectPercent.toFixed(0)}% of jobs. {R.history}
              </p>
            )}
          </>
        )}
      </Section>
    </div>
  );
}

const PROVIDERS: Record<string, string> = {
  gemini: "Google Gemini",
  groq: "Groq",
  openrouter: "OpenRouter",
};

/** "gemini/gemini-3.5-flash-lite" -> "Google Gemini (gemini-3.5-flash-lite)". */
function modelLabel(model: string): string {
  if (model === "heuristic-v1") return "Rules only (no AI; used when every AI is unavailable)";
  const slash = model.indexOf("/");
  if (slash < 0) return model;
  const provider = model.slice(0, slash);
  return `${PROVIDERS[provider] ?? provider} (${model.slice(slash + 1)})`;
}

/** "claude-haiku-5-5" -> "Claude Haiku 5.5". */
function referenceLabel(model: string): string {
  const m = /^claude-([a-z]+)-(\d+)-(\d+)$/.exec(model);
  if (!m) return model;
  return `Claude ${m[1][0].toUpperCase()}${m[1].slice(1)} ${m[2]}.${m[3]}`;
}

const usd = (n: number) => `$${n < 1 ? n.toFixed(3) : n.toFixed(2)}`;
const num = (n: number | null) => (n === null ? "–" : n.toLocaleString("en-IN"));

function CostSection({ stats }: { stats: TaggingStats | null }) {
  if (!stats) {
    return <p>The cost figures are not available right now. Try again in a minute.</p>;
  }
  if (stats.llmTaggedJobs === 0) {
    return <p>No jobs have been tagged by a language model yet. Figures appear after the first daily run.</p>;
  }
  const ref = referenceLabel(stats.referenceModel);
  return (
    <>
      <dl className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border p-4">
          <dt className="text-muted-foreground text-sm">What we spend per 1,000 jobs</dt>
          <dd className="mt-1 text-2xl font-bold tabular-nums">{usd(stats.actualPer1000Usd ?? 0)}</dd>
          <dd className="text-muted-foreground text-sm">We use the AI providers&apos; free tiers.</dd>
        </div>
        <div className="rounded-lg border p-4">
          <dt className="text-muted-foreground text-sm">If we paid ({ref}, list price)</dt>
          <dd className="mt-1 text-2xl font-bold tabular-nums">
            {stats.paidPer1000Usd === null ? "–" : usd(stats.paidPer1000Usd)}
            {stats.paidPer1000Inr !== null && (
              <span className="text-muted-foreground text-base font-normal">
                {" "}
                (about ₹{stats.paidPer1000Inr.toFixed(2)})
              </span>
            )}
          </dd>
          <dd className="text-muted-foreground text-sm">per 1,000 jobs</dd>
        </div>
      </dl>
      <p>
        Worked out from the tokens actually used: on average {num(stats.avgInputTokens)} tokens in and{" "}
        {num(stats.avgOutputTokens)} out per job, retries included, across {num(stats.llmTaggedJobs)} jobs.
        Priced at {ref}&apos;s ${stats.referenceInputUsdPerMTok.toFixed(2)} per million input and $
        {stats.referenceOutputUsdPerMTok.toFixed(2)} per million output tokens.
      </p>
      <table className="w-full text-left">
        <caption className="mb-2 text-left font-semibold">Which model tagged the jobs</caption>
        <thead>
          <tr className="border-b">
            <th scope="col" className="py-2 font-semibold">
              Model
            </th>
            <th scope="col" className="py-2 text-right font-semibold">
              Jobs
            </th>
          </tr>
        </thead>
        <tbody>
          {stats.models.map((m) => (
            <tr key={m.model} className="border-b">
              <td className="py-2">{modelLabel(m.model)}</td>
              <td className="py-2 pl-3 text-right whitespace-nowrap tabular-nums">
                {num(m.jobs)} ({m.percent.toFixed(0)}%)
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {stats.lastRun && (
        <p className="text-muted-foreground text-sm">
          Updated after every daily run. Last run:{" "}
          {new Date(stats.lastRun).toLocaleString("en-IN", {
            dateStyle: "medium",
            timeStyle: "short",
            timeZone: "Asia/Kolkata",
          })}{" "}
          IST.
        </p>
      )}
    </>
  );
}
