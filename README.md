# GrowthKit — honest short-form growth for SaaS & apps

An open-source [Claude Code](https://claude.com/claude-code) skill that helps any
SaaS/app founder run a short-form-video-led growth motion (**TikTok-first**, with
**Reels/Shorts** where TikTok is weak or banned) — grounded in **real data** and
**honest about uncertainty**.

Most "AI marketing" tools are thin prompt wrappers that confidently hallucinate
metrics: fake hashtag volumes, made-up completion-rate benchmarks, invented
install numbers. **GrowthKit is the opposite.** Every market/performance number is
computed by an auditable script from real data, labeled with its confidence and
source, and the skill refuses to fake the things that genuinely can't be known
precisely (dollar-perfect organic attribution, panel-grade competitor stats).

## The honesty model (why this is different)

- **The model never emits a market/performance number.** Views, completion rate,
  followers, installs, CAC, LTV, hashtag volume — these come ONLY from
  deterministic scripts run on **your own real exports**, or from a clearly-labeled
  external fetch. The LLM does positioning, scripts, calendars, and diagnosis —
  in words. Missing data ⇒ it asks for the export or says "no data." It never
  fabricates.
- **Every number carries an envelope:**
  `{value, low, high, confidence∈{LOW,MEDIUM,HIGH}, method, sources, flags}`.
  Algorithm rules-of-thumb (e.g., "~70% completion ≈ viral") are labeled
  `heuristic`, live only in `playbook.md`, and are never emitted as a value.
- **Owned data is ground truth; external data is best-effort.** Your TikTok
  Studio / Business Suite CSV and your own analytics/MMP exports are the reliable
  layer. The Creative Center trend fetcher is **optional** and **degrades
  gracefully** — every other feature works fully with the network disabled.

## What it does

| Area | Capability | How honesty is enforced |
|------|-----------|--------------------------|
| **Strategy** | Positioning (Dunford), ICP, PLG-model selection, AARRR/RARRA diagnosis | PLG ranges read from `benchmarks.json` (labeled); funnel computed by `funnel_diagnose.py` |
| **Content** | Hook→Value→CTA scripts, TikTok-SEO captions/on-screen text, 60/30/10 calendar | Compliance gate on every promo script |
| **Owned analytics** | `analyze_studio_csv.py` ranks winners, flags hook failures, per-post metrics | `confidence: HIGH`, `sources: [owned_csv]` — ground truth |
| **Metrics** | `saas_metrics.py` (CAC/LTV/ratio/payback/K-factor) | Deterministic formulas over your inputs |
| **Attribution** | `attribution_estimate.py` — organic installs | A **band** + confidence + the "deferred deep links ≠ reliable" caveat — never a precise count |
| **Trends (optional)** | `fetch_trends.py` — Creative Center hashtags | Best-effort; on failure → labeled fallback, never fabricated |
| **Compliance** | Music / disclosure / restricted-category / repurposing | **Hard gate** in `compliance.py` |
| **Deliverable** | `build_plan.py` renders the finished `growth-plan.html` | Presentation-only; stamps the disclosure block on any undisclosed promo post |
| **Federation (opt-in)** | Share public anonymized trend rows; pull community defaults | `assert_public_only` aborts on any identifying field |

## Install

```
/plugin marketplace add Ahad690/growthkit-skill
/plugin install growthkit@growthkit-marketplace
```

Then just describe what you're building — *"help me grow my study app on
TikTok"* — or run `/growthkit`. The skill asks one set of intake questions,
plans in conversation, runs its deterministic scripts on the numbers you give
it, and finishes by writing **`growth-plan.html`**: your positioning, the
week-by-week script calendar with copy buttons, a metrics table with provenance
per row, and the compliance checklist. No input files, no keys, no setup.

> **New here?** The [**User Manual**](USER_MANUAL.md) walks through your first
> run, the three data layers, reading the output envelopes, and the opt-in
> federation loop.

### Requirements
- **Python 3.10+.** The core scripts use only the standard library.
- Optional: `requests` (live trends), `huggingface_hub` (federation),
  `playwright` (Creative Center header acquisition). See `requirements.txt`.
  **The skill works fully without any of these** — they only enable optional
  enrichment.

## Branching by ICP + market

- **B2C app-install** vs **B2B-leadgen** playbooks (different content, CTAs,
  measurement).
- **TikTok-native** vs **Reels/Shorts-native**: when your primary market is
  `weak`/`banned` in `markets.json` (e.g., India, Pakistan), the skill switches
  to the Reels/Shorts playbook and tells you why. TikTok trends are still used as
  a leading indicator where available.

## Compliance gates (hard requirements, not suggestions)

1. **Music** — business accounts must use the Commercial Music Library or
   original/owned audio. Never reuse a trending commercial sound on a business
   account.
2. **Disclosure** — any promotional post gets the in-app Commercial Content
   Disclosure toggle + first-line + spoken + on-screen disclosure. A bio
   disclosure does not cover a post; `#ad` alone is insufficient.
3. **Restricted categories** — screened against `restricted_categories.json`
   (crypto, financial, health/supplements, etc.) before generating a campaign.
4. **Repurposing** — always export a clean master; never download the watermarked
   TikTok and re-upload (cross-platform watermark down-rank).

Proven by `tests/test_compliance_guard.py`.

## Known limitations (by design)

1. **Keyword Insights is unsupported** — there is no reliable free path; the skill
   says so rather than promising it.
2. **Organic attribution is approximate** — there is no pixel on organic posts.
   GrowthKit triangulates UTM/landing hits + promo codes + brand-search lift +
   MMP organic bucket + surveys into a **band**, never a precise number.
3. **Case-study growth numbers are self/agency-reported** — taught as patterns,
   labeled `self_reported`, never presented as reproducible benchmarks.

## Federation (opt-in, OFF by default)

GrowthKit can contribute **public, anonymized** trend/benchmark rows to a shared
[Hugging Face dataset](https://huggingface.co/datasets/Ahad690/growthkit-trends)
(CC-BY-4.0) that improves everyone's default benchmarks over time. Owned
analytics, handles, and any identifying field **never leave your machine** — the
`assert_public_only` guard refuses the whole contribution on any banned field.

Every run **stages** its shareable observations in a local, append-only store
(`data/observations.local.json`) — successful trend fetches and aggregated
(median-only) CSV benchmarks accumulate there, nothing is ever deleted — so
contributing later is one command:

```bash
# Preview exactly what's staged / would be shared (no upload):
python3 skills/growthkit/scripts/federation/contribute.py --dry-run

# Pull community data and refresh default benchmarks (preview):
python3 skills/growthkit/scripts/federation/refresh_dataset.py --dry-run
```

A real upload requires **both** dropping `--dry-run` and setting `HF_TOKEN`.
There is no background upload. See [DATA_POLICY.md](DATA_POLICY.md).

**Self-growing, safely.** Each contribution is one new, content-addressed,
append-only file (`contributions/<author>-<hash>.json`) — it never rewrites
existing data. A guarded auto-merge bot
([`automerge.py`](skills/growthkit/scripts/federation/automerge.py), run on a
daily GitHub Actions cron) merges only purely-additive PRs that clear the full
guard stack (additive-only → size cap → schema/PII/range/enum + corrupt-ratio →
anti-abuse) and **holds the rest for a human**. Because a Hugging Face repo is a
git repo, any merge is one corrective commit from reverted, and consumers can pin
a known-good revision. The guards prove rows are well-formed, PII-free, in-range,
and unremarkable — not that the numbers are *authentic*; versioning is the
recovery half of that story. The auto-merge bot needs a **fine-grained** HF token
(write + discussions, scoped to just the dataset) stored as the `HF_TOKEN` repo
secret.

## Repo layout

```
skills/growthkit/
  SKILL.md                      # orchestration + the honesty spine
  scripts/                      # deterministic, real-data-only (direct CLI flags)
    analyze_studio_csv.py       # ground truth
    saas_metrics.py  attribution_estimate.py  funnel_diagnose.py
    compliance.py               # hard gate
    build_plan.py               # renders the growth-plan.html deliverable
    fetch_trends.py             # optional, degrade-gracefully
    federation/                 # opt-in, self-growing community dataset
      validate.py               # stdlib-only schema/PII/range/abuse guards (single source)
      contribute.py             # write side: content-addressed append-only PRs
      refresh_dataset.py        # pull side: validate + dedup + rebuild benchmarks
      automerge.py              # safe unattended auto-merge bot (guard stack)
      notifications.py          # config-gated contribution nudge (user-facing)
  references/                   # playbook.md + benchmarks/markets/restricted/config JSON
.github/workflows/automerge.yml # daily cron that runs the auto-merge bot
tests/                          # 72 tests across all stages
examples/sample_studio_export.csv
```

## Development

```bash
python -m pytest tests/ -q
```

## Related projects (same honesty architecture)

GrowthKit is part of a family of **local-first, no-fabricated-numbers Claude
Code skills** — each with deterministic scripts, provenance envelopes, an HTML
deliverable, append-only local data, and an opt-in federated dataset:

- [**AppScope** (open-app-intel)](https://github.com/Ahad690/open-app-intel) —
  honest app market intelligence: local store-data capture and
  confidence-banded download/revenue estimates. If you run both, AppScope's
  download estimate can serve as one more owned signal in GrowthKit's
  triangulated attribution band.
- [**fiverr-gig-optimizer**](https://github.com/Ahad690/fiverr-gig-optimizer) —
  research-backed Fiverr gig catalogs with no guessed market numbers; also home
  to the reusable [HF auto-merge community-dataset pattern](https://github.com/Ahad690/fiverr-gig-optimizer/tree/main/patterns/hf-community-dataset)
  these projects share.

## License

- **Code:** MIT ([LICENSE](LICENSE))
- **Data & docs:** CC-BY-4.0 ([LICENSE-DATA](LICENSE-DATA))

Contributions welcome — see [CONTRIBUTORS.md](CONTRIBUTORS.md) and
[DATA_POLICY.md](DATA_POLICY.md).
