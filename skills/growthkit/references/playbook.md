# GrowthKit Playbook — short-form growth craft

> **Read this for judgment and language, not numbers.** Every quantitative claim
> in this file is either a labeled `heuristic` (an algorithm rule-of-thumb that
> creators repeat — NOT measured truth) or points you to a script that computes
> the real number from the founder's own data. The model must never restate a
> heuristic as a measured fact, and never invent a market/performance number
> (P1). When you need a number, run a script (§9) on real data.

---

## 1. Hook → Value → CTA structure

Every short-form script has three beats:

- **Hook (0–3s):** earn the next second. State the payoff, the tension, or the
  question. The first frame's on-screen text + the first spoken line both carry
  it (TikTok SEO indexes spoken words and on-screen text).
- **Value (3s–end):** deliver the thing the hook promised — a demo, a teaching
  moment, a transformation, a story. Keep one idea per video.
- **CTA:** one ask. B2C app → "try it / link in bio / search '[app]'." B2B →
  "comment a keyword for the template / follow for the series / book a demo."

### Validated hook formulas (language patterns, not guarantees)
- **Problem–agitate–reveal:** "If you [pain], stop doing [common mistake]."
- **Result-first:** "This is how we got [outcome] without [expected cost]."
- **Curiosity gap:** "Nobody tells you this about [topic]…"
- **Direct callout:** "[ICP], this one's for you."
- **Contrarian:** "Stop [common advice]. Do this instead."
- **Listicle:** "3 [tools/tricks] for [job-to-be-done]."
- **POV / relatable:** "POV: you're a [ICP] and [relatable pain]."

> `heuristic`: creators say a strong hook lifts the **3-second view-through**,
> which the algorithm reads as an early quality signal. We do NOT assert a
> numeric lift. We measure your real watch-through with `analyze_studio_csv.py`
> and flag posts below the configured 3-sec floor as `hook_failure`.

---

## 2. Algorithm rules-of-thumb (ALL `heuristic` — never present as measured)

These are widely-repeated creator beliefs. They are labeled `heuristic` and live
ONLY here. Do not emit them as `value`s; use them only to *tier* the founder's
own measured results (from `analyze_studio_csv.py`) and frame guidance.

- `heuristic`: ~**70%** average completion is often cited as a "viral-leaning"
  threshold for short videos; ~50% is "strong"; <30% is "weak." (`creator_lore`)
- `heuristic`: **shares + saves** are weighted more than likes as intent signals.
- `heuristic`: the **first hour**'s engagement velocity influences distribution.
- `heuristic`: **watch time %** matters more than absolute views for small accounts.
- `heuristic`: **niche consistency** (clear pillars) helps the algorithm classify
  and re-serve your account.

The real, measured versions of completion/watch/share for *your* posts come from
the CSV analyzer. Benchmarks for your (industry, country) segment come from
`benchmarks.json` (LOW confidence until the federated dataset fills the segment).

---

## 3. Content pillars (60/30/10) — see `config.json` pillar_split

- **60% Educational** — teach the job-to-be-done your product serves. Builds
  authority and search surface (TikTok SEO). Mostly non-promotional.
- **30% Entertainment / relatability** — trends, POVs, behind-the-scenes,
  founder personality. Builds reach and saves.
- **10% Promotional** — direct product/feature/offer. **Every promotional post
  must pass the compliance gate (`compliance.py`) and carry the disclosure
  block.**

The planner (SKILL Step) emits a 2–4 week calendar respecting this split and the
chosen platform variant.

---

## 4. Branch by ICP — B2C-install vs B2B-leadgen

### B2C app-install variant
- **Goal:** installs / activations, not vanity reach.
- **Content:** problem→app-as-solution demos, transformation/before-after
  (mind restricted-category claims), relatable POVs, UGC-style.
- **CTA:** "search [app] in the App Store / link in bio." App Store search beats
  fragile deep links.
- **Measurement:** organic installs are triangulated (see §6) — never a precise
  count. Use `attribution_estimate.py`.

### B2B-leadgen variant
- **Goal:** awareness + qualified leads, NOT installs. Longer cycle.
- **Content:** founder POV, customer-pain education, product demos/teardowns,
  "how we built/sell X," thought leadership. Authenticity > production polish.
- **CTA:** "comment [keyword] for the template," "follow for the series,"
  "book a demo (link in bio)." Capture to a lead magnet / waitlist.
