import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import { EVAL_RESULTS as R } from "@/lib/eval-results";

export const metadata: Metadata = {
  title: "Sources and method",
  description: "Where the jobs come from, how they are tagged, and how accurate the tags are.",
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
    <section aria-labelledby={id} className="card p-6">
      <h2 id={id} className="text-xl font-bold">
        {title}
      </h2>
      <div className="mt-3 grid gap-3 leading-7">{children}</div>
    </section>
  );
}

export default function AboutPage() {
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

      <Section id="numbers" title="Accuracy and cost">
        {R.sampleSize === null ? (
          <p>
            Not measured yet. The accuracy check (50 jobs labelled by a person without seeing the
            model&apos;s answers) and the cost per 1,000 jobs will be published here once they
            have been run.
          </p>
        ) : (
          <>
            <p>
              Checked on {R.measuredOn} against {R.sampleSize} jobs labelled by a person who did
              not see the model&apos;s answers. Model: {R.model}.
            </p>
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
                <tr>
                  <td className="py-2 font-semibold">All fields correct</td>
                  <td className="py-2 text-right font-semibold tabular-nums">
                    {R.allFieldsCorrectPercent?.toFixed(0)}%
                  </td>
                </tr>
              </tbody>
            </table>
            <p>
              Tagging cost: ${R.costPer1000Usd?.toFixed(3)} (about ₹{R.costPer1000Inr?.toFixed(2)}) per
              1,000 jobs.
            </p>
          </>
        )}
      </Section>
    </div>
  );
}
