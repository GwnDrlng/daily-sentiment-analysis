import { defineSchedule } from "eve/schedules";

export default defineSchedule({
  cron: "0 10 * * *", // 6am EDT / 5am EST — 10:00 UTC daily (Vercel cron is fixed-UTC)
  markdown:
    "Produce today's Daily PM & AI Strategic Intelligence Briefing following your instructions. " +
    "First research the priority topics and companies with the web_search tool, running many focused " +
    "queries so every claim is backed by a real source you retrieved this run. Then write the full " +
    "briefing as <body> HTML per the OUTPUT FORMAT (component classes and badge levels). Then call " +
    "save_briefing_to_repo with that bodyHtml to archive it and get the link. Finally call post_to_slack " +
    "once with just that archive URL as the text.",
});
