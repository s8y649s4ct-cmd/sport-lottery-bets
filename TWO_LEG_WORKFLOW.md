# Safe researched two-leg publishing (hourly / detected material changes)

The renderer is **offline only**. It reads reviewed tracked JSON, validates it, preserves the existing `#results` section byte-for-byte, and optionally writes HTML. It NEVER retrieves odds, imports legacy scripts, grades results, places bets, commits, or pushes. Do not run `site.py` or `build.py`: the legacy publisher can overwrite the shortlist and auto-push. No model or routine changes belong in this workflow.

The requested hourly schedule is 8 AM–11 PM America/New_York; a schedule is not continuous monitoring or a promise of immediate detection. A material change detected between scheduled reviews should trigger the same scoped research/review/publication flow. The browser only checks expiration against its clock, not injuries, availability, odds, or event postponements.

## 1. Research first — do not refresh timestamps without research

- Use today's local date (America/New_York), independent official sport/team schedules, current identities/rosters, venue, injuries/inactives or actual starting lineups/goalies. Confirm event has not started and is not tomorrow. Distinguish projected/expected from official confirmation. Recheck weather/roof for outdoor events.
- All FanDuel markets/sports are eligible, but do not assume a prop or an extra sport improves the slate. Stage exactly two DIFFERENT-game legs per card; no artificial card count, payout floor, or repeated-pick permutations. Show shared-game exposure explicitly if it is unavoidable. Unsupported same-game correlation is rejected.
- Cite each pick's concrete supporting facts and counterevidence, not just its favorite status. Official availability and descriptive records/averages are not a calibrated win forecast. Do not invent edge, expected value, model percentages, or guarantees.
- Obtain a legitimate public FanDuel quote or a public provider explicitly attributing prices to FanDuel. Record actual provider snapshot time, American odds, price source, and whether PA/MD-specific. Do NOT replace a source's older timestamp with the retrieval/render time. Provider odds do not establish an actual bookable parlay quote. Nov 8 initial NFL source was AgentBets' **7 AM EST** snapshot; live PA/MD prices were not verified. Direct shell access returned HTTP403; no retry/bypass/internal sportsbook API or copied key was used.
- For two uncorrelated/different-game legs, displayed return is theoretical decimal multiplication including stake; it is NOT the sportsbook parlay quote. Raw reciprocal price product includes margin and is not a forecast or proof of independence.
- Use documented public share/deep-link formats and only exact event/selection/market IDs from legitimately obtained, attributable records. Never derive from ESPN IDs, invent IDs, copy app keys, reverse-engineer internal APIs, or bypass a 403. Nov 8 IDs were exact Nov 8 event/team/moneyline matches in the Nov 7 3:02 PM EST local cache, not live-validated IDs. App opening was user-confirmed; actual iPhone selection acceptance was NOT tested.
- An absent ID record yields **app-only, no picks** rather than a fake load-picks button. A malformed/mismatched provided record fails validation. PA/MD changes market IDs and website fallback, NOT app geolocation/account jurisdiction. No automatic redirect or wager placement.
- Remove/withdraw candidates if support weakens; do not keep them merely for quantity or payout. If none pass, publish an empty `cards: []` review, with honest source limitations and `odds_reported_at_est: null` if no usable quote. Never fabricate a wager or grading result.

## 2. Reviewed tracked data

Maintain `docs/shortlist-YYYY-MM-DD.json`, schema version 2. Use the Nov 8 file as the shape, **not** as reusable picks/IDs. Each card has an id, title, `conditional|ready|withdrawn` status, status_reason, exactly two legs, and optional exactly two identifier records. Each leg requires:

- exact team/selection label, market, event, independent `event_key`, `start_at` with timezone, venue;
- precise `evidence`, `remaining_checks`, `lineup_status`, research source URLs, official availability URL/check timestamp and independent schedule URL;
- integer `american_odds`, actual `price_quoted_at`, `price_source`, `price_state_verified`, and actual `checked_at`.

