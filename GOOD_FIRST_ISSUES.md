# Good First Issues — seed list

16 small, well-scoped tasks that make good first PRs. Label them `good first issue`;
this is the **fork-funnel** that drove 11.5k forks on comparable repos.

| # | Title | Area | Acceptance |
|---|-------|------|-----------|
| 1 | Add a YouTube Studio CSV parser | parsers | parses export into the envelope; test on a fixture |
| 2 | Add an Instagram/Reels insights parser | parsers | new parser + test |
| 3 | Add a LinkedIn analytics parser | parsers | new parser + test |
| 4 | Add `--json` output to the plan builder | feature | emits the plan as JSON; schema test |
| 5 | Add a dark-mode theme to `growth-plan.html` | ui | `prefers-color-scheme: dark`; screenshot in PR |
| 6 | Add a disclosure template for EU/UK ad rules | compliance | new template + test that the gate uses it |
| 7 | Add a disclosure template for FTC (US) | compliance | new template + test |
| 8 | Document the confidence envelope schema | docs | one markdown page with examples |
| 9 | Add an example TikTok Studio CSV fixture | examples | realistic anonymized sample under `examples/` |
| 10 | Validate that no heuristic leaks as a value | validation | test asserts heuristics never emitted as numbers |
| 11 | Add a `make test` / `just test` shortcut | dx | one-command test run + README note |
| 12 | Improve the "network disabled" empty-state | ux | trend section renders an honest fallback; test |
| 13 | Add alt-text lint for README images | a11y | script flags `<img>` missing `alt` |
| 14 | Localize `growth-plan.html` labels (Spanish) | i18n | `.es` label set + test |
| 15 | Add a `pre-commit` config running pytest | dx | `.pre-commit-config.yaml` + docs |
| 16 | Add a CONTRIBUTORS shout-out to the README | community | auto-updatable contributors section |

## Creating them

Run a `gh issue create` loop (see the fiverr repo's `GOOD_FIRST_ISSUES.md` for a
template script), or create by hand. **Creating public issues is outward-facing and
hard to undo — start with 5–8 and review before sharing.**

Suggested labels: `good first issue` (color `7057ff`), `hacktoberfest` (`ff6b35`).
