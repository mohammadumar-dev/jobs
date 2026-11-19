"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BRAND } from "@/lib/brand";
import { useAuth } from "./auth-provider";

export function Logo() {
  return (
    <span className="flex items-center gap-2 text-lg font-bold">
      <span
        aria-hidden="true"
        className="grid size-8 place-items-center rounded-full bg-accent-yellow text-sm font-extrabold"
      >
        1
      </span>
      {BRAND.name}
    </span>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = pathname === href || pathname.startsWith(`${href}/`);
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`rounded-md px-2 py-2 text-[15px] font-semibold hover:text-brand ${
        active ? "text-brand" : "text-[#414651]"
      }`}
    >
      {children}
    </Link>
  );
}

export function SiteHeader() {
  const { me, logout } = useAuth();
  const router = useRouter();

  async function onLogout() {
    await logout();
    router.push("/");
    router.refresh();
  }

  return (
    <header className="px-4 pt-3">
      <nav
        aria-label="Main"
        className="card mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 rounded-[10px] px-4 py-2"
      >
        <Link href="/" aria-label={`${BRAND.name} home`} className="mr-2 rounded-md">
          <Logo />
        </Link>
        <NavLink href="/jobs">Jobs</NavLink>
        <NavLink href="/about">About</NavLink>
        <div className="ml-auto flex items-center gap-2">
          {me === null ? (
            <span className="h-10 w-24" aria-hidden="true" />
          ) : me.authenticated ? (
            <>
              <NavLink href="/dashboard">Dashboard</NavLink>
              <button type="button" onClick={onLogout} className="btn btn-secondary btn-sm">
                Log out
              </button>
            </>
          ) : (
            <>
              <NavLink href="/login">Log in</NavLink>
              <Link href="/register" className="btn btn-primary btn-sm">
                Sign up
              </Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t px-4 py-8 text-sm text-muted-foreground">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
        <p>
          {BRAND.name} links to each employer&apos;s own posting. We never apply on your behalf.{" "}
          <a href="https://www.adzuna.in" className="underline underline-offset-4" rel="noopener">
            Jobs by Adzuna
          </a>
          .
        </p>
        <nav aria-label="Footer" className="flex gap-4">
          <Link href="/jobs" className="underline-offset-4 hover:underline">
            Browse jobs
          </Link>
          <Link href="/about" className="underline-offset-4 hover:underline">
            Sources and method
          </Link>
        </nav>
      </div>
    </footer>
  );
}
