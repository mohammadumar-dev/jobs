/**
 * The walkthrough video. Paste the Loom share link here when it is recorded,
 * e.g. "https://www.loom.com/share/0123456789abcdef0123456789abcdef".
 * While it is null, /loom shows a "coming soon" note instead.
 */
export const LOOM_SHARE_URL: string | null = null;

/** Date the note on /loom was written (shown to visitors). */
export const LOOM_NOTE_DATE = "21 Nov 2026";

const LOOM_ID = /^https:\/\/(?:www\.)?loom\.com\/(?:share|embed)\/([0-9a-f]{32})/i;

/** Turns a Loom share link into its embed link, or null if it is not a Loom link. */
export function loomEmbedUrl(shareUrl: string | null): string | null {
  const id = shareUrl?.match(LOOM_ID)?.[1];
  return id ? `https://www.loom.com/embed/${id}` : null;
}
