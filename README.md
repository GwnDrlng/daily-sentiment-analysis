# Daily Sentiment Analysis

Most people who want to stay current on product and AI read more. They subscribe to another newsletter, follow another thread, save another link they will never reopen. The result is not insight. It is volume. A product leader who consumes everything and synthesizes nothing has traded judgment for exposure, and the market rewards judgment.

This project inverts that. It is a daily strategic intelligence agent that scans the noise so a human does not have to, and returns a five-minute executive briefing built around signal rather than coverage.

The hard part was never gathering the news. Aggregation is a solved problem. The hard part is discrimination, separating an early structural shift from a viral LinkedIn post that will be forgotten by Thursday, and doing it consistently enough that the reader learns to trust the filter. A briefing that surfaces everything relevant is a briefing that surfaces nothing useful.

So the agent operates like an analyst rather than a feed. It runs across Reddit, Hacker News, X, GitHub, Product Hunt, research papers, funding news, and earnings calls, then classifies what it finds. It reads momentum on a scale from rapidly emerging through declining, it reads sentiment alongside the reason the sentiment exists, and it reads enterprise relevance and hype risk. It weights an enterprise case study above a thousand reposts on purpose. Good intelligence is mostly a discipline of what you refuse to include.

The topical focus sits where product management and AI are actually reshaping how teams work, meaning AI for PM, agentic and autonomous workflows, product-led growth, and the operating-model changes underneath them. It watches the companies driving that conversation, from OpenAI and Anthropic to Linear, Figma, Cursor, and Notion, and adds new entrants as their momentum earns the attention.

## What's here

- `agent/instructions.md` holds the agent's operating instructions: objective, methodology, source weighting, and the HTML output format.
- `agent/` is the Vercel Eve agent — model wiring, tools (web search, archive, Slack), the daily schedule, and the HTTP channel.
- `briefings/` holds dated intelligence briefings, rendered as standalone HTML and published via GitHub Pages.
- `CLAUDE.md` is the developer guide for running and deploying the agent.
- The root-level `.md` and `.html` files are an early briefing kept for longitudinal comparison.

## How it runs

The agent is built on the [Vercel Eve](https://vercel.com) framework and runs autonomously on a daily 6am ET cron. Each run it researches the web with Tavily, drafts the briefing with GLM 5.2 (via Ollama Cloud), commits the styled HTML into `briefings/`, and posts the published GitHub Pages link to Slack for review. Follow the Quickstart to run your own; `CLAUDE.md` is the developer reference.

## Quickstart

### 0. Prerequisites

- **Node 24** and npm.
- A **Vercel** account and the CLI: `npm i -g vercel`.
- Accounts for the four services below (Ollama, Tavily, Slack, GitHub).

### 1. Install

```bash
git clone https://github.com/mthistle/daily-sentiment-analysis.git
cd daily-sentiment-analysis
npm install
```

### 2. Get your keys

Copy the template, then fill in `.env.local` (it's gitignored — secrets never get committed):

```bash
cp .env.example .env.local
```

| Var | Where to get it |
| --- | --- |
| `OLLAMA_API_KEY` | [ollama.com/settings/keys](https://ollama.com/settings/keys). Needs Ollama Cloud access to the `glm-5.2:cloud` model. |
| `TAVILY_API_KEY` | Sign up at [app.tavily.com](https://app.tavily.com) — the free tier is enough to start. |
| `SLACK_WEBHOOK_URL` | Create a Slack app → **Incoming Webhooks** → *Add New Webhook* for your review channel ([api.slack.com/apps](https://api.slack.com/apps)). Use a test channel first. |
| `GITHUB_TOKEN` | A [fine-grained PAT](https://github.com/settings/tokens?type=beta) with **Contents: Read and write** on your fork of this repo. |
| `GITHUB_REPO` | Your repo as `owner/repo` (e.g. `mthistle/daily-sentiment-analysis`). |
| `ROUTE_AUTH_BASIC_PASSWORD` | Any secret you choose — it protects manual triggers of the deployed agent. |

Then enable **GitHub Pages** on the repo: *Settings → Pages → Source: Deploy from a branch → `main` / `/(root)`*. That's what makes the Slack link resolve.

### 3. Connect to Vercel

```bash
vercel login
vercel link
```

`vercel link` creates the `.vercel/project.json` link between this directory and a Vercel project.

### 4. Test locally

Start the dev runtime in one terminal:

```bash
npm run dev
```

`eve dev` never fires schedules on their cron cadence, so trigger today's run once, out of band, from a second terminal:

```bash
curl -X POST http://localhost:3000/eve/v1/dev/schedules/daily-briefing
```

Watch the run search the web, commit `briefings/briefing-<date>.html`, and post the Pages link to Slack. Confirm the message lands and the linked page renders.

### 5. Deploy

Add each secret from step 2 to the Vercel project (Production environment), via the dashboard or the CLI:

```bash
vercel env add OLLAMA_API_KEY production
# ...repeat for TAVILY_API_KEY, SLACK_WEBHOOK_URL, GITHUB_TOKEN, GITHUB_REPO, ROUTE_AUTH_BASIC_PASSWORD
```

Then deploy:

```bash
vercel deploy --prod
```

The daily 6am ET cron is generated from `agent/schedules/daily-briefing.ts` automatically — no `vercel.json`. Smoke-test the live app with `curl https://<your-app>/eve/v1/health`, or force a run without waiting for the cron:

```bash
curl -u $ROUTE_AUTH_BASIC_USER:$ROUTE_AUTH_BASIC_PASSWORD \
  -X POST https://<your-app>/eve/v1/session \
  -H 'content-type: application/json' \
  -d '{"message":"Run today'\''s briefing now."}'
```

## How it reads

Each briefing opens with a short executive summary covering the three-to-five highest-signal developments, what is accelerating, and what is weakening. From there it moves through emerging trends, contrarian debates, fatiguing narratives, a tools-to-watch list, and the strategic implications for the next thirty to ninety days. Every claim carries a source. Where confidence is low, the briefing says so instead of rounding up.

## Naming the obvious gap

The automation is now in place — a deployed daily pipeline rather than a person running a prompt. What it still does not do is grade its own longitudinal accuracy: it does not yet measure how often a "rapidly emerging" call held up a month later. I am naming that because the whole premise rests on trusting the filter, and a filter that never grades itself is asking for faith it has not earned. That measurement layer is the next thing worth building.

The methodology is documented in `agent/instructions.md` if you want to see exactly how a topic gets classified, or adapt the weighting to a different domain.
