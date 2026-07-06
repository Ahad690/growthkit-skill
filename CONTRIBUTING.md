# Contributing to GrowthKit

Thanks for helping build marketing numbers you can audit. **First-timers welcome** —
this repo is deliberately friendly to your first open-source PR.

## Your first PR in 10 minutes

```bash
git clone https://github.com/Ahad690/growthkit-skill && cd growthkit-skill
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt pytest
pytest -q                                        # 84 tests — should be green
```

Pick a [`good first issue`](https://github.com/Ahad690/growthkit-skill/labels/good%20first%20issue),
comment to claim it, open a PR.

## The one rule (non-negotiable)

**The model never invents a metric.** Every market/performance number comes from a
deterministic script on the user's real export, wrapped in a confidence envelope, or
it is not emitted. The compliance gate is a **hard gate**, not a suggestion. See
`AGENTS.md` for the full contract.

## What makes a good PR here

- **Small and scoped.** One issue, one PR, with a test. Keep `pytest -q` green.
- **Honest.** New export parsers (with provenance), new deterministic metrics, new
  disclosure templates, docs, and platform adapters are welcome. "Make the AI estimate
  reach/CAC" is not.

## Good areas to contribute

- New **platform export parsers** (YouTube Studio, Instagram/Reels, LinkedIn).
- New **disclosure/compliance templates** for additional regions.
- New **deterministic metrics** with clear method + sources.
- Localization, docs, examples, and test coverage.

By contributing you agree your work is licensed like the rest of the repo.
