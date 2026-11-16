/**
 * Numbers shown on /about. Filled in from eval/score.py and eval/cost.py output
 * (see docs/cost.md). `null` means "not measured yet" and the page says so:
 * never put an estimate here.
 */
export const EVAL_RESULTS: {
  measuredOn: string | null;
  model: string | null;
  sampleSize: number | null;
  accuracy: { field: string; percent: number }[];
  allFieldsCorrectPercent: number | null;
  costPer1000Usd: number | null;
  costPer1000Inr: number | null;
} = {
  measuredOn: null,
  model: null,
  sampleSize: null,
  accuracy: [],
  allFieldsCorrectPercent: null,
  costPer1000Usd: null,
  costPer1000Inr: null,
};
