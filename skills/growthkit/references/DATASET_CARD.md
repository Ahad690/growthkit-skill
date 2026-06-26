---
license: cc-by-4.0
language:
  - en
tags:
  - marketing
  - tiktok
  - short-form-video
  - saas
  - growth
  - trends
  - benchmarks
pretty_name: GrowthKit Trends
configs:
  - config_name: default
    data_files:
      - split: train
        path: contributions/*.json
---

# GrowthKit Trends

A **community, opt-in, federated** dataset of **public, anonymized** short-form
short-form-video trend and benchmark observations, contributed by users of the
open-source [**GrowthKit**](https://github.com/Ahad690/growthkit-skill) Claude
Code skill. It improves GrowthKit's *default* benchmarks over time so every
founder starts from better, source-tagged ranges instead of fabricated numbers.

> **Honesty first.** GrowthKit never lets a model invent a market metric. Numbers
> come from deterministic scripts run on a founder's own real exports. This
> dataset holds ONLY public, anonymized, aggregated observations — never owned
> analytics, handles, or per-post/per-install data.

## What is (and isn't) here

**Here:** public trending-hashtag/sound observations from TikTok Creative Center,
and **aggregated** performance benchmarks (e.g., the *median* of a metric across a
contributor's posts in a category).

**Never here (blocked by `assert_public_only` before any upload):** raw CSV
exports, account handles / names / usernames / profile URLs / emails, per-post
identifiers (`video_id`, `post_id`) or per-post metrics (`views`, `likes`,
`comments`, `profile_visits`), MMP/attribution exports, install-level rows,
`install_id`, `device_id`, IP addresses, `user_id`.

## Row schema

Each row is one JSON object with exactly these fields:

```json
{
  "platform": "tiktok",
  "data_type": "hashtag_trend | sound_trend | perf_benchmark",
  "industry": "string",
  "country": "string",
  "metric_name": "string",
  "metric_value": 0,
  "period_days": 7,
  "captured_on": "YYYY-MM-DD",
  "source": "creative_center | aggregated_owned"
}
```

| Field | Meaning |
|-------|---------|
| `platform` | Always `tiktok` in v1. |
| `data_type` | `hashtag_trend`, `sound_trend`, or `perf_benchmark`. |
| `industry` | Coarse industry/vertical label (e.g., `saas`, `fitness`). |
| `country` | ISO-style country code (e.g., `US`, `GB`). |
| `metric_name` | e.g. `publish_cnt`, `video_views`, `completion_rate_median`. |
| `metric_value` | Numeric. For `perf_benchmark` this is **aggregated** (e.g., a median), never per-post. |
| `period_days` | Observation window (default 7). |
| `captured_on` | Date the observation was captured (`YYYY-MM-DD`). |
| `source` | `creative_center` (public trend fetch) or `aggregated_owned` (anonymized aggregate of a contributor's own data). |

## How the data is stored — stack, don't rewrite

Each contribution is **one new, content-addressed, append-only file** at
`contributions/<author>-<sha256(payload)[:10]>.json` (a JSON array of rows).
Two contributors never collide on a path, resubmitting identical data is
idempotent (same hash → same filename), and merging one PR can never clobber
another. Because a Hugging Face repo is a git repo, every change is a commit with
a SHA and any merge is **one corrective commit from being reverted** — consumers
can also pin a known-good revision so a bad merge never reaches them.

## Auto-merge (safe, unattended)

Clean PRs are merged by a bot ([`automerge.py`](https://github.com/Ahad690/growthkit-skill/blob/main/skills/growthkit/scripts/federation/automerge.py),
run on a daily GitHub Actions cron). A PR merges **only if it clears every layer**
of the guard stack — additive-only (no removes/modifies; only new
`contributions/*.json`), size cap, per-row schema/PII/range/enum validation, a
corrupt-ratio gate (a single bad row holds the whole PR), and anti-abuse
heuristics (flooding, group-median outliers). Anything that fails is **commented
and left open for a human**, never silently dropped.

**Honest boundary:** these gates prove a row is well-formed, PII-free, in-range,
non-duplicate, and statistically unremarkable. They do **not** prove the numbers
are *authentic* — a patient adversary could submit plausible fake data. That
residual risk is why versioning/revert matters: prevention narrows the blast
radius; git versioning guarantees recovery.

## License

**CC-BY-4.0.** You may share and adapt with attribution. (GrowthKit *code* is MIT;
see the GitHub repo.)

## How to contribute (via PR)

Contribution is **off by default** and runs locally with the GrowthKit skill:

```bash
# 1. Preview EXACTLY what would be shared — no upload happens:
python3 skills/growthkit/scripts/federation/contribute.py --rows rows.json --dry-run

# 2. To actually open a dataset PR, set a token and drop --dry-run:
export HF_TOKEN=hf_...      # contributors only; never shipped
python3 skills/growthkit/scripts/federation/contribute.py --rows rows.json
```

The contributor's machine strips each row to the schema above, runs
`assert_public_only` (which **aborts the entire contribution** if any identifying
or owned field is present), dedups, and opens a **pull request** to this dataset.
Maintainers review PRs before merge. There is no background upload.

Pulling community data back into your local benchmarks:

```bash
python3 skills/growthkit/scripts/federation/refresh_dataset.py --dry-run
```

`refresh_dataset.py` validates every row (schema + range + banned-field check),
refuses corrupt-heavy files, no-ops below a minimum new-row threshold, and labels
community benchmarks with a coverage-aware confidence (`LOW` until a segment has
enough rows).

See [`DATA_POLICY.md`](https://github.com/Ahad690/growthkit-skill/blob/main/DATA_POLICY.md)
for the full policy.
