/**
 * Animated diagrams for the /docs page. Plain SVG: the dashed lines move with CSS
 * (see .flow-line in globals.css) and the dots travel with SMIL <animateMotion>,
 * so nothing here needs client-side JavaScript. Both stop for prefers-reduced-motion.
 */

const BRAND = "var(--brand)";

function Box({
  x,
  y,
  w,
  h,
  title,
  lines = [],
  tone = "card",
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  lines?: string[];
  tone?: "card" | "brand" | "yellow" | "muted";
}) {
  const fill = { card: "#ffffff", brand: "#eef0fd", yellow: "#fff6cc", muted: "#f3f3f0" }[tone];
  const stroke = tone === "brand" ? BRAND : tone === "yellow" ? "#e0b400" : "#d4d4cf";
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={10} fill={fill} stroke={stroke} strokeWidth={1.5} />
      <text x={x + w / 2} y={y + 28} textAnchor="middle" fontSize={16} fontWeight={700}>
        {title}
      </text>
      {lines.map((line, i) => (
        <text key={line} x={x + w / 2} y={y + 52 + i * 20} textAnchor="middle" fontSize={13} className="muted">
          {line}
        </text>
      ))}
    </g>
  );
}

/** A moving dashed connector with an arrow head and a dot that travels along it. */
function Edge({
  d,
  label,
  lx,
  ly,
  dur = 2.5,
  warn = false,
  slow = false,
  marker = "arrow",
}: {
  d: string;
  label?: string;
  lx?: number;
  ly?: number;
  dur?: number;
  warn?: boolean;
  slow?: boolean;
  marker?: string;
}) {
  return (
    <g>
      <path d={d} className={`flow-line${warn ? " warn" : ""}${slow ? " slow" : ""}`} markerEnd={`url(#${warn ? "arrow-warn" : marker})`} />
      <circle r={4.5} className={warn ? "flow-dot warn" : "flow-dot"}>
        <animateMotion dur={`${dur}s`} repeatCount="indefinite" path={d} />
      </circle>
      {label && lx !== undefined && ly !== undefined && (
        <text x={lx} y={ly} textAnchor="middle" fontSize={12} className="muted">
          {label}
        </text>
      )}
    </g>
  );
}

function Markers() {
  return (
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10 z" fill={BRAND} />
      </marker>
      <marker id="arrow-warn" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10 z" fill="#b54708" />
      </marker>
    </defs>
  );
}

/** Wide diagrams scroll sideways inside their frame on small screens, never the page. */
function Frame({ label, minWidth, children }: { label: string; minWidth: number; children: React.ReactNode }) {
  return (
    <figure className="overflow-x-auto rounded-lg border bg-[#fffef9] p-3" aria-label={label}>
      <div style={{ minWidth }}>{children}</div>
    </figure>
  );
}

export function ArchitectureDiagram() {
  return (
    <Frame label="Architecture diagram" minWidth={720}>
      <svg viewBox="0 0 960 420" className="diagram" role="img" aria-labelledby="arch-t arch-d">
        <title id="arch-t">FirstRung architecture</title>
        <desc id="arch-d">
          Five job APIs feed a Python worker on GitHub Actions. The worker asks free AI models for tags and saves
          everything in Neon Postgres. A Spring Boot API on Render reads the database. The Next.js website on Vercel
          calls the API and serves pages to students.
        </desc>
        <Markers />

        <rect x={20} y={40} width={190} height={300} rx={12} fill="#f3f3f0" stroke="#d4d4cf" />
        <text x={115} y={70} textAnchor="middle" fontSize={16} fontWeight={700}>
          Job sources
        </text>
        {["Adzuna (India API)", "Greenhouse", "Lever", "Ashby", "SmartRecruiters"].map((s, i) => (
          <g key={s}>
            <rect x={38} y={90 + i * 48} width={154} height={36} rx={8} fill="#ffffff" stroke="#e4e4e0" />
            <text x={115} y={113 + i * 48} textAnchor="middle" fontSize={13}>
              {s}
            </text>
          </g>
        ))}

        <Box x={270} y={90} w={210} h={110} title="Worker (Python)" lines={["GitHub Actions", "daily, 02:47 IST"]} tone="yellow" />
        <Box x={270} y={270} w={210} h={110} title="Free AI models" lines={["Gemini → Groq →", "OpenRouter → rules"]} />
        <Box x={540} y={90} w={170} h={110} title="Neon Postgres" lines={["jobs, tags, runs,", "users, saved jobs"]} tone="brand" />
        <Box x={770} y={90} w={170} h={110} title="Spring Boot API" lines={["on Render", "search, auth, stats"]} />
        <Box x={770} y={270} w={170} h={110} title="Next.js website" lines={["on Vercel", "pages + /api proxy"]} />
        <Box x={540} y={270} w={170} h={110} title="Student" lines={["any browser,", "phone or laptop"]} tone="muted" />

        <Edge d="M210,190 L268,150" label="fetch" lx={238} ly={150} dur={2} />
        <Edge d="M360,200 L360,268" label="tag" lx={384} ly={240} dur={1.8} />
        <Edge d="M400,268 L400,202" dur={1.8} slow />
        <Edge d="M480,145 L538,145" label="save" lx={509} ly={136} dur={1.6} />
        <Edge d="M770,145 L712,145" label="read" lx={741} ly={136} dur={1.6} />
        <Edge d="M855,270 L855,202" label="JSON" lx={884} ly={240} dur={1.8} />
        <Edge d="M710,325 L768,325" label="HTTPS" lx={739} ly={316} dur={1.6} />
      </svg>
    </Frame>
  );
}

