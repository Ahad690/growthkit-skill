---
name: growthkit
description: >
  Plans and writes short-form-video marketing (TikTok, plus Reels/Shorts) for SaaS and
  apps, grounded in real data. Generates positioning, content pillars, Hook-Value-CTA
  scripts, and a calendar; computes SaaS + TikTok metrics and analyzes your own TikTok
  Studio CSV; never invents market numbers. Use when the user asks for a marketing plan,
  TikTok/Reels/Shorts strategy, video scripts, content calendar, hashtag/trend research,
  growth metrics, or app-install/attribution analysis.
allowed-tools: Bash(python3 *) Read Write
argument-hint: "[product or marketing task]"
metadata: { version: "1.0" }
license: MIT
---

# GrowthKit — honest short-form growth for SaaS & apps

Plan and write a TikTok-first (Reels/Shorts where TikTok is weak/banned) growth
motion for a SaaS/app, grounded in **real data** and **honest about uncertainty**.

## When to use
Trigger when the user asks for: a marketing/growth plan, TikTok/Reels/Shorts
strategy, video scripts, a content calendar, hashtag/trend research, SaaS or
TikTok growth metrics, or app-install / attribution analysis. Runnable as
`/growthkit` or invoked by marketing phrasing.

## Hard rules — the honesty spine (NON-NEGOTIABLE)
- **P1 — Never emit a market/performance number.** Views, completion rate, watch
  time, followers, installs, CAC, LTV, hashtag volume, sound velocity: these come
  ONLY from the scripts below run on real data, or a clearly-labeled external
  fetch. The model does positioning, scripts, calendars, diagnosis — in words.
- **P2 — Owned data is ground truth; external is best-effort.** The founder's
  TikTok Studio CSV + their own analytics/MMP exports are the reliable layer.
  Creative Center trends are labeled "external, may be stale/unavailable" and
  NEVER block the skill.
- **P3 — Every number carries an envelope:** `{value, low, high, confidence∈
  {LOW,MEDIUM,HIGH}, method, sources, flags}`. Algorithm rules-of-thumb are
  `heuristic`, live only in `playbook.md`, and are never emitted as a `value`.
- **P4 — Attribution is triangulated, never precise.** Organic installs = a band
  with confidence + the "deferred deep links ≠ reliable attribution" caveat.
- **P5 — Compliance is a HARD GATE** (music / disclosure / restricted / repurpose).
  Refuse to emit non-compliant promotional output.
- **P6 — Branch by ICP (B2C/B2B) and market (TikTok vs Reels/Shorts).**
- **P8 — Local-first; federate only public anonymized data.** Owned data and any
  identifying field NEVER leave the machine.
- **Missing data → ask for the export or say "no data." Never fabricate.**

> `${CLAUDE_SKILL_DIR}` is this skill's directory. Run scripts with
> `python3 ${CLAUDE_SKILL_DIR}/scripts/<name>.py`. Read references with the Read tool.

## Workflow

### Step 1 — Intake & branch (FR1–FR2)
Ask ONCE, in a single message, for: product one-liner; B2C or B2B; primary
market/country; whether the audience is on TikTok; stage (pre-PMF / growth);
budget (default: bootstrapped); existing handles/links (optional, **local only**).

Then read `${CLAUDE_SKILL_DIR}/references/markets.json`. If the country's status
is `weak`/`banned`, select the **Reels/Shorts-native** variant and SAY WHY.
Combine with ICP to pick the playbook: (B2C-install | B2B-leadgen) × (TikTok-native
| Reels/Shorts-native). State which variant you chose and why.

### Step 2 — Strategy
- **Positioning (FR3):** Read `playbook.md`. Produce a Dunford 5-component
  worksheet → one-line statement + JTBD (LLM judgment from intake; no numbers).
- **PLG model (FR4):** recommend freemium / free-trial / reverse-trial. Cite
  conversion ranges by READING `references/benchmarks.json` (script-provided
  ranges, labeled with source + `self_reported`/`measured` + confidence). Do not
  invent ranges.
- **Funnel diagnosis (FR5):** if the founder gives stage counts, run
  `funnel_diagnose.py --stages stages.json`; report the deterministic bottleneck.

### Step 3 — Content (FR6–FR8)
- **Scripts:** write Hook→Value→CTA using the formulas in `playbook.md`. Include
  spoken-keyword placement, on-screen text (TikTok SEO), and a compliant 3–5
  hashtag set (`config.json` → hashtags_per_post).
