# GrowthKit — User Manual

A practical, end-to-end guide to using **GrowthKit**, the honest short-form-video
marketing skill for SaaS and apps. For the *why* behind the design, see
[`README.md`](README.md); for the data/privacy contract, see
[`DATA_POLICY.md`](DATA_POLICY.md).

---

## 1. What GrowthKit is (and the one rule that defines it)

GrowthKit plans and writes a TikTok-first (Reels/Shorts where TikTok is weak or
banned) growth motion for a SaaS/app. The single rule that governs everything:

> **The model never invents a market/performance number.** Views, completion
> rate, followers, installs, CAC, LTV, hashtag volume — these come ONLY from the
> deterministic scripts run on *your own real exports*, or from a clearly-labeled
> external fetch. Missing data ⇒ GrowthKit asks for the export or says "no data."
> It never fabricates.

Every number you see carries an **envelope**:
`{value, low, high, confidence∈{LOW,MEDIUM,HIGH}, method, sources, flags}`.

---

## 2. Requirements & install

- **Python 3.10+.** The core scripts use only the standard library — no installs
  needed to analyze your data, compute metrics, or run the compliance gate.
- Optional extras (only for optional features):
  ```bash
  pip install -r requirements.txt        # requests (live trends), huggingface_hub (federation)
  pip install "playwright>=1.40" && playwright install chromium   # only for live-trend header acquisition
  ```

Clone and use as a Claude Code skill:

```bash
git clone https://github.com/Ahad690/growthkit-skill.git
```

The skill lives in `skills/growthkit/`. Invoke it in Claude Code with
`/growthkit` or just ask for a marketing plan, video scripts, a content calendar,
growth metrics, or attribution analysis. Scripts can also be run directly from a
terminal (see §5).

---

## 3. Quick start (5 minutes)

1. **Describe your product** to GrowthKit: one-liner, B2C or B2B, primary
   market/country, stage, budget. It picks the right playbook variant and tells
   you which and why.
2. **Get a plan:** positioning, content pillars (60/30/10), and a 2–4 week
   Hook→Value→CTA script calendar. Promotional scripts come with the mandatory
   disclosure block already attached.
3. **Bring real data when you have it:** export your TikTok Studio CSV and ask
   GrowthKit to analyze it (see §5.1). Now your "what's working" is measured, not
   guessed.

---

## 4. The intake questions (and why they branch the playbook)

GrowthKit asks once, in one message:

| Question | Why it matters |
|----------|----------------|
| Product one-liner | Positioning + script substance |
| **B2C or B2B** | B2C = install-chasing; B2B = awareness/leads, longer cycle |
| **Primary market/country** | If `weak`/`banned` in `markets.json` (e.g., India, Pakistan) → Reels/Shorts-native playbook |
| Audience on TikTok? | Confirms platform choice |
| Stage (pre-PMF / growth) | Tunes priorities |
| Budget (default: bootstrapped) | Organic-first vs paid |
| Existing handles/links (optional) | **Stays local** — never uploaded |

Chosen variant = **(B2C-install | B2B-leadgen) × (TikTok-native | Reels/Shorts-native)**.

---

## 5. The scripts (run directly or via the skill)

All scripts print JSON with the provenance envelope. Paths below are relative to
the repo root; the skill calls them as `python3 ${CLAUDE_SKILL_DIR}/scripts/<name>.py`.

### 5.1 Analyze your TikTok Studio CSV — ground truth
Export from **TikTok Studio → Analytics → Content** (columns like `video_id,
post_date, views, video_duration_sec, avg_watch_time_sec, full_video_watch_rate,
shares, saves, profile_visits, …`; the analyzer tolerates name variants and
missing columns).

```bash
python skills/growthkit/scripts/analyze_studio_csv.py path/to/export.csv --floor 0.20 --top-n 10
```
Returns per-post completion/watch-time/share/save/profile-visit rates, ranked
winners, and `hook_failure` flags for posts below the 3-second-view floor. All
`confidence: HIGH`, `sources: ["owned_csv"]`. **Your raw CSV never leaves your
machine.**

### 5.2 SaaS metrics calculator
Create an `inputs.json`:
```json
{ "spend": 1000, "new_customers": 50, "arpa_monthly": 100, "arpu_monthly": 100,
  "gross_margin": 0.8, "monthly_churn": 0.02,
  "invites_per_user": 5, "invite_conversion_rate": 0.2 }
```
```bash
python skills/growthkit/scripts/saas_metrics.py --inputs inputs.json \
  --benchmarks skills/growthkit/references/config.json
```
Returns CAC, LTV, LTV:CAC, CAC payback, annual churn, K-factor, with threshold
flags (`ltv_cac_below_floor`, `payback_too_long`, `churn_above_warn`).

### 5.3 Funnel diagnostic (AARRR/RARRA)
`stages.json` (ordered):
```json
{ "visitors": 10000, "signups": 1200, "activated": 400, "paid": 60, "retained_d30": 30 }
```
```bash
python skills/growthkit/scripts/funnel_diagnose.py --stages stages.json
```
Returns step conversions, drop-offs, and the biggest bottleneck — deterministic.

### 5.4 Organic-attribution estimate (banded, never precise)
`signals.json` — all your own owned counts:
```json
{ "landing_utm_installs": 100, "promo_code_redemptions": 50,
  "brand_search_lift_installs": 50, "mmp_organic_bucket": 400,
  "survey_tiktok_share": 0.3, "total_installs": 1000 }
```
```bash
python skills/growthkit/scripts/attribution_estimate.py --signals signals.json
```
Returns a **band** (`value`, `low`, `high`) + confidence + the
"deferred deep links ≠ reliable attribution" caveat. No signals ⇒ `confidence:
NONE`, `flags: [no_attribution_data]` (never a fabricated number).

