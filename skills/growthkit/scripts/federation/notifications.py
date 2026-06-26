#!/usr/bin/env python3
"""notifications.py — the user-facing contribution nudge.

A self-growing dataset needs people to actually contribute, so prompt them — but
put the nudge where the *user* sees it, NOT on stderr. In an agent-driven tool
(Claude Code), stderr is read by the agent, not the human, so a "please
contribute" line there is invisible to the end user. The skill therefore surfaces
this line in the final human-facing summary (stdout), gated by a config flag and
emitted only once, at the deliverable step.

  - Config-toggle, default on: `ui.contribution_reminder` in config.json.
  - Repo link read from the same config (`federation.dataset_repo`).
  - Both a plain-text line (for the CLI/agent summary) and an HTML banner (if a
    visual artifact is ever rendered) are provided.
"""
from __future__ import annotations

import html
import json
import os
from typing import Any, Optional


def _cfg(cfg: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    if cfg is not None:
        return cfg
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "..", "references", "config.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _enabled(cfg: dict[str, Any]) -> bool:
    return bool(cfg.get("ui", {}).get("contribution_reminder", True))


def _repo(cfg: dict[str, Any]) -> str:
    fed = cfg.get("federation", {})
    return fed.get("dataset_repo") or "https://huggingface.co/datasets/Ahad690/growthkit-trends"


def contribution_line_text(cfg: Optional[dict[str, Any]] = None) -> str:
    """Plain-text nudge for the CLI/agent final summary (stdout). '' if disabled."""
    cfg = _cfg(cfg)
    if not _enabled(cfg):
        return ""
    return (
        "✨ Help GrowthKit's benchmarks get better for everyone — contribute your "
        f"anonymized, public trend/benchmark rows: {_repo(cfg)} "
        "(opt-in, PII-guarded, --dry-run first). See DATA_POLICY.md."
    )


def contribution_banner_html(cfg: Optional[dict[str, Any]] = None) -> str:
    """HTML banner (or '' if disabled) for any rendered visual deliverable."""
    cfg = _cfg(cfg)
    if not _enabled(cfg):
        return ""
    repo = html.escape(_repo(cfg))
    return (
        '<div class="contrib" style="margin:12px 0;padding:10px 14px;'
        'border-left:4px solid #2d6;border-radius:8px;background:#0e1a12;'
        'color:#bdf5cf;font-size:14px">'
        '✨ Help this dataset grow — '
        f'<a href="{repo}" target="_blank" rel="noopener" '
        'style="color:#5ee08a;font-weight:600">contribute your anonymized data</a>'
        ' so everyone gets better results.</div>'
    )


if __name__ == "__main__":
    import sys
    try:  # the nudge contains an emoji; don't let a legacy console codec crash it
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    line = contribution_line_text()
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"))
