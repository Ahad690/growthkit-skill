# Data Policy

GrowthKit is **local-first**. Everything you analyze stays on your machine. The
only data that can ever leave is what **you** choose to contribute to the shared
trend dataset — and only after it has been stripped to a small, public,
anonymized schema and checked by a hard guard.

## What NEVER leaves your machine (P8)
- Raw TikTok Studio / Business Suite CSV exports.
- Any account handle, account name, username, profile URL, or email.
- Per-post identifiers (`video_id`, `post_id`) or per-post metrics
  (`views`, `likes`, `comments`, `profile_visits`).
- MMP / attribution exports, install-level rows, `install_id`, `device_id`,
  IP addresses, `user_id`.
- Your private analytics, your funnel numbers, your SaaS metrics.

These are enforced by `assert_public_only` in
`skills/growthkit/scripts/federation/contribute.py` (and re-checked on pull by
`refresh_dataset.validate_row`). If **any** of the banned fields appears in a
candidate contribution, the entire contribution is **refused** — proven by
`tests/test_contribution_guard.py`.

## The ONLY shareable schema (§8.3)
A contributed row contains exactly these fields and nothing else:

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

For `perf_benchmark` rows, `metric_value` is **aggregated** (e.g., the median of
a metric across your posts in a category) — never per-post, never tied to a
`video_id`, handle, or account.

## Contribution is OFF by default (FR21)
- Running `contribute.py` **without** `--dry-run` AND **with** an `HF_TOKEN`
  is the only way anything uploads. Missing either ⇒ nothing is sent.
- There is **no background upload**. Every run prints exactly what it would
  share so you can inspect it first.
- Preview safely any time:
  ```bash
  python3 skills/growthkit/scripts/federation/contribute.py --rows rows.json --dry-run
  ```

## How contributions are stored — stack, don't rewrite
Each contribution is **one new, content-addressed, append-only file** at
`contributions/<author>-<sha256(payload)[:10]>.json`. Contributors never collide
on a path, resubmitting identical data is idempotent (same hash → same filename),
and merging one PR can never clobber another. A Hugging Face repo is a git repo,
so every change is a commit with a SHA, and any merge is **one corrective commit
from being reverted**; consumers can pin a known-good revision so a bad merge
never reaches them.

## Auto-merge bot (safe, unattended)
Clean PRs are merged by `scripts/federation/automerge.py` (run on a daily GitHub
Actions cron). A PR merges **only if it clears every layer** of the guard stack:

| Layer | Stops | On fail |
|------|-------|---------|
| Additive-only | edits/deletes/overwrites, sneaked-in files (only new `contributions/*.json` allowed) | hold `unsafe_shape` |
| Size cap | flooding / DoS | hold `too_large` |
| Schema + PII + range + enum, then corrupt-ratio gate (0.0 ⇒ a single bad row holds the PR) | malformed/PII/out-of-range rows | hold/abort `corrupt` |
| Anti-abuse | duplicate flooding, group-median outliers vs a trusted reference | hold `suspicious` |

Anything that fails is **commented and left open for a human** — never silently
dropped. A token gate (no write token ⇒ nothing merges) and `--dry-run` round it out.

**Honest boundary:** these gates prove a row is well-formed, PII-free, in-range,
non-duplicate, and statistically unremarkable. They do **not** prove the numbers
are *authentic* — a patient adversary could submit plausible fake data. Prevention
narrows the blast radius; git versioning (revert + pinned revisions) guarantees
recovery.

## Token permissions (for the auto-merge bot only)
Use a **fine-grained** Hugging Face token (NOT an `hf auth login` OAuth token,
which expires and would silently break the scheduled run), scoped to **only**
`Ahad690/growthkit-trends`, with: write access to contents/settings (commits /
merge PRs) and "interact with discussions / open pull requests". Store it as the
GitHub repo secret `HF_TOKEN`. Reading the public dataset needs no token.

## Pulling community data
`refresh_dataset.py` pulls the shared dataset (no token needed to read),
validates every row (schema + range + enum + banned-field check), **refuses**
files whose corrupt ratio exceeds `max_corrupt_ratio` (default 0.25), **no-ops**
below `min_new_on_refresh` (default 50), then rebuilds the community benchmark
defaults with row-level dedup. Community benchmarks are labeled `measured` with a
coverage-aware confidence (`LOW` until a segment has enough rows). Preview with
`--dry-run`.

## License
The shared dataset is licensed **CC-BY-4.0** (see `LICENSE-DATA`). Code is MIT
(see `LICENSE`). Contribute via PR — see `CONTRIBUTORS.md`.
