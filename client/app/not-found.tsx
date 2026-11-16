import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <h1 className="display text-3xl">Page not found</h1>
      <p className="mt-3 text-muted-foreground">
        This page does not exist, or the job has been removed.
      </p>
      <Link href="/jobs" className="btn btn-primary mt-6">
        Browse jobs
      </Link>
    </div>
  );
}
