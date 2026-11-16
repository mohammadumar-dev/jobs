"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/client-api";
import { formatDate } from "@/lib/format";
import type { UserJob } from "@/lib/types";
import { useAuth } from "./auth-provider";
import { JobCard } from "./job-card";

const TABS = [
  { id: "saved", text: "Saved", path: "/api/me/saved", verb: "Saved", empty: "You have not saved any jobs yet." },
  { id: "applied", text: "Applied", path: "/api/me/applied", verb: "Apply clicked", empty: "Jobs you click apply on will show up here." },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function Dashboard() {
  const { me } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<TabId>("saved");
  const [lists, setLists] = useState<Record<TabId, UserJob[]> | null>(null);
  const [failed, setFailed] = useState(false);
  const [now] = useState(() => Date.now());

  useEffect(() => {
    if (me === null) return;
    if (!me.authenticated) {
      router.replace("/login?next=/dashboard");
      return;
    }
    Promise.all([apiGet<UserJob[]>(TABS[0].path), apiGet<UserJob[]>(TABS[1].path)])
      .then(([saved, applied]) => setLists({ saved, applied }))
      .catch(() => setFailed(true));
  }, [me, router]);

  if (!me?.authenticated) {
    return <p role="status">Loading your dashboard…</p>;
  }

  const current = TABS.find((t) => t.id === tab)!;
  const items = lists?.[tab];

  return (
    <>
      <h1 className="display text-3xl">Hi {me.name?.split(" ")[0] ?? "there"}</h1>
      <p className="mt-2 text-muted-foreground">Signed in as {me.email}</p>

      <div role="tablist" aria-label="Your jobs" className="mt-6 flex gap-2 border-b">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls="tab-panel"
            onClick={() => setTab(t.id)}
            className={`-mb-px min-h-11 border-b-2 px-4 font-semibold ${
              tab === t.id ? "border-brand text-brand" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.text}
            {lists && <span className="ml-2 text-sm font-medium">{lists[t.id].length}</span>}
          </button>
        ))}
      </div>

      <div id="tab-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="mt-6">
        {failed ? (
          <p role="alert" className="card p-6">
            Your jobs could not be loaded. Please refresh the page.
          </p>
        ) : !items ? (
          <p role="status">Loading…</p>
        ) : items.length === 0 ? (
          <div className="card p-8 text-center">
            <p className="font-semibold">{current.empty}</p>
            <Link href="/jobs" className="btn btn-primary mt-5">
              Browse jobs
            </Link>
          </div>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((entry) => (
              <li key={entry.job.id}>
                <JobCard job={entry.job} now={now} note={`${current.verb} ${formatDate(entry.at)}`} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
