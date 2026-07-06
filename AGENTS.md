# AGENTS.md — running GrowthKit from any agentic CLI

GrowthKit is a **Claude Code skill**, but CLI-agnostic: the intelligence lives in
`skills/growthkit/SKILL.md` plus deterministic Python scripts, so any agentic coding
CLI (Claude Code, Codex, OpenCode, Cursor, Gemini CLI, Copilot CLI, Qwen, Kimi, Grok)
can drive it. This file is the entry point those tools read.

## The one rule you may never break

**The model never emits a market/performance number.** Views, completion rate,
followers, installs, CAC, LTV, hashtag volume — these come **only** from deterministic
scripts run on the user's **own real exports** (TikTok Studio / Business Suite CSV,
analytics/MMP exports), or from a clearly-labeled external fetch. The LLM does
positioning, scripts, calendars, and diagnosis — in **words**. Missing data ⇒ ask for
the export or say "no data." Never fabricate.

Every number carries an envelope: `{value, low, high, confidence∈{LOW,MEDIUM,HIGH},
method, sources, flags}`. Heuristics (e.g. "~70% completion ≈ viral") are labeled
`heuristic`, live only in `playbook.md`, and are **never** emitted as a value.

## How to run it

1. Read `skills/growthkit/SKILL.md` — the full operating procedure.
2. Ask the user for their platform exports; owned data is ground truth.
3. Produce numbers only via the deterministic scripts under `skills/growthkit/scripts/`
   (CSV analysis, envelope builders). The trend fetcher is **optional** and degrades
   gracefully — every other feature works with the network disabled.
4. Render `growth-plan.html` — the deliverable — with confidence, method, and sources
   on every number, and disclosure blocks on every script/calendar.

## Contract enforcement

`pytest -q` (84 tests) encodes the honesty rules and the compliance gate. A change that
lets the model author a metric, or that softens the compliance gate from a hard gate to
a suggestion, is a bug — not a feature.
