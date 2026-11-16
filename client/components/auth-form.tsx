"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { apiSend, HttpError } from "@/lib/client-api";
import { useAuth } from "./auth-provider";

/** Only same-site relative paths are accepted as a post-login destination. */
function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\")
    ? value
    : "/dashboard";
}

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(
    params.get("error") === "oauth" ? "Google sign-in did not complete. Please try again." : null,
  );
  const [notice, setNotice] = useState<string | null>(
    params.get("registered") ? "If that email was not registered yet, your account is ready. Log in below." : null,
  );
  const isRegister = mode === "register";

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (isRegister) {
        await apiSend("POST", "/api/auth/register", { email, password, name: String(form.get("name") ?? "") });
        router.push("/login?registered=1");
      } else {
        await apiSend("POST", "/api/auth/login", { email, password });
        await refresh();
        router.push(safeNext(params.get("next")));
        router.refresh();
      }
    } catch (e) {
      if (e instanceof HttpError && e.status === 429) {
        setError("Too many attempts. Wait a minute and try again.");
      } else if (e instanceof HttpError && e.status === 400) {
        setError("Check the form: a valid email and a password of at least 10 characters are required.");
      } else if (e instanceof HttpError && e.status === 401) {
        setError("Invalid email or password.");
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="display text-3xl">{isRegister ? "Create your account" : "Welcome back"}</h1>
      <p className="mt-3 text-muted-foreground">
        {isRegister ? "Save jobs and keep track of where you applied." : "Log in to see your saved and applied jobs."}
      </p>

      <div className="card mt-6 p-6">
        {/* A normal navigation (not fetch): the API redirects to Google and back. */}
        <a href="/oauth2/authorization/google" className="btn btn-secondary w-full">
          Continue with Google
        </a>
        <p className="my-4 text-center text-sm text-muted-foreground">or use your email</p>

        <form onSubmit={onSubmit} className="grid gap-4" noValidate={false}>
          {isRegister && (
            <div>
              <label htmlFor="name" className="mb-1 block text-sm font-semibold">
                Full name
              </label>
              <input id="name" name="name" required maxLength={80} autoComplete="name" className="field" />
            </div>
          )}
          <div>
            <label htmlFor="email" className="mb-1 block text-sm font-semibold">
              Email
            </label>
            <input id="email" name="email" type="email" required maxLength={254} autoComplete="email" className="field" />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-semibold">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              minLength={isRegister ? 10 : undefined}
              maxLength={128}
              autoComplete={isRegister ? "new-password" : "current-password"}
              aria-describedby={isRegister ? "password-hint" : undefined}
              className="field"
            />
            {isRegister && (
              <p id="password-hint" className="mt-1 text-sm text-muted-foreground">
                At least 10 characters.
              </p>
            )}
          </div>
          {notice && (
            <p role="status" className="rounded-md bg-brand-soft px-3 py-2 text-sm">
              {notice}
            </p>
          )}
          {error && (
            <p role="alert" className="rounded-md bg-[#fdeceb] px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
          <button type="submit" disabled={busy} className="btn btn-primary w-full">
            {busy ? "Please wait…" : isRegister ? "Create account" : "Log in"}
          </button>
        </form>
      </div>

      <p className="mt-4 text-center text-sm">
        {isRegister ? "Already have an account? " : "New here? "}
        <Link href={isRegister ? "/login" : "/register"} className="font-semibold text-brand underline-offset-4 hover:underline">
          {isRegister ? "Log in" : "Create an account"}
        </Link>
      </p>
    </div>
  );
}