### 5.5 Compliance screen (hard gate)
```bash
python skills/growthkit/scripts/compliance.py --account-type business --category crypto --sound-source trending
```
Screens music (business → CML/original only), restricted categories, and (in the
skill flow) disclosure + repurposing. Used automatically before any promotional
output is shown.

### 5.6 Live trends (OPTIONAL, degrades gracefully)
```bash
python skills/growthkit/scripts/fetch_trends.py --country US           # prints a ToS notice to stderr
python skills/growthkit/scripts/fetch_trends.py --country US --acquire-headers   # tries Playwright
```
With no signature headers/proxy it returns a clearly-labeled `fetch_failed`
fallback — it never crashes and never fabricates a trend. **Every other feature
works with the network disabled.**

---

## 6. Compliance gates (what GrowthKit will refuse to do)

1. **Music** — on a **business account**, only Commercial Music Library or
   original/owned audio. It will not tell you to reuse a trending commercial sound.
2. **Disclosure** — any promotional post gets the in-app Commercial Content
   Disclosure toggle + first-line + spoken + on-screen disclosure. A bio
   disclosure does not cover a post; `#ad` alone is insufficient.
3. **Restricted categories** — crypto, financial, health/supplements, alcohol,
   etc. are flagged/adjusted before a campaign is generated.
4. **Repurposing** — always export a clean master; never download the watermarked
   TikTok and re-upload.

---

## 7. Known limitations (by design, not bugs)

1. **Keyword Insights is unsupported** — no reliable free path; GrowthKit says so.
2. **Organic attribution is approximate** — there's no pixel on organic posts;
   you get a band, never a precise count.
3. **Case-study growth numbers are self/agency-reported** — taught as patterns,
   labeled `self_reported`, never presented as reproducible benchmarks.

---

## 8. Federation (opt-in, OFF by default)

GrowthKit can contribute **public, anonymized** trend/benchmark rows to a shared
Hugging Face dataset that improves everyone's default benchmarks. Your owned
analytics, handles, and any identifying field **never leave your machine**.

### 8.1 Preview what would be shared (safe; no upload)
```bash
python skills/growthkit/scripts/federation/contribute.py --rows rows.json --dry-run
```
`assert_public_only` aborts the entire contribution if any banned field (handle,
`video_id`, raw CSV, install-level data, etc.) is present.

### 8.2 Actually contribute (requires BOTH a token AND dropping --dry-run)
```bash
export HF_TOKEN=hf_...      # PowerShell: $env:HF_TOKEN = "hf_..."
python skills/growthkit/scripts/federation/contribute.py --rows rows.json
```
Each contribution becomes one new content-addressed file
`contributions/<author>-<hash>.json` opened as a **pull request** — append-only,
never rewriting existing data. There is no background upload.

### 8.3 Pull community data back into your local benchmarks
```bash
python skills/growthkit/scripts/federation/refresh_dataset.py --dry-run   # preview
python skills/growthkit/scripts/federation/refresh_dataset.py             # merge
```
Validates every row (schema + range + enum + banned-field), refuses corrupt-heavy
files, no-ops below the new-row threshold, and rebuilds community benchmarks with
coverage-aware confidence (`LOW` until a segment has enough rows). Reading the
public dataset needs no token.

### 8.4 Maintainers: the auto-merge bot
Clean PRs are merged unattended by
`skills/growthkit/scripts/federation/automerge.py` (daily GitHub Actions cron),
but only if they're purely additive and clear the guard stack (additive-only →
size cap → schema/PII/range → anti-abuse); anything else is held for a human. It
needs a **fine-grained** HF token (write + discussions, scoped to just
`Ahad690/growthkit-trends`) stored as the `HF_TOKEN` repo secret:

```powershell
# PowerShell one-liner (prompts without echoing the token):
gh secret set HF_TOKEN -R Ahad690/growthkit-skill # `-b` flag allows to see your token in the powershell UI
```

```bash
# Preview the bot's decisions without merging:
python skills/growthkit/scripts/federation/automerge.py --dry-run
```

> **Honest boundary:** the guards prove a row is well-formed, PII-free, in-range,
> and statistically unremarkable — not that the numbers are *authentic*. Because a
> Hugging Face repo is a git repo, any merge is one corrective commit from
> reverted, and consumers can pin a known-good revision.

---

## 9. Configuration

All tunable constants live in
[`skills/growthkit/references/config.json`](skills/growthkit/references/config.json):
pillar split, hashtags-per-post, the 3-sec-view floor, SaaS benchmark thresholds,
fetch settings, federation thresholds, and `ui.contribution_reminder` (the
opt-out toggle for the contribution nudge). Same inputs + same config + same
dataset snapshot ⇒ reproducible outputs.

---

## 10. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `fetch_failed` in trend results | Expected without signature headers/proxy. Use owned-CSV analysis + bundled benchmarks; live trends are optional. |
| Attribution returns `NONE` | You supplied no usable signals — add UTM/promo/MMP/survey numbers. It won't guess. |
| `refusing to upload identifying/owned fields` | A banned field was in your contribution rows. Strip to the shareable schema (§8). This is the guard working. |
| `missing_columns:` flag from the analyzer | Your CSV lacked some columns; GrowthKit computed what it could and flagged the rest. |
| Benchmarks labeled `LOW` confidence | That (industry, country) segment lacks community data yet. Contribute to improve coverage. |
| `python3: command not found` (Windows) | Use `python` instead of `python3`. |

---

## 11. License

- **Code:** MIT ([`LICENSE`](LICENSE))
- **Data & docs:** CC-BY-4.0 ([`LICENSE-DATA`](LICENSE-DATA))

Run the tests with `python -m pytest tests/ -q` (61 tests).