export function TaggingChainDiagram() {
  const providers = [
    { x: 190, name: "Gemini", sub: "flash-lite" },
    { x: 390, name: "Groq", sub: "gpt-oss-120b" },
    { x: 590, name: "OpenRouter", sub: "free router" },
  ];
  return (
    <Frame label="AI tagging fallback diagram" minWidth={720}>
      <svg viewBox="0 0 960 330" className="diagram" role="img" aria-labelledby="chain-t chain-d">
        <title id="chain-t">How one job gets its tags</title>
        <desc id="chain-d">
          The job goes to Gemini first. If Gemini hits a limit or keeps failing, Groq is tried, then OpenRouter, then
          simple rules. Every answer is checked against the allowed values, fixed by title guards and saved with its
          token count.
        </desc>
        <Markers />
        <Box x={20} y={40} w={130} h={80} title="New job" lines={["title + text"]} tone="muted" />
        {providers.map((p) => (
          <Box key={p.name} x={p.x} y={40} w={160} h={80} title={p.name} lines={[p.sub]} tone="brand" />
        ))}
        <Box x={790} y={40} w={150} h={80} title="Rules only" lines={["no AI, last resort"]} />

        <Edge d="M150,80 L188,80" dur={1.2} />
        <Edge d="M350,80 L388,80" warn dur={1.4} label="limit / error" lx={370} ly={30} />
        <Edge d="M550,80 L588,80" warn dur={1.4} label="limit / error" lx={570} ly={30} />
        <Edge d="M750,80 L788,80" warn dur={1.4} label="all down" lx={770} ly={30} />

        {[270, 470, 670, 865].map((x) => (
          <Edge key={x} d={`M${x},120 L${x},198`} dur={1.6} />
        ))}

        <rect x={190} y={200} width={750} height={100} rx={12} fill="#ffffff" stroke="#d4d4cf" strokeWidth={1.5} />
        {[
          { x: 300, t: "1. Check", s: ["JSON + allowed values;", "bad answer → retry once"] },
          { x: 565, t: "2. Guards", s: ["fix clear mistakes", "(\"Intern\" → internship)"] },
          { x: 820, t: "3. Save", s: ["tags + every token,", "10 jobs at a time"] },
        ].map((c) => (
          <g key={c.t}>
            <text x={c.x} y={232} textAnchor="middle" fontSize={15} fontWeight={700}>
              {c.t}
            </text>
            {c.s.map((line, i) => (
              <text key={line} x={c.x} y={255 + i * 19} textAnchor="middle" fontSize={13} className="muted">
                {line}
              </text>
            ))}
          </g>
        ))}
        <Edge d="M400,250 L455,250" dur={1.4} />
        <Edge d="M675,250 L720,250" dur={1.4} />
      </svg>
    </Frame>
  );
}

