# User Manual — GrowthKit

A step-by-step guide to using the skill, from install to a finished growth plan.
For the project overview and the honesty model, see [`README.md`](README.md).
For exactly what data is handled, see [`DATA_POLICY.md`](DATA_POLICY.md).

---

## 1. What this skill does (in one minute)

You describe your SaaS/app in Claude Code. The skill picks the right playbook
(B2C-install vs B2B-leadgen, TikTok-native vs Reels/Shorts where TikTok is weak
or banned), writes positioning and Hook→Value→CTA scripts, plans a 2–4 week
60/30/10 content calendar, measures your funnel and SaaS metrics from *your*
numbers, analyzes your own TikTok Studio export, and hands you a finished
**`growth-plan.html`** — a single page with your positioning, calendar (with
copy-buttons per script), metrics with provenance, and a compliance checklist.

**The rule that makes it different:** every market/performance number (views,
completion rate, installs, CAC, LTV, hashtag volume) is computed by a Python
script from data you can see. The model never guesses one. If the data isn't
there, it asks you or says "no data."

---

## 2. Requirements

- **Claude Code** (the skill runs there).
- **Python 3.10+** on your PATH (the scripts run via `python3`).
- *Optional:* `requests` — only for live Creative Center trends (Path C below).
- *Optional:* `huggingface_hub` — only if you contribute data back or pull
  community benchmarks.
- *Optional:* `playwright` — only for live-trend signature headers.

Install the optional packages only if you'll fetch trends or federate:

```
pip install -r requirements.txt
```

The core — planning, scripts, calendar, CSV analysis, metrics, attribution,
compliance — needs **none** of them and works fully offline.

---

## 3. Install

```
/plugin marketplace add Ahad690/growthkit-skill
/plugin install growthkit@growthkit-marketplace
```

Verify the package locally any time with:

```
claude plugin validate .
```

---

## 4. Your first run

1. In Claude Code, just describe what you're building, e.g.:

   > help me grow my study app on TikTok

   (Or run it explicitly: `/growthkit`.)

2. The skill asks **one** set of questions. Answer in a single message:
   - your product one-liner
   - **B2C or B2B**
   - your primary market/country
   - whether your audience is on TikTok
   - stage (pre-PMF / growth) and budget (bootstrapped is the default)
   - existing handles/links, or "none" (optional — stays local)

3. It states which playbook variant it chose and **why** — e.g. *"You're in
   Pakistan, where TikTok is banned per `markets.json`, so this is the
   Reels/Shorts-native plan; TikTok trends are used only as a leading
   indicator."*

4. It writes your positioning (Dunford worksheet → one-liner + JTBD), proposes
   content pillars, and drafts the script calendar. Every **promotional** script
   arrives with the mandatory disclosure block already attached — that's the
   compliance gate, not a suggestion.

5. Give it numbers when you have them, in plain conversation:
   - *"I spent $1,000 and got 50 customers, ARPA $100, margin 80%, churn 2%"* →
     it runs the metrics script and reports CAC/LTV/payback **with flags**.
   - *"10,000 visitors, 1,200 signups, 60 paid"* → it runs the funnel script and
     names your biggest bottleneck.
   - Drop your **TikTok Studio CSV** → it ranks winners, flags hook failures,
     and reports per-post metrics (`confidence: HIGH`, `sources: owned_csv`).

6. It assembles everything into **`growth-plan.html`** and tells you where it
   wrote it. Open it in a browser: positioning, the pillar split, week-by-week
   post cards with copy buttons, a metrics table with confidence/method/sources
   per row, and the compliance checklist.

That's the whole loop — no input files, no keys, no setup.

---

## 5. The three data layers

### Layer A — Your own exports (ground truth, default)
Your TikTok Studio / Business Suite CSV and your own funnel/MMP numbers. This is
the reliable layer: everything computed from it is `confidence: HIGH` with
`sources: ["owned_csv"]` or `["user_input"]`. To export: TikTok Studio →
Analytics → Content → Download data. The analyzer tolerates column-name variants
and missing columns. **Raw exports never leave your machine.**

