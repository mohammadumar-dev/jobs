"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";

export type Screenshot = {
  src: string;
  w: number;
  h: number;
  title: string;
  text: string;
  /** Phone screenshots are shown narrower so they are not blown up to full width. */
  phone?: boolean;
};

/**
 * Thumbnail grid plus a viewer: a native modal <dialog> (focus trap, Esc to close,
 * background made inert by the browser) with previous/next buttons, arrow keys and swipe.
 */
export function ScreenshotGallery({ shots }: { shots: Screenshot[] }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [index, setIndex] = useState<number | null>(null);
  const touchX = useRef<number | null>(null);

  const open = (i: number) => {
    setIndex(i);
    dialog.current?.showModal();
  };
  const close = () => dialog.current?.close();
  const step = useCallback(
    (delta: number) => setIndex((i) => (i === null ? i : (i + delta + shots.length) % shots.length)),
    [shots.length],
  );

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") step(1);
      if (e.key === "ArrowLeft") step(-1);
    };
    const onClose = () => setIndex(null);
    el.addEventListener("keydown", onKey);
    el.addEventListener("close", onClose);
    return () => {
      el.removeEventListener("keydown", onKey);
      el.removeEventListener("close", onClose);
    };
  }, [step]);

  const shot = index === null ? null : shots[index];

  return (
    <>
      <ul className="grid gap-6 md:grid-cols-2">
        {shots.map((s, i) => (
          <li key={s.src} className="card overflow-hidden">
            <button
              type="button"
              onClick={() => open(i)}
              className="group relative block w-full cursor-zoom-in overflow-hidden border-b bg-muted"
              aria-label={`Open screenshot: ${s.title}`}
            >
              <span className={`block h-[300px] overflow-hidden ${s.phone ? "flex justify-center pt-4" : ""}`}>
                <Image
                  src={s.src}
                  width={s.w}
                  height={s.h}
                  alt=""
                  sizes="(min-width: 768px) 50vw, 100vw"
                  className={`h-auto transition-transform duration-300 group-hover:scale-[1.02] ${
                    s.phone ? "w-44 rounded-lg border" : "w-full"
                  }`}
                />
              </span>
              <span className="absolute right-3 bottom-3 rounded-md bg-foreground/80 px-2 py-1 text-xs font-semibold text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                View larger
              </span>
            </button>
            <div className="p-4">
              <p className="font-bold">{s.title}</p>
              <p className="text-sm text-muted-foreground">{s.text}</p>
            </div>
          </li>
        ))}
      </ul>

      <dialog
        ref={dialog}
        aria-label={shot ? `Screenshot ${index! + 1} of ${shots.length}: ${shot.title}` : "Screenshot viewer"}
        className="m-auto h-[100dvh] max-h-none w-full max-w-none bg-transparent p-0 backdrop:bg-black/85"
        onClick={(e) => {
          if (e.target === e.currentTarget) close();
        }}
        onTouchStart={(e) => {
          touchX.current = e.touches[0].clientX;
        }}
        onTouchEnd={(e) => {
          if (touchX.current === null) return;
          const dx = e.changedTouches[0].clientX - touchX.current;
          touchX.current = null;
          if (Math.abs(dx) > 50) step(dx < 0 ? 1 : -1);
        }}
      >
        {shot && (
          <div className="flex h-full flex-col text-white" onClick={(e) => e.target === e.currentTarget && close()}>
            <header className="flex items-center justify-between gap-4 px-4 py-3">
              <p className="text-sm tabular-nums text-[#d4d4d4]" aria-live="polite">
                {index! + 1} / {shots.length}
              </p>
              <button type="button" onClick={close} className="btn btn-sm bg-white/10 text-white hover:bg-white/20">
                Close <span aria-hidden="true">✕</span>
              </button>
            </header>

            <div className="relative flex min-h-0 flex-1 items-center gap-2 px-2 sm:px-4">
              <NavButton label="Previous screenshot" onClick={() => step(-1)} dir="prev" />
              <div
                key={shot.src}
                className="viewer-fade mx-auto max-h-full min-h-0 w-full overflow-auto rounded-lg"
                style={{ maxWidth: shot.phone ? 420 : 1280 }}
                tabIndex={0}
                aria-label="Screenshot, scroll to see all of it"
              >
                <Image
                  src={shot.src}
                  width={shot.w}
                  height={shot.h}
                  alt={`${shot.title} screenshot`}
                  sizes="(min-width: 1280px) 1280px, 100vw"
                  className="h-auto w-full"
                  priority
                />
              </div>
              <NavButton label="Next screenshot" onClick={() => step(1)} dir="next" />
            </div>

            <footer className="px-4 py-3 text-center">
              <p className="font-bold">{shot.title}</p>
              <p className="text-sm text-[#d4d4d4]">{shot.text}</p>
              <ol className="mt-3 flex justify-center gap-2" aria-label="Jump to screenshot">
                {shots.map((s, i) => (
                  <li key={s.src}>
                    <button
                      type="button"
                      onClick={() => setIndex(i)}
                      aria-label={`Show ${s.title}`}
                      aria-current={i === index ? "true" : undefined}
                      className={`block size-2.5 rounded-full transition-colors ${
                        i === index ? "bg-white" : "bg-white/35 hover:bg-white/60"
                      }`}
                    />
                  </li>
                ))}
              </ol>
            </footer>
          </div>
        )}
      </dialog>
    </>
  );
}

function NavButton({ label, onClick, dir }: { label: string; onClick: () => void; dir: "prev" | "next" }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={`absolute top-1/2 z-10 grid size-11 -translate-y-1/2 place-items-center rounded-full bg-white/90 text-xl font-bold text-foreground shadow-lg hover:bg-white sm:static sm:translate-y-0 ${
        dir === "prev" ? "left-3" : "right-3"
      }`}
    >
      <span aria-hidden="true">{dir === "prev" ? "‹" : "›"}</span>
    </button>
  );
}
