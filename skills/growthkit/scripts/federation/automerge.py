#!/usr/bin/env python3
"""automerge.py — safe auto-merge bot for the GrowthKit HF dataset.

Lists open PRs on `Ahad690/growthkit-trends` and merges only the ones that are
purely ADDITIVE and pass the full guard stack (schema / PII / range / enum +
corrupt-ratio + anti-abuse heuristics); everything else is commented and left
open for a human — never silently dropped. Reversible by design: HF repos are
git, so any merge is one corrective commit from gone (see DATA_POLICY.md).

Guard stack (a PR merges only if it clears EVERY layer):
  0. Scope        — only open pull requests.
  1. Additive-only — no removes/modifies; only new `contributions/*.json`.
  2. Size cap     — max_rows_per_pr.
  3. Schema+PII+range+enum per row, then corrupt-ratio gate (0.0 => any bad row holds).
  4. Anti-abuse   — flooding / outliers vs the trusted reference.
Plus a token gate (no write token => nothing merges) and --dry-run.

    python3 automerge.py --dry-run     # decide + report only
    python3 automerge.py               # merge clean PRs, hold the rest
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import validate  # the stdlib-only guard module in this folder

CONFIG = {
    "repo_id": "Ahad690/growthkit-trends",
    "repo_type": "dataset",
    "path_prefix": "contributions/",   # only NEW files here are auto-mergeable
    "file_ext": ".json",
    "max_rows_per_pr": 2000,
    "max_corrupt_ratio": 0.0,          # any invalid row holds the whole PR
    "schema": validate.GROWTHKIT_SCHEMA,
    "abuse": validate.GROWTHKIT_ABUSE,
    "dedup_key": validate.SHAREABLE,
    "reference_path": None,            # local JSON of trusted rows for outlier checks
}


def repo_id_from(s: str) -> str:
    return s.rstrip("/").split("datasets/")[-1].split("models/")[-1]


def additive_only(added, removed, modified, cfg):
    if removed:
        return False, f"removes {len(removed)} file(s)"
    if modified:
        return False, f"modifies {len(modified)} existing file(s)"
    if not added:
        return False, "no added files"
    bad = [f for f in added
           if not (f.startswith(cfg["path_prefix"]) and f.endswith(cfg["file_ext"]))]
    if bad:
        return False, f"adds non-contribution file(s): {bad[:3]}"
    return True, "additive only"


def _siblings(api, repo_id, repo_type, revision):  # pragma: no cover - network
    info = api.repo_info(repo_id=repo_id, repo_type=repo_type,
                         revision=revision, files_metadata=True)
    return {s.rfilename: getattr(s, "blob_id", None) for s in info.siblings}


def diff_files(api, repo_id, repo_type, pr_num):  # pragma: no cover - network
    main = _siblings(api, repo_id, repo_type, "main")
    pr = _siblings(api, repo_id, repo_type, f"refs/pr/{pr_num}")
    added = [f for f in pr if f not in main]
    removed = [f for f in main if f not in pr]
    modified = [f for f in pr if f in main
                and main[f] is not None and pr[f] is not None and main[f] != pr[f]]
    return added, removed, modified


def load_pr_rows(api, repo_id, repo_type, pr_num, files):  # pragma: no cover - network
    from huggingface_hub import hf_hub_download
    rows, errs = [], 0
    for fname in files:
        try:
            local = hf_hub_download(repo_id=repo_id, filename=fname,
                                    repo_type=repo_type, revision=f"refs/pr/{pr_num}")
            with open(local, encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception as exc:  # noqa: BLE001
            print(f"warning: PR #{pr_num} '{fname}' unreadable: {exc}", file=sys.stderr)
            errs += 1
            continue
        rows.extend(payload if isinstance(payload, list) else [payload])
    return rows, errs


def pr_verdict(added, removed, modified, rows, invalid, valid_new, errs, cfg, abuse_reasons):
    ok, why = additive_only(added, removed, modified, cfg)
    if not ok:
        return {"action": "hold", "status": "unsafe_shape", "reason": why}
    if cfg["max_rows_per_pr"] and rows > cfg["max_rows_per_pr"]:
        return {"action": "hold", "status": "too_large",
                "reason": f"{rows} rows > {cfg['max_rows_per_pr']}"}
    gate = validate.decide(rows, invalid, valid_new, 1, cfg["max_corrupt_ratio"], errs)
    if gate["action"] != "merge":
        return {"action": "hold", "status": gate["status"], "reason": gate["reason"]}
    if abuse_reasons:
        return {"action": "hold", "status": "suspicious", "reason": "; ".join(abuse_reasons)}
    return {"action": "merge", "status": "ok", "reason": gate["reason"]}


def main(argv=None):  # pragma: no cover - network
    ap = argparse.ArgumentParser(description="Auto-merge clean PRs to the GrowthKit HF dataset.")
    ap.add_argument("--repo", default=CONFIG["repo_id"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--token")
    args = ap.parse_args(argv)

    repo_id = repo_id_from(args.repo)
    rt = CONFIG["repo_type"]
    token = args.token or os.environ.get("HF_TOKEN")  # None -> cached login

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("error: pip install huggingface_hub", file=sys.stderr)
        return 1
    api = HfApi(token=token)

    reference = []
    if CONFIG.get("reference_path") and os.path.exists(CONFIG["reference_path"]):
        with open(CONFIG["reference_path"], encoding="utf-8") as fh:
            reference = json.load(fh)

    prs = list(api.get_repo_discussions(repo_id=repo_id, repo_type=rt,
                                        discussion_type="pull_request",
                                        discussion_status="open"))
    actions = []
    for pr in prs:
        added, removed, modified = diff_files(api, repo_id, rt, pr.num)
        rows, errs = load_pr_rows(api, repo_id, rt, pr.num, added)
        valid, invalid = validate.partition(rows, CONFIG["schema"])
        valid_new = validate.dedup_count(valid, CONFIG["dedup_key"])
        abuse = validate.abuse_scan(valid, reference, CONFIG.get("abuse", {}))
        v = pr_verdict(added, removed, modified, len(rows), len(invalid),
                       valid_new, errs, CONFIG, abuse)
        entry = {"pr": pr.num, "title": pr.title, "rows": len(rows),
                 "invalid": len(invalid), **v}
        if not args.dry_run:
            try:
                if v["action"] == "merge":
                    api.merge_pull_request(repo_id, pr.num, repo_type=rt,
                                           comment=f"Auto-merged: {v['reason']}.")
                    entry["merged"] = True
                else:
                    api.comment_discussion(repo_id, pr.num, repo_type=rt,
                                           comment=f"Held ({v['status']}): {v['reason']}. "
                                                   f"Needs human review.")
                    entry["merged"] = False
            except Exception as exc:  # noqa: BLE001
                entry["error"] = str(exc)
        actions.append(entry)

    print(json.dumps({"repo": repo_id, "open_prs": len(prs),
                      "merged": sum(1 for a in actions if a.get("merged")),
                      "held": sum(1 for a in actions if a["action"] == "hold"),
                      "dry_run": args.dry_run, "actions": actions}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
