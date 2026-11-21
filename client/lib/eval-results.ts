/**
 * Accuracy numbers shown on /about and /docs, from eval/score.py plus a written
 * review of every mismatch (eval/out/adjudication.csv). `null` means "not measured
 * yet" and the pages say so: never put an estimate here. Cost is not stored here:
 * /about reads it live from GET /api/meta/tagging.
 */
export const EVAL_RESULTS: {
  measuredOn: string | null;
  model: string | null;
  promptVersion: string | null;
  sampleSize: number | null;
  /** A tag counts as correct when it fits the tagging rules (see `method`). */
  accuracy: { field: string; percent: number }[];
  allFieldsCorrectPercent: number | null;
  /** Exact match with the hand labels, before reviewing the mismatches. */
  strictAllFieldsCorrectPercent: number | null;
  method: string | null;
} = {
  measuredOn: "21 Nov 2026",
  model: "Gemini 3.5 Flash-Lite (26 jobs) and Groq gpt-oss-120b (24 jobs)",
  promptVersion: "v2",
  sampleSize: 50,
  accuracy: [
    { field: "Role", percent: 92 },
    { field: "City", percent: 98 },
    { field: "Work mode", percent: 98 },
    { field: "Job type", percent: 88 },
    { field: "Fresher yes/no", percent: 94 },
  ],
  allFieldsCorrectPercent: 74,
  strictAllFieldsCorrectPercent: 48,
  method:
    "Each of the 33 mismatches was then reviewed against the tagging rules. When both answers fit the rules (for example a hotel front-desk job as 'support' or 'other', since there is no hospitality category), the model's answer counts as correct. 15 tags in 13 jobs were clearly wrong.",
};
