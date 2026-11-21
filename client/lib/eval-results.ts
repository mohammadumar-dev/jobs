/**
 * Accuracy numbers shown on /about and /docs, from eval/score.py plus a written
 * review of every mismatch (eval/out/adjudication_v3.csv). `null` means "not
 * measured yet" and the pages say so: never put an estimate here. Cost is not
 * stored here: /about reads it live from GET /api/meta/tagging.
 */
export const EVAL_RESULTS: {
  measuredOn: string | null;
  model: string | null;
  promptVersion: string | null;
  sampleSize: number | null;
  /** A tag counts as correct when it fits the tagging rules (see `method`). */
  accuracy: { field: string; percent: number }[];
  /** Share of all tags (jobs x fields) that are correct. */
  tagsCorrectPercent: number | null;
  allFieldsCorrectPercent: number | null;
  /** Exact match with the hand labels, before reviewing the mismatches. */
  strictAllFieldsCorrectPercent: number | null;
  method: string | null;
  /** Caveats and the earlier measurement, shown under the table. */
  history: string | null;
} = {
  measuredOn: "21 Nov 2026",
  model: "Gemini 3.5 Flash-Lite",
  promptVersion: "v3",
  sampleSize: 50,
  accuracy: [
    { field: "Role", percent: 94 },
    { field: "City", percent: 98 },
    { field: "Work mode", percent: 96 },
    { field: "Job type", percent: 100 },
    { field: "Fresher yes/no", percent: 100 },
  ],
  tagsCorrectPercent: 97.6,
  allFieldsCorrectPercent: 88,
  strictAllFieldsCorrectPercent: 52,
  method:
    "Every mismatch was then reviewed against the tagging rules. When both answers fit the rules (mostly hotel jobs, which have no category of their own, as 'other', 'operations' or 'support'), the model's answer counts as correct. 6 tags in 6 jobs were clearly wrong.",
  history:
    "These are the same 50 jobs whose mistakes led to the v3 fixes, so a fresh sample may score a little lower. The first check, with prompt v2, got all fields right on 74% of jobs (48% exact match); most of its errors were \"Graduate Trainee\" jobs tagged as internships and jobs asking for one year of experience marked as not for freshers. Several of the remaining errors are on Adzuna jobs, where only a 500-character preview is available.",
};
