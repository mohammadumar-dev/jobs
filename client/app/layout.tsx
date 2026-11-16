import type { Metadata } from "next";
import { Albert_Sans, Unbounded } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";
import { AuthProvider } from "@/components/auth-provider";
import { SiteFooter, SiteHeader } from "@/components/site-header";
import { BRAND } from "@/lib/brand";

const albert = Albert_Sans({ subsets: ["latin"], variable: "--font-albert" });
const unbounded = Unbounded({ subsets: ["latin"], weight: ["700"], variable: "--font-unbounded" });

export const metadata: Metadata = {
  title: { default: `${BRAND.name} - fresher jobs and internships in India`, template: `%s | ${BRAND.name}` },
  description: BRAND.tagline,
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  // Reading a request header makes every page render per request, which the
  // nonce-based CSP from proxy.ts requires (Next.js picks the nonce up itself).
  await headers();

  return (
    <html lang="en-IN" className={`${albert.variable} ${unbounded.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <AuthProvider>
          <SiteHeader />
          <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
            {children}
          </main>
          <SiteFooter />
        </AuthProvider>
      </body>
    </html>
  );
}
