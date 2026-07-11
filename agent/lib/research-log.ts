// In-memory log of the current run's web searches, drained into a replay case
// when the briefing is archived (evals/cases/case-<date>.json). Replay cases are
// what the offline optimizer (python -m rigor.optimize) trains the prompt against.

export type SearchRecord = {
  query: string;
  results: { title: string; url: string; content: string }[];
  at: string; // ISO timestamp
};

// A warm serverless instance can survive between runs; entries older than this
// belong to a previous run and are dropped at drain time.
const MAX_AGE_MS = 6 * 60 * 60 * 1000;

const log: SearchRecord[] = [];

export function recordSearch(entry: Omit<SearchRecord, "at">): void {
  log.push({ ...entry, at: new Date().toISOString() });
}

export function drainSearches(): SearchRecord[] {
  const cutoff = Date.now() - MAX_AGE_MS;
  const drained = log.splice(0);
  return drained.filter((s) => Date.parse(s.at) >= cutoff);
}
