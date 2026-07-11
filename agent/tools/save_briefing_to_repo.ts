import { defineTool } from "eve/tools";
import { z } from "zod";

import { drainSearches } from "../lib/research-log.js";

// Fixed dark-theme shell (stylesheet lifted verbatim from briefings/briefing-2026-06-11.html,
// plus the missing badge-level variants). The CSS never drifts — the model only emits the
// <body> content using these component classes (see agent/instructions.md for the vocabulary).
function renderHtml(title: string, bodyHtml: string, day: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title}</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d27; --surface2: #222536; --border: #2e3148;
    --accent: #6c63ff; --accent2: #00c2a8; --accent3: #f59e0b; --accent4: #ef4444;
    --text: #e8eaf0; --text-muted: #8b8fa8; --text-dim: #5a5d75;
    --green: #22c55e; --yellow: #eab308; --red: #ef4444; --orange: #f97316; --blue: #3b82f6; --purple: #a855f7;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; line-height: 1.7; max-width: 900px; margin: 0 auto; padding: 40px 24px 80px; }
  a { color: var(--accent2); text-decoration: none; border-bottom: 1px solid transparent; transition: border-color 0.15s; }
  a:hover { border-bottom-color: var(--accent2); }
  .header { border-bottom: 1px solid var(--border); padding-bottom: 28px; margin-bottom: 36px; }
  .header-label { font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent); font-weight: 600; margin-bottom: 10px; }
  .header h1 { font-size: 26px; font-weight: 700; color: var(--text); letter-spacing: -0.3px; margin-bottom: 6px; }
  .header-meta { color: var(--text-muted); font-size: 13px; }
  .section-title { font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent); font-weight: 700; margin: 44px 0 18px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
  .exec-summary { background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 8px; padding: 24px 26px; margin-bottom: 8px; }
  .exec-summary h2 { font-size: 15px; font-weight: 700; margin-bottom: 14px; color: var(--text); }
  .signal-row { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 10px; }
  .signal-num { background: var(--accent); color: white; font-size: 11px; font-weight: 700; width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 2px; }
  .signal-text { color: var(--text); line-height: 1.6; }
  .sentiment-bar-container { margin-top: 18px; }
  .sentiment-label { font-size: 12px; color: var(--text-muted); margin-bottom: 6px; }
  .sentiment-bar { height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }
  .sentiment-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, #ef4444 0%, #eab308 40%, #22c55e 75%); width: 64%; }
  .sentiment-caption { font-size: 11px; color: var(--text-muted); margin-top: 5px; }
  .trend-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 22px 24px; margin-bottom: 18px; }
  .trend-title { font-size: 15px; font-weight: 700; color: var(--text); margin-bottom: 10px; }
  .badges { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
  .badge { display: inline-flex; align-items: center; font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; padding: 3px 8px; border-radius: 4px; white-space: nowrap; }
  .badge-label { color: var(--text-muted); font-weight: 400; margin-right: 4px; font-size: 9px; }
  .m-explosive { background: rgba(239,68,68,0.18); color: #f87171; }
  .m-high { background: rgba(245,158,11,0.18); color: #fbbf24; }
  .m-medium { background: rgba(59,130,246,0.18); color: #60a5fa; }
  .m-low { background: rgba(139,143,168,0.18); color: #b6bad0; }
  .s-positive { background: rgba(34,197,94,0.15); color: #4ade80; }
  .s-mixed { background: rgba(234,179,8,0.15); color: #fde047; }
  .s-polarizing { background: rgba(168,85,247,0.15); color: #c084fc; }
  .s-negative { background: rgba(239,68,68,0.15); color: #f87171; }
  .er-high { background: rgba(34,197,94,0.12); color: #4ade80; }
  .er-medium { background: rgba(59,130,246,0.12); color: #60a5fa; }
  .er-low { background: rgba(139,143,168,0.12); color: #b6bad0; }
  .hr-high { background: rgba(239,68,68,0.12); color: #f87171; }
  .hr-medium { background: rgba(245,158,11,0.12); color: #fbbf24; }
  .hr-low { background: rgba(34,197,94,0.12); color: #4ade80; }
  .cl-high { background: rgba(34,197,94,0.12); color: #4ade80; }
  .cl-medium { background: rgba(59,130,246,0.12); color: #60a5fa; }
  .cl-low { background: rgba(245,158,11,0.12); color: #fbbf24; }
  .trend-body p { margin-bottom: 10px; }
  .trend-body strong { font-weight: 600; }
  .field-label { color: var(--text-muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 14px; margin-bottom: 4px; display: block; }
  .contrarian-card { background: var(--surface); border: 1px solid var(--border); border-left: 3px solid #a855f7; border-radius: 8px; padding: 18px 22px; margin-bottom: 16px; }
  .contrarian-card h3 { font-size: 14px; font-weight: 700; color: var(--text); margin-bottom: 10px; }
  .declining-card { background: var(--surface); border: 1px solid var(--border); border-left: 3px solid #f97316; border-radius: 8px; padding: 18px 22px; margin-bottom: 16px; }
  .declining-card h3 { font-size: 14px; font-weight: 700; color: var(--text); margin-bottom: 10px; }
  .watchlist-item { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; }
  .watchlist-name { font-size: 14px; font-weight: 700; color: var(--accent2); margin-bottom: 6px; }
  .implication-block { border-left: 2px solid var(--accent3); padding: 10px 0 10px 16px; margin-bottom: 12px; }
  .implication-type { font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--accent3); font-weight: 700; margin-bottom: 4px; }
  .long-row { display: flex; gap: 10px; align-items: flex-start; margin-bottom: 10px; }
  .long-icon { font-size: 13px; margin-top: 2px; width: 24px; flex-shrink: 0; color: var(--accent2); font-weight: 700; }
  .sources-section { margin-top: 52px; border-top: 1px solid var(--border); padding-top: 24px; }
  .sources-section h2 { font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-muted); font-weight: 700; margin-bottom: 14px; }
  .sources-list { list-style: none; }
  .sources-list li { font-size: 12px; color: var(--text-muted); margin-bottom: 7px; display: flex; gap: 8px; }
  .sources-list li .src-num { color: var(--text-dim); flex-shrink: 0; width: 24px; }
  .sources-list li a { font-size: 12px; color: var(--text-muted); }
  .sources-list li a:hover { color: var(--accent2); }
  .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--border); font-size: 11px; color: var(--text-dim); text-align: center; }
</style>
</head>
<body>
${bodyHtml}
<div class="footer">PM &amp; AI Intelligence Briefing &nbsp;&middot;&nbsp; ${day} &nbsp;&middot;&nbsp; Automated daily run &nbsp;&middot;&nbsp; Signal over noise</div>
</body>
</html>
`;
}

// The model sometimes wraps its output in ```html fences or a full <html> doc.
// Strip that down to just the body content the shell wraps.
export function extractBody(raw: string): string {
  let s = raw.trim();
  s = s.replace(/^```(?:html)?\s*/i, "").replace(/```\s*$/i, "").trim();
  const bodyMatch = s.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  if (bodyMatch) s = bodyMatch[1].trim();
  return s;
}

// GitHub Contents API: create or update one file on the target branch.
async function commitFile(path: string, content: string, message: string): Promise<void> {
  const repo = process.env.GITHUB_REPO!; // owner/repo
  const branch = process.env.GITHUB_BRANCH ?? "main";
  const token = process.env.GITHUB_TOKEN!;
  const api = `https://api.github.com/repos/${repo}/contents/${path}`;
  const headers = {
    authorization: `Bearer ${token}`,
    accept: "application/vnd.github+json",
    "content-type": "application/json",
    "user-agent": "daily-sentiment-analysis-agent",
  };

  // Need the existing blob SHA to update a file that already exists (e.g. same-day re-run).
  let sha: string | undefined;
  const existing = await fetch(`${api}?ref=${branch}`, { headers });
  if (existing.ok) sha = ((await existing.json()) as { sha?: string }).sha;
  else if (existing.status !== 404) throw new Error(`GitHub GET failed: ${existing.status} ${await existing.text()}`);

  const res = await fetch(api, {
    method: "PUT",
    headers,
    body: JSON.stringify({
      message,
      content: Buffer.from(content, "utf8").toString("base64"),
      branch,
      ...(sha ? { sha } : {}),
    }),
  });
  if (!res.ok) throw new Error(`GitHub PUT failed: ${res.status} ${await res.text()}`);
}

export default defineTool({
  description:
    "Archive the finished briefing to the repo. Wraps the HTML <body> content you produced (using the " +
    "briefing component classes) in the fixed stylesheet, commits briefings/briefing-<date>.html, and " +
    "returns the GitHub Pages URL to link in Slack.",
  inputSchema: z.object({
    // The <body> content only — header, section blocks, and sources — using the component classes.
    bodyHtml: z.string().min(1),
    title: z.string().optional(),
    // ponytail: defaults to today's UTC date (run fires ~10:00 UTC = same ET calendar day)
    date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  }),
  async execute({ bodyHtml, title, date }) {
    const day = date ?? new Date().toISOString().slice(0, 10);
    const body = extractBody(bodyHtml);
    const h1 = body.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i)?.[1].replace(/<[^>]+>/g, "").trim();
    const docTitle = title ?? h1 ?? `PM & AI Intelligence Briefing — ${day}`;

    const html = renderHtml(docTitle, body, day);
    const htmlPath = `briefings/briefing-${day}.html`;
    await commitFile(htmlPath, html, `Add briefing ${day}`);

    // Freeze this run's research as a replay case — the offline optimizer
    // (python -m rigor.optimize) trains agent/instructions.md against these.
    // Best-effort: a failed case commit must not lose the briefing archive.
    const searches = drainSearches();
    let caseSaved = false;
    if (searches.length > 0) {
      try {
        await commitFile(
          `evals/cases/case-${day}.json`,
          JSON.stringify({ date: day, capturedAt: new Date().toISOString(), searches }, null, 2),
          `Add replay case ${day}`,
        );
        caseSaved = true;
      } catch (err) {
        console.error(`replay case commit failed for ${day}:`, err);
      }
    }

    // GitHub Pages (main /root): https://<owner>.github.io/<repo>/<path>
    // ponytail: Pages redeploys after the commit, so the link may 404 for ~1 min.
    const [owner, name] = process.env.GITHUB_REPO!.split("/");
    const htmlUrl = `https://${owner}.github.io/${name}/${htmlPath}`;

    return { htmlUrl, date: day, caseSaved };
  },
});
