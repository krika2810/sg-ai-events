Staged SG events site patch (private, no secrets). Created 2026-11-06 ~9:57 PM SGT.
Baseline: GitHub main commit 4907a45735e0 (pushed 2026-11-06 ~9:52 PM, Luma-style redesign + Nov 6 refresh); production deployment dpl_4QgKsZcPgPCrv7onvqiJy8npyD5q at sg-ai-events.vercel.app. (GitHub says repo moved to krika2810/sg-ai-events.)
Diff vs baseline:
1. index.html: red "Paid workshop proposed" box (field `fee`) incl. dark-mode style.
2. data/events.json: Grok workshop (lu.ma/6mdkxzgh) gets `fee` (S$50 proposed, regular S$200, Luma ticket is free interest registration only); Vultr credits text without "new account" claim; Kiroween 2026 added (virtual, amber).
3. data/manual-events.json + credits.json: Vultr wording fix.
4. data/meta.json counts updated.
Deploy only after Main's go. Verify Grok fee, Vultr and Kiroween terms against organiser pages first.
5. v3: AMD AI League (lablab, online, new-member $100 GPU credits) added; event count 65.
6. v4: Clocked Build Challenge (amber) and Anthropic Briefing livestream (no credits, end time unstated) added; 67 events.
7. v5: /goal cup and Concordium Trusted Agents (both online, no credits) added; 69 events. Excluded stale AMD AI DevMaster (ended Aug 6).
8. v6/v7: AI labs vendor-chip filter restored (old semantics from 600493e), vendor tags on 19 events, refresh.py location_type fix (zoom/youtube etc. now count as virtual - root cause of thin virtual list), GMI Cloud x Factory and Miro AI online events added; 71 events.
9. v8: explainx Grok Bot Zoom workshop (Nov 7 9 PM SGT, free), explainx Copilot Zoom workshop (Dec 20-21, price unstated), Jumping Rivers Agents in Production webinar (Nov 19, free) added; 74 events.
10. v9: OpenAI Academy Codex bootcamps 101/201/301 (Dec 4/11/18, 2 AM SGT) and 3 OpenAI Forum livestreams added via cloud-browser read of official event pages; 80 events.
11. v10 (final for 09 batch): vendor tags backfilled to 33/80 via refresh.py VENDOR_KW (extended: Hugging Face, ClickHouse, Base44, Bitdeer, ElevenLabs, Kiro, GMI Cloud, Qwen, Daytona, Nosana, vLLM, Vultr) applied to name+hosts+calendar; "Untagged" chip added (47 genuinely vendor-less community events); hybrid semantics fixed (SG tab keeps hybrid events; SMC online livestream marked virtual+sg); refresh.py location_type fix included. Counts: 80 total, 49 SG, 32 virtual, 8 credits. Interaction tests and mobile light/dark + desktop screenshots verified on this build.
12. v11: SG hybrid scan complete - all 49 SG physical events' Luma descriptions checked for zoom/teams/meet/online/virtual/hybrid/livestream keywords; every 'teams' hit was the ordinary word (team size), not Microsoft Teams; the only true hybrid is the SMC Symposium, whose online livestream twin (evt-2raPbsIRWuyVYbK, lu.ma/50l63ism) is already listed and marked virtual+sg. Click-through verification: all 80 organiser URLs resolve and match their events (Luma via api.lu.ma/url name match; external via page title; NUS Law page is Incapsula bot-walled, verified via search-result page content instead). lablab.ai URLs canonicalised to lablab.build (Vultr + AMD AI League; old URLs 308-redirect). Counts unchanged: 80 total, 49 SG, 32 virtual, 8 credits.