Provided identifier records must match the leg label (`sel`), event, market, start (`time`), independent event_key, positive `selectionId`, both PA/MD market IDs, source, capture time, and verification description. IDs need not be NFL; the matching rule is sport-independent. For an unsupported state, omit identifiers altogether and disclose app-only limitation (do not substitute another state's IDs). Existing derived URL and return fields, if retained, must agree exactly with the records/math.

`ready` additionally requires confirmed availability, live verified prices (including each leg's state verification) and live verified selection links. Those flags are evidence claims, not an invitation to flip booleans without proof. None of the initial Nov 8 cards met that standard.

Keep research and source-snapshot times separate from rendering time. Default conservative *operational*, not statistically optimized, gates are 120 minutes maximum quote age and 75 minutes maximum research age; the earliest gate or event start wins. Cards are held (without selection links) on render if wrong date, started, stale, or withdrawn. Browser clock hides/disables a staged card at the same deadline and prevents a state switch from reviving it. No JavaScript means PA/default links must only be used before the printed deadline. Publish fresh research rather than relaxing gates to keep cards visible.

Update `update_log` with real material changes. Never change old history or pretend that source checks prove predictive accuracy. The fixed `tools/fixtures` file is regression evidence, not today's recommendations.

## 3. Exact safe local commands (repository root)

```bash
DAY=$(TZ=America/New_York date +%F)
python3 tools/render_two_leg.py --data "docs/shortlist-$DAY.json" --check
python3 tools/test_two_leg.py
node --check docs/two-leg.js
node tools/test_two_leg_js.cjs
python3 tools/render_two_leg.py --data "docs/shortlist-$DAY.json" --write
```

`--check` and no flag validate only; `--write` atomically writes `docs/index.html` and nothing else. No network/deployment side effects. A missing current-day data file or missing historical section fails rather than silently reusing yesterday. The clock is actual Eastern time, not a caller-supplied past timestamp. Regression tests use a fixed dated fixture so future price/card changes do not change expected assertions. The production `--check` separately validates current reviewed data. Run in a scoped branch/worktree synced to main to avoid publication races.

## 4. Reviewed publication — authorized changes only

- Before editing: check `git status` and `gh auth status` (never expose tokens), fetch main, and use a fresh scoped branch/worktree. Locally back up page/data and compute the historical-section hash. Keep unrelated changes untouched.
- Review actual rendered current/held cards, exact two-selection PA and MD link query pairs, names/date/start times, source timestamps, dollars including stake, current/expired states, and mobile layout. Unit tests/DOM harness are NOT an iPhone, live FanDuel, or visual mobile-browser test; report any missing real-device test.
- Inspect `git diff --check`, `git diff --stat` and an explicitly scoped diff. Stage ONLY reviewed public files. The narrow `.gitignore` allowlist deliberately keeps legacy scripts, caches, secrets and Python bytecode ignored; do not `git add -f` them.
- One branch push, create a PR with `gh`, inspect mergeability/checks, then merge normally only within user authorization. Do not force-push, skip hooks, bypass protections, or run auto-publishing legacy scripts. If protection blocks merge, report it.
- Wait for the normal Pages deployment. Fetch the live page and compare expected exact names/two-leg count, deadline, last check, selection pairs/PA–MD assets and historical hash. Report actual PR/commit/site URL and ready/conditional counts. A successful deployment does not verify sportsbook acceptance or predict wins.

## Initial Nov 8 decision

Retained Lions/Texans and Rams/Broncos as CONDITIONAL, zero ready. Withdrew Cowboys/Patriots because combined unresolved receiver/TE/blocker/defender absences leave insufficient support; opponent injuries alone are not enough. NHL: all 12 goalies unconfirmed and no official lineup/schedule clearance. NBA: later official game-day updates required and no current exact FanDuel selection IDs independently established. No extra card was added merely to meet a count. Historical `0–49` aggregate remains verbatim, including its legacy overlap/repeated-leg limitations.