### Layer B — Bundled benchmarks (labeled defaults)
`benchmarks.json` ships source-tagged default ranges (PLG conversion, SaaS
thresholds, completion tiers). Each is labeled `self_reported`, `measured`, or
`heuristic` — the skill cites them with those labels and never upgrades a
heuristic to a fact. Community data improves these over time (§8).

### Layer C — Live Creative Center trends (opt-in, best-effort)
Ask for live trending hashtags and the skill runs the fetcher. It needs
signature headers (Playwright) and works best from a residential IP; it surfaces
a ToS notice on first use. **On any failure it returns a labeled
`fetch_failed` fallback — never a fabricated trend — and the rest of the skill
is unaffected.** Keyword Insights is explicitly unsupported (no reliable free
path); the skill says so if asked.

---

## 6. Reading the output

Every number in the chat and in `growth-plan.html` carries an envelope:

| Field | What it means |
|---|---|
| **value / low / high** | The number — always a **band** for estimates (attribution is never a single count). |
| **confidence** | `HIGH` only for directly-observed owned facts; estimates cap at `MEDIUM`; thin data is `LOW`; missing data is `NONE`. |
| **method** | How it was computed (`owned_studio_csv`, `deterministic_formula`, `triangulated_estimate`, …). |
| **sources** | Where the inputs came from (`owned_csv`, `user_input`, `creative_center`, `community_dataset`). |
| **flags** | e.g. `hook_failure`, `ltv_cac_below_floor`, `organic_attribution_is_approximate` — read these; they tell you how much to trust a number. |

Anything labeled `heuristic` (e.g. "~70% completion ≈ viral") is creator lore
used only to frame guidance — never presented as a measured fact.

---

## 7. Running the scripts directly (optional)

You don't need to — the skill orchestrates them — but they're plain CLIs:

```
# Analyze your TikTok Studio export (ground truth)
python3 skills/growthkit/scripts/analyze_studio_csv.py export.csv --floor 0.20

# SaaS metrics from your raw numbers
python3 skills/growthkit/scripts/saas_metrics.py --spend 1000 --new-customers 50 \
    --arpa-monthly 100 --arpu-monthly 100 --gross-margin 0.8 --monthly-churn 0.02

# Funnel bottleneck (flag order = funnel order)
python3 skills/growthkit/scripts/funnel_diagnose.py \
    --stage visitors=10000 --stage signups=1200 --stage paid=60

# Banded organic-attribution estimate (never a precise count)
python3 skills/growthkit/scripts/attribution_estimate.py \
    --landing-utm-installs 100 --promo-code-redemptions 50 \
    --mmp-organic-bucket 400 --survey-tiktok-share 0.3 --total-installs 1000

# Compliance screen
python3 skills/growthkit/scripts/compliance.py --account-type business \
    --category crypto --sound-source trending

# Live trends (optional; labeled fallback on failure)
python3 skills/growthkit/scripts/fetch_trends.py --country US

# Render a plan you already have
python3 skills/growthkit/scripts/build_plan.py growth-plan.json --out growth-plan.html
```

Every script prints JSON; add `--help` to any of them.

---

## 8. Contributing data back (opt-in)

The skill can share **public, anonymized** trend/benchmark rows to a community
Hugging Face dataset that improves everyone's defaults.

**Contribution is OFF by default. Nothing ever leaves your machine unless you
deliberately run the command without `--dry-run`.** Two independent on-switches
must both be flipped: dropping `--dry-run` **and** having `HF_TOKEN` set.

**Step 1 — preview (safe; shares nothing):**

```
python3 skills/growthkit/scripts/federation/contribute.py --rows rows.json --dry-run
```

This prints the exact cleaned rows that *would* be shared. `assert_public_only`
aborts the whole contribution if any identifying/owned field (handle, `video_id`,
raw CSV, per-post metrics, install-level data…) is present.