- **Measurement:** track lead-gen funnel (`funnel_diagnose.py`) and SaaS metrics
  (`saas_metrics.py`); attribute via UTM'd link-in-bio + self-report on demo
  forms ("how did you hear about us?").

---

## 5. Branch by market — TikTok-native vs Reels/Shorts-native

`markets.json` sets per-country status (`available|weak|banned`). When the
founder's primary market is `weak`/`banned` (e.g., India, Pakistan), default to
the **Reels/Shorts-native** playbook and say why. The craft transfers; the deltas:

- **Instagram Reels:** lean into shares to Stories/DMs and saves; trending audio
  pool differs; on-screen captions still matter; link-in-bio via the profile.
- **YouTube Shorts:** stronger search/SEO longevity; titles + spoken keywords
  matter more; Shorts can funnel to long-form. Less ephemeral than TikTok.
- **TikTok as a leading indicator:** even where TikTok is banned for *posting*,
  Creative Center trends (if fetchable) can hint at formats/sounds rising
  globally — labeled `external_best_effort`, never required.

> `heuristic`: Reels rewards saves/sends heavily; Shorts rewards
> swipe-away-rate avoidance and search. Treat as lore, measure with owned data.

---

## 6. Attribution reality (organic short-form → installs/signups)

There is **no pixel on organic posts.** Attribution is structurally approximate
(P4). Triangulate the founder's OWN signals via `attribution_estimate.py`:

- UTM'd link-in-bio / landing-page installs
- promo-code redemptions
- brand-search lift (App Store search volume / branded web search) in a window
- MMP "organic" bucket export (AppsFlyer/Branch/Adjust)
- post-install survey ("How did you hear about us?")

The output is a **band with a confidence label**, never a single precise number.
Deferred deep links are **not** reliable for attribution — surface this caveat.

---

## 7. Compliance (hard gate — see `compliance.py`)

- **Music (FR14):** business accounts use **Commercial Music Library** or
  original/owned audio ONLY. Never reuse a trending commercial sound on a
  business account (Sony/USC-type lawsuits, up to ~$150k/work). Personal/creator
  accounts have more latitude but cross-platform reuse needs a separate license.
- **Disclosure (FR15):** any promotional/branded post must enable TikTok's
  Commercial Content Disclosure toggle AND carry a first-line + spoken + on-screen
  disclosure. A bio disclosure does NOT cover a post. `#ad` alone is insufficient.
  Disclosed content has **no reach penalty** (per TikTok's own large study; tested
  in ID and PK).
- **Restricted categories (FR16):** screen against `restricted_categories.json`
  (crypto, financial, health/supplements, alcohol, etc.) before generating a
  campaign; adjust claims and flag approval-gating.
- **Repurposing (FR17):** export a **clean master**; never download the
  watermarked TikTok and re-upload (Reels/Shorts down-rank foreign watermarks).

---

## 8. Cold-start & shadowban guidance (heuristics, labeled)

- `heuristic`: post natively (in-app or via official tools); third-party
  schedulers that strip native signals can hurt cold-start. **No automation /
  bots** (N5) — auto-follow/engagement risks bans.
- `heuristic`: a brand-new account benefits from clear niche consistency early so
  the algorithm can classify it.
- **Suspected shadowban:** check for guideline strikes, avoid banned hashtags,
  pause and post original clean content; there is no reliable "reset" trick —
  treat claims of one as lore.
- We never promise a numeric reach recovery; measure with owned data over time.

---

## 9. Repurposing workflow (clean-master)

1. Edit and export a **clean master** (no TikTok watermark) from your editor.
2. Re-upload **natively** to each platform (TikTok, Reels, Shorts) with
   platform-appropriate captions/audio.
3. Remember: **CML clearance is TikTok-only** — using the same track on Reels/
   Shorts may need a separate license.
4. Never "save the TikTok and post it everywhere" — the watermark gets
   down-ranked. (Enforced by `compliance.screen_repurposing`.)

---

## 10. Case-study patterns (numbers are `self_reported`)

Teach the *patterns* (consistent posting, strong hooks, niche clarity,
founder-led B2B content, UGC for B2C apps). Any growth numbers attached to named
case studies (e.g., Turbo AI, Cal AI, StudyFetch, Deepstash, TripBFF) are
**self/agency-reported** — label them as such and never present them as measured
benchmarks or as something this skill can reproduce.
