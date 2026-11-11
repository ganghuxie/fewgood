# P3-B batch 1 — source validation evidence

Validation date: 2026-11-11 (Asia/Shanghai). Cost: 24 `channels.list?forHandle=` calls = 24 YouTube quota units. No `search.list`, `playlistItems`, or `channels.list?id=` calls. `data/quota.json` was not used or modified by the one-off validator.

The YouTube RSS endpoint returned HTTP 404 in this environment even for existing whitelist channels (e.g. OpenAI), so last-upload evidence comes from each channel's public `/videos` page (the same public upload data exposed by the Atom feed). Subscriber counts and channel ids come from the API response.

## Added (22 active channels)

| id | handle | channel id | subscribers | latest public upload | topic / language | why it qualifies |
|---|---|---|---:|---|---|---|
| crossroads-luoyonghao | @罗永浩的十字路口 | UC33VP_gIBzCVcEvaGKBocZA | 45,500 | 7d | podcast / zh | Verified handle; Chinese long-form talk channel; active upload. |
| stanford-hai | @stanfordhai | UChugFTK0KyrES9terTid8vA | 36,500 | 6d | ai / en | Verified handle; Stanford HAI talks/conference series; active upload. |
| ycombinator | @ycombinator | UCcefcZRL2oaA_uBNeo5UOWg | 2.43M | 2d | ai / en | Verified handle; startup/AI speaker series; active upload. |
| a16z | @a16z | UC9cn0TuPq4dnbTY-CBsm8XA | 308K | 14h | ai / en | Verified handle; AI/startup interviews; active upload. |
| mit-csail | @MITCSAIL | UCBpxspUNl1Th33XbugiHJzw | 90,500 | 3w | ai / en | Verified handle; research talks; active upload within 90 days. |
| sequoia-capital | @sequoiacapital | UCWrF0oN6unbXrWsTN7RctTw | 257K | 5d | ai / en | Verified handle; founder/AI interviews; active upload. |
| veritasium | @veritasium | UCHnyfMqiRRG1u-2MsSQLbXA | 21.4M | 6d | editorial / en | Verified handle; science explainers; active upload. |
| computerphile | @Computerphile | UC9-y-6csu5WGm29I7JiwpnA | 2.64M | 5d | editorial / en | Verified handle; CS explainers; active upload. |
| ted | @TED | UCAuUUnT6oDeKwE6v1NGQxug | 28M | 14h | editorial / en | Verified handle; talks; active upload. |
| long-now | @longnow | UCT1yd7gEOrja_gecmA1lT0Q | 141K | 6d | editorial / en | Verified handle; long-form talks; active upload. |
| computer-history-museum | @ComputerHistory | UCHDr4RtxwA1KqKGwxgdK4Vg | 180K | 4d | editorial / en | Verified handle; computing history; active upload. |
| kurzgesagt | @kurzgesagt | UCsXVk37bltHxD1rDPwtNM8Q | 25.8M | 15h | editorial / en | Verified handle; science animation; active upload. |
| numberphile | @numberphile | UCoxcjq-8xIDTYp3uz647V5A | 4.79M | 1d | editorial / en | Verified handle; mathematics; active upload. |
| pbs-space-time | @pbsspacetime | UC7_gcs09iThXybpVgjHZ_7g | 3.54M | 5d | editorial / en | Verified handle; physics/space; active upload. |
| usenix | @UsenixOrg | UC4-GrpQBx6WCGwmwozP744Q | 42,800 | 1d | editorial / en | Verified handle; systems conference talks; active upload. |
| stanford-gsb | @stanfordgsb | UCGwuxdEeCf0TIA2RbPOj-8g | 2.81M | 4d | editorial / en | Verified handle; business/tech talks; active upload. |
| harvard-business-review | @harvardbusinessreview | UCWo4IA01TXzBeGJJKWHOG9g | 1.68M | 12h | editorial / en | Verified handle; business/tech interviews; active upload. |
| knowledge-project | @tkppodcast | UCLtTf_uKt0Itd0NG7txrwXA | 468K | 19h | editorial / en | Verified handle; long-form interviews; active upload. |
| hard-fork | @hardfork | UCZcR2SVWaGWNlMqPxvQS3vw | 77,400 | 15h | editorial / en | Verified handle; tech journalism; active upload. |
| steve-mould | @SteveMould | UCEIwxahdLz7bap-VDs9h35A | 3.62M | 10d | editorial / en | Verified handle; science explainers; active upload. |
| sabine-hossenfelder | @SabineHossenfelder | UC1yNl2E66ZzKApQdRuTQ4tw | 1.79M | 1d | editorial / en | Verified handle; physics; active upload. |
| minutephysics | @minutephysics | UCUHW94eEFW7hkUMVaZz4eDg | 5.99M | 12d | editorial / en | Verified handle; physics animation; active upload. |

## Rejected or skipped

| candidate | reason |
|---|---|
| Google TechTalks | Resolved @GoogleTechTalks / UCtXKDgv1AVoG88PLl8nGXmw with 349K subs, but latest public upload was 5 months ago (>90 days). Rejected. |
| Strange Loop Conference | Resolved @StrangeLoopConf / UC_QIfHvN9auy2CoOdSfMWDw with 88.2K subs, but latest public upload was 3 years ago. Rejected. |
| 42章经 | Resolved @42章经 / UCirUGhuiz6m85eKO8n3Picw, but only 63 subscribers (<5,000). Rejected. |
| What's Next｜科技早知道 | No official channel/handle resolved from public YouTube channel search. Skipped rather than inventing an id. |
| 硬地骇客 | No official channel/handle resolved. Skipped. |
| 三五环 | No official channel/handle resolved. Skipped. |
| NeurIPS | No verified official handle resolved; skipped to avoid inventing an id or spending extra quota. |
| ICML | @ICMLconf resolves to UC_JtgG9jWCnd9fU5upXboGQ but has 185 subscribers (<5,000). Not added. |