**Step 2 — actually share:**

```
export HF_TOKEN=your_hf_token               # Windows: setx HF_TOKEN "..."
python3 skills/growthkit/scripts/federation/contribute.py --rows rows.json
```

Your contribution lands as one new content-addressed file
(`contributions/<you>-<hash>.json`) opened as a **pull request** — append-only,
never rewriting existing data. A guarded bot auto-merges clean PRs and holds
anything suspicious for a human. Full policy: [`DATA_POLICY.md`](DATA_POLICY.md).

**Pulling community data back down:**

```
python3 skills/growthkit/scripts/federation/refresh_dataset.py --dry-run   # preview
python3 skills/growthkit/scripts/federation/refresh_dataset.py             # merge
```

It refuses corrupt-heavy files, no-ops below a minimum of clean new rows, and
labels community benchmarks with coverage-aware confidence.

**Maintainers** — store the bot's fine-grained HF token (write + discussions,
scoped to only the dataset) as a repo secret:

```powershell
# gh prompts for the value with hidden input (avoid -b, which echoes the token):
gh secret set HF_TOKEN -R Ahad690/growthkit-skill
```

---

## 9. Tuning

All knobs live in `skills/growthkit/references/config.json` — nothing is hidden
in the model. Common edits:

- **`content.pillar_split`** — change the 60/30/10 mix.
- **`analyzer.three_sec_view_floor`** — where `hook_failure` fires (default 0.20).
- **`saas_benchmarks.*`** — the LTV:CAC floor, payback ceiling, churn warning.
- **`fetch.*`** — default country, period, cache TTL for live trends.
- **`federation.*`** — dataset repo, refresh thresholds.
- **`ui.contribution_reminder`** — set `false` to remove the "help grow the
  dataset" banner from the generated `growth-plan.html`.

Re-run after editing — output changes deterministically.

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| **Skill asks for an export instead of giving a number** | By design. It won't guess your metrics — drop the TikTok Studio CSV or state the number. |
| **Attribution shows a wide band / LOW confidence** | Your triangulation methods disagree. Add more signals (UTM links, promo codes, an MMP export, a post-install survey). It will never collapse the band into a fake precise count. |
| **Trends return `fetch_failed`** | Expected without signature headers / from a datacenter IP. The plan still works fully on owned data; try `--acquire-headers` with Playwright installed, or skip trends. |
| **A promo script "has extra text about disclosure"** | That's the mandatory disclosure block (compliance gate). It stays. |
| **Business account + trending sound refused** | Also by design — business accounts must use Commercial Music Library or original audio. |
| **Benchmarks say LOW confidence** | That (industry, country) segment has little community data yet. Contribute (§8) to improve it. |
| **`refusing to upload identifying/owned fields`** | The PII guard caught a banned field in your contribution. Strip to the shareable schema — this is the guard working. |
| **`python3: command not found` (Windows)** | Use `python` instead of `python3`. |

---

## 11. FAQ

**Does it post to TikTok for me?** No. No auto-posting, no scheduling, no
engagement automation — it produces copy-paste-ready scripts and a plan.

**Will the numbers change between runs?** Not for the same inputs — every metric
is deterministic. They change only when your data changes.

**Can it tell me exactly how many installs TikTok drove?** No, and it won't
pretend to — organic attribution has no pixel. You get a triangulated band with
a confidence label and the deferred-deep-link caveat.

**Are the case-study numbers real?** They're self/agency-reported and labeled as
such; the skill teaches the patterns, not the numbers.

**Is fetching Creative Center trends allowed?** That's on you to determine —
it's opt-in, surfaced with a ToS notice, and the skill never requires it. See
[`DATA_POLICY.md`](DATA_POLICY.md).

---

## 12. License

- **Code:** MIT ([`LICENSE`](LICENSE))
- **Data & docs:** CC-BY-4.0 ([`LICENSE-DATA`](LICENSE-DATA))

Run the tests with `python -m pytest tests/ -q` (72 tests).
