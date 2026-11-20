"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
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

function NavLink({
  href,
  children,
  onNavigate,
  block = false,
}: {
  href: string;
  children: React.ReactNode;
  onNavigate?: () => void;
  block?: boolean;
}) {
  const pathname = usePathname();
  const active = pathname === href || pathname.startsWith(`${href}/`);
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={`rounded-md font-semibold hover:text-brand ${
        block ? "flex min-h-12 items-center px-3 text-base hover:bg-muted" : "px-2 py-2 text-[15px]"
      } ${active ? "text-brand" : "text-[#414651]"} ${block && active ? "bg-brand-soft" : ""}`}
    >
      {children}
    </Link>
  );
}

const LINKS = [
  ["/jobs", "Jobs"],
  ["/about", "About"],
  ["/docs", "Docs"],
] as const;

export function SiteHeader() {
  const { me, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  // The menu belongs to the page it was opened on, so any navigation closes it.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const menuOpen = openOn === pathname;
  const close = () => setOpenOn(null);

  async function onLogout() {
    close();
    await logout();
    router.push("/");
    router.refresh();
  }

  return (
    <header className="px-4 pt-3">
      <nav
        aria-label="Main"
        className="card mx-auto max-w-6xl rounded-[10px] px-3 py-2 sm:px-4"
        onKeyDown={(e) => {
          if (e.key === "Escape") close();
        }}
      >
        <div className="flex items-center gap-x-4">
          <Link href="/" aria-label={`${BRAND.name} home`} className="mr-2 inline-flex min-h-11 items-center rounded-md" onClick={close}>
            <Logo />
          </Link>
          {/* Wide screens: links in the bar. */}
          <div className="hidden items-center gap-x-4 sm:flex">
            {LINKS.map(([href, text]) => (
              <NavLink key={href} href={href}>
                {text}
              </NavLink>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-2">
            {me === null ? (
              <span className="h-10 w-24" aria-hidden="true" />
            ) : me.authenticated ? (
              <div className="hidden items-center gap-2 sm:flex">
                <NavLink href="/dashboard">Dashboard</NavLink>
                <button type="button" onClick={onLogout} className="btn btn-secondary btn-sm">
                  Log out
                </button>
              </div>
            ) : (
              <>
                <span className="hidden sm:inline">
                  <NavLink href="/login">Log in</NavLink>
                </span>
                <Link href="/register" className="btn btn-primary btn-sm" onClick={close}>
                  Sign up
                </Link>
              </>
            )}
            {/* Phones: one menu button instead of a bar that wraps onto two lines. */}
            <button
              type="button"
              className="grid size-11 place-items-center rounded-[10px] border hover:bg-muted sm:hidden"
              aria-expanded={menuOpen}
              aria-controls="mobile-menu"
              aria-label={menuOpen ? "Close menu" : "Open menu"}
              onClick={() => setOpenOn(menuOpen ? null : pathname)}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
                {menuOpen ? (
                  <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                ) : (
                  <path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                )}
              </svg>
            </button>
          </div>
        </div>

        <div id="mobile-menu" hidden={!menuOpen} className="menu-drop mt-2 border-t pt-2 pb-1 sm:hidden">
          <ul className="grid gap-1">
            {LINKS.map(([href, text]) => (
              <li key={href}>
                <NavLink href={href} onNavigate={close} block>
                  {text}
                </NavLink>
              </li>
            ))}
            {me?.authenticated ? (
              <>
                <li>
                  <NavLink href="/dashboard" onNavigate={close} block>
                    Dashboard
                  </NavLink>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={onLogout}
                    className="flex min-h-12 w-full items-center rounded-md px-3 text-left text-base font-semibold text-[#414651] hover:bg-muted"
                  >
                    Log out
                  </button>
                </li>
              </>
            ) : (
              <li>
                <NavLink href="/login" onNavigate={close} block>
                  Log in
                </NavLink>
              </li>
            )}
          </ul>
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
        <nav aria-label="Footer" className="-mx-2 flex flex-wrap">
          {[
            ["/jobs", "Browse jobs"],
            ["/about", "Sources and method"],
            ["/docs", "Project docs"],
            ["/loom", "Video walkthrough"],
          ].map(([href, text]) => (
            <Link
              key={href}
              href={href}
              className="inline-flex min-h-11 items-center px-2 underline-offset-4 hover:underline"
            >
              {text}
            </Link>
          ))}
        </nav>
      </div>
    </footer>
  );
}
