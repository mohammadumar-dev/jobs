/**
 * Accuracy numbers shown on /about, filled in from eval/score.py output (see
 * docs/cost.md). `null` means "not measured yet" and the page says so: never put
 * an estimate here. Cost is not stored here: /about reads it live from
 * GET /api/meta/tagging.
 */
export const EVAL_RESULTS: {
  measuredOn: string | null;
  model: string | null;
  sampleSize: number | null;
  accuracy: { field: string; percent: number }[];
  allFieldsCorrectPercent: number | null;
} = {
  measuredOn: null,
  model: null,
  sampleSize: null,
  accuracy: [],
  allFieldsCorrectPercent: null,
};