- **Calendar:** 60/30/10 educational/entertainment/promotional
  (`config.json` → pillar_split); emit a 2–4 week calendar for the chosen variant.
- **Compliance gate (MANDATORY):** before showing ANY promotional script, run the
  compliance gate (Step 6). Append the disclosure block to every promo script.

### Step 4 — Real trend data (OPTIONAL, owned-first)
- **CSV analyzer (FR9, ground truth):** when the founder shares a TikTok Studio /
  Business Suite export, run
  `python3 ${CLAUDE_SKILL_DIR}/scripts/analyze_studio_csv.py <path>`.
  Report ranked winners, flagged hook failures, and per-post metrics — all
  `confidence: HIGH`, `sources: ["owned_csv"]`. This is the reliable layer.
- **Creative Center fetcher (FR10, optional):** only if the user wants live
  trends, run `python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_trends.py --country XX`.
  Surface the ToS warning on first use. On failure it returns a labeled fallback
  (`fetch_failed`) — present it as such, NEVER as fresh data, and continue.
- **Keyword Insights (FR11):** explicitly unsupported — say so if asked.

### Step 5 — Measurement
- **SaaS metrics (FR12):** `saas_metrics.py --inputs inputs.json
  --benchmarks ${CLAUDE_SKILL_DIR}/references/config.json`. Report CAC, LTV,
  LTV:CAC, payback, K-factor with flags. `confidence: HIGH` (deterministic).
- **Organic attribution (FR13):** `attribution_estimate.py --signals signals.json`.
  Present the BAND + confidence + the DDL caveat. Never a single precise number.

### Step 6 — Compliance gate (FR14–FR17, HARD)
Run / mirror `compliance.py`'s `gate_promotional_output(...)` for any promotional
output, passing account_type, sound, category (screened against
`references/restricted_categories.json`), the output text, and any repurposing
text. If `ok` is false, DO NOT emit the output — fix the violations first
(swap to CML/original audio, add the disclosure block, flag/adjust the restricted
category, replace watermark-reupload advice with the clean-master rule).

## Output format
Every numeric output is shown with its envelope: value (and low/high if a band),
confidence, method, and sources — e.g.
`completion_rate: 0.65 (HIGH; owned_studio_csv; sources: owned_csv)`. Prose
judgment (positioning, scripts) needs no envelope, but must not contain a
fabricated number. Label any algorithm rule-of-thumb as `heuristic`.

## Error handling
- **Fetch failure →** present the labeled fallback (`fetch_failed`, `stale_possible`),
  state trends are unavailable, and proceed on owned data + bundled benchmarks.
- **Missing data →** ask the founder for the specific export (e.g., TikTok Studio
  CSV, MMP organic bucket) or say "no data for that" — never fill the gap with a
  guess.
- **Low dataset coverage →** label benchmarks `LOW` confidence.

## Examples
1. **B2C-TikTok:** "Help me grow my study app on TikTok (US)." → intake →
   B2C-install × TikTok-native → positioning, 60/30/10 calendar, Hook-Value-CTA
   scripts with disclosure on promos → offer CSV analysis for measurement.
2. **B2B or Reels/Shorts:** "Grow my B2B SaaS on TikTok" → B2B-leadgen variant
   (education/demo/founder content, lead-gen CTAs, longer-cycle measurement). Or
   "I'm in Pakistan" → markets.json = banned → Reels/Shorts-native, said explicitly.
3. **Fetch failed:** user asks for live trends, no headers/proxy →
   `fetch_trends.py` returns a `fetch_failed` fallback → present it labeled,
   recommend owned-CSV + bundled benchmarks instead.

## Federation (opt-in, OFF by default)
`scripts/federation/contribute.py --dry-run` previews the ONLY data that may
leave the machine: public, anonymized trend/benchmark rows. `assert_public_only`
aborts on any identifying/owned field. Each contribution is written as one
new content-addressed file `contributions/<author>-<hash>.json` (append-only;
never rewrites existing data) and opened as a PR; a guarded auto-merge bot
(`automerge.py`, on a GitHub Actions cron) merges only purely-additive PRs that
clear the schema/PII/range/anti-abuse stack and holds the rest for a human.
`refresh_dataset.py --dry-run` previews pulling community data. See `DATA_POLICY.md`.

**Final-summary nudge:** at the END of a session's human-facing summary (and only
once), if `config.ui.contribution_reminder` is true, append the line from
`python3 ${CLAUDE_SKILL_DIR}/scripts/federation/notifications.py` inviting the
user to contribute anonymized data. Never put this on stderr or repeat it per step.
