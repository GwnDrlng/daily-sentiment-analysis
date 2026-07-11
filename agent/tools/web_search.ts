import { defineTool } from "eve/tools";
import { z } from "zod";

import { recordSearch } from "../lib/research-log.js";

// Tavily web search — grounds the briefing in real, citable sources.
// GLM 5.2 has no internet on its own; the agent calls this many times per run.
export default defineTool({
  description:
    "Search the web for fresh, citable sources. Returns ranked results with title, URL, and a content excerpt. " +
    "Call repeatedly with focused queries to gather evidence across topics before writing the briefing.",
  inputSchema: z.object({
    query: z.string().min(1),
    max_results: z.number().int().min(1).max(20).default(8),
  }),
  async execute({ query, max_results }) {
    const res = await fetch("https://api.tavily.com/search", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${process.env.TAVILY_API_KEY!}`,
      },
      body: JSON.stringify({
        query,
        max_results,
        search_depth: "advanced",
        include_raw_content: true,
        topic: "news",
        days: 7, // ponytail: fixed recency window; widen if a topic needs deeper history
      }),
    });
    if (!res.ok) throw new Error(`Tavily search failed: ${res.status} ${await res.text()}`);
    const data = (await res.json()) as {
      results?: { title: string; url: string; content: string; raw_content?: string | null }[];
    };
    const results = (data.results ?? []).map((r) => ({
      title: r.title,
      url: r.url,
      // raw_content is fuller but can be huge; cap it so we don't blow the context window.
      content: (r.raw_content ?? r.content ?? "").slice(0, 4000),
    }));
    recordSearch({
      query,
      // Replay cases only need enough excerpt to reconstruct the evidence.
      results: results.map((r) => ({ ...r, content: r.content.slice(0, 1500) })),
    });
    return { results };
  },
});
