"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiSend, HttpError } from "@/lib/client-api";
import type { UserJob } from "@/lib/types";
import { useAuth } from "./auth-provider";

/**
 * Apply = open the employer's own posting in a new tab. It is a real link (so
 * it survives pop-up blockers and middle-click); the click is recorded in the
 * background so the job shows up under "Applied" in the dashboard.
 */
export function ApplyButton({ jobId, applyUrl }: { jobId: string; applyUrl: string | null }) {
  const [clicked, setClicked] = useState(false);
  if (!applyUrl) {
    return <p className="text-sm text-muted-foreground">This posting has no valid apply link.</p>;
  }
  return (
    <div>
      <a
        href={applyUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="btn btn-primary w-full sm:w-auto"
        onClick={() => {
          setClicked(true);
          apiSend("POST", `/api/jobs/${jobId}/apply`, undefined, { keepalive: true }).catch(() => {});
        }}
      >
        Apply on company site
        <span className="sr-only"> (opens in a new tab)</span>
        <span aria-hidden="true">↗</span>
      </a>
      <p className="mt-2 text-sm text-muted-foreground" aria-live="polite">
        {clicked
          ? "Opened in a new tab. Finish the application there."
          : "You apply on the employer's own page. We only keep a note that you clicked."}
      </p>
    </div>
  );
}

export function SaveButton({ jobId }: { jobId: string }) {
  const { me } = useAuth();
  const router = useRouter();
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!me?.authenticated) return;
    let cancelled = false;
    apiGet<UserJob[]>("/api/me/saved")
      .then((list) => {
        if (!cancelled) setSaved(list.some((entry) => entry.job.id === jobId));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [me, jobId]);

  async function toggle() {
    if (!me?.authenticated) {
      router.push(`/login?next=${encodeURIComponent(`/jobs/${jobId}`)}`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await apiSend(saved ? "DELETE" : "POST", `/api/jobs/${jobId}/save`);
      setSaved(!saved);
    } catch (e) {
      setError(e instanceof HttpError && e.status === 401 ? "Please log in again." : "Could not save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={toggle}
        disabled={busy || me === null}
        aria-pressed={saved}
        className="btn btn-secondary w-full sm:w-auto"
      >
        {saved ? "Saved ✓" : "Save job"}
      </button>
      {error && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