export function RequestFlowDiagram() {
  const lanes = [
    { x: 100, name: "Student's browser" },
    { x: 360, name: "Next.js (Vercel)" },
    { x: 620, name: "Spring API (Render)" },
    { x: 860, name: "Postgres (Neon)" },
  ];
  const steps: { from: number; to: number; y: number; text: string; back?: boolean }[] = [
    { from: 100, to: 360, y: 110, text: "1. Open /jobs?city=Pune" },
    { from: 360, to: 620, y: 160, text: "2. GET /api/jobs (+ visitor IP, signed)" },
    { from: 620, to: 860, y: 210, text: "3. SQL: filters + full-text search" },
    { from: 860, to: 620, y: 260, text: "4. Matching rows", back: true },
    { from: 620, to: 360, y: 310, text: "5. JSON page of jobs", back: true },
    { from: 360, to: 100, y: 360, text: "6. HTML with a fresh CSP nonce", back: true },
  ];
  return (
    <Frame label="Request flow diagram" minWidth={720}>
      <svg viewBox="0 0 960 400" className="diagram" role="img" aria-labelledby="req-t req-d">
        <title id="req-t">What happens when a student searches</title>
        <desc id="req-d">
          The browser asks the Next.js server for a page. Next.js calls the Spring API, which runs one SQL query on
          Postgres. The rows come back as JSON and Next.js returns finished HTML.
        </desc>
        <Markers />
        {lanes.map((l) => (
          <g key={l.name}>
            <rect x={l.x - 90} y={20} width={180} height={44} rx={10} fill="#eef0fd" stroke={BRAND} strokeWidth={1.5} />
            <text x={l.x} y={48} textAnchor="middle" fontSize={14} fontWeight={700}>
              {l.name}
            </text>
            <line x1={l.x} y1={64} x2={l.x} y2={385} stroke="#d4d4cf" strokeWidth={2} strokeDasharray="2 6" />
          </g>
        ))}
        {steps.map((s, i) => {
          const d = `M${s.from},${s.y} L${s.to + (s.to > s.from ? -4 : 4)},${s.y}`;
          return (
            <g key={s.text}>
              <Edge d={d} dur={1.6} slow={s.back} />
              <text x={(s.from + s.to) / 2} y={s.y - 10} textAnchor="middle" fontSize={13}>
                {s.text}
              </text>
              <circle cx={s.from} cy={s.y} r={5} fill={BRAND} className="pulse-ring" style={{ animationDelay: `${i * 0.3}s` }} />
            </g>
          );
        })}
      </svg>
    </Frame>
  );
}

const INGEST_STEPS = [
  ["Fetch", "Call each job API. One failing source never stops the rest."],
  ["Filter", "Keep jobs in India with a fresher signal (intern, trainee, 0–1 yrs…)."],
  ["De-duplicate", "Same role, company and city from two sources = one job."],
  ["Skip unchanged", "A hash of title + company + text. Same hash → no AI call."],
  ["Tag with AI", "Only new or changed jobs. Free models, in order."],
  ["Guard + save", "Fix clear mistakes, save every 10 jobs, count every token."],
  ["Hide old jobs", "Missing from its source two runs in a row → hidden."],
  ["Record the run", "Counts, errors and cost go into ingest_runs."],
];

/** The daily run as a strip of steps; a highlight walks along them on a loop. */
export function IngestSteps() {
  return (
    <ol className="step-strip grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Daily ingest steps">
      {INGEST_STEPS.map(([title, text], i) => (
        <li key={title} className="rounded-lg border bg-card p-4" style={{ animationDelay: `${i}s` }}>
          <p className="flex items-center gap-2 font-bold">
            <span className="grid size-7 shrink-0 place-items-center rounded-full bg-accent-yellow text-sm">{i + 1}</span>
            {title}
          </p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{text}</p>
        </li>
      ))}
    </ol>
  );
}

const TABLES: { name: string; what: string; cols: string[] }[] = [
  { name: "sources", what: "One row per job API or company board", cols: ["key", "type", "config_json", "enabled"] },
  {
    name: "jobs",
    what: "Every posting we have seen",
    cols: ["title, company, location", "apply_url", "content_hash", "dedupe_key", "canonical_job_id", "is_active"],
  },
  {
    name: "job_tags",
    what: "The AI's labels for a job",
    cols: ["role_category, city, state", "work_mode, job_type", "experience_min / max", "is_fresher", "model, prompt_version", "input / output tokens"],
  },
  { name: "ingest_runs", what: "One row per daily run", cols: ["fetched, new, updated", "deactivated, tagged", "llm_cost_usd", "errors_json"] },
  { name: "users", what: "Student accounts", cols: ["email", "password_hash (bcrypt)", "provider (local / Google)"] },
  { name: "saved_jobs + apply_clicks", what: "What a student saved and applied to", cols: ["user_id → users", "job_id → jobs", "time"] },
];

export function DataModel() {
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {TABLES.map((t) => (
        <li key={t.name} className="rounded-lg border bg-card p-4">
          <p className="font-mono text-sm font-bold text-brand">{t.name}</p>
          <p className="mt-1 text-sm text-muted-foreground">{t.what}</p>
          <ul className="mt-3 grid gap-1 text-sm">
            {t.cols.map((c) => (
              <li key={c} className="rounded bg-muted px-2 py-1 font-mono text-[13px]">
                {c}
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}
