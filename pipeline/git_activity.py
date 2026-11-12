#!/usr/bin/env python3
"""Dated commit and tag activity per project, from the commit-only clones of the replication source.

The clones are read, never written (`git --git-dir ... log`). Only timestamps leave this script: no
author, no message, no hash. Commits are counted by committer date on the default branch (HEAD of
the bare clone); tags by their creation date.

Output: data/inputs/git_activity.parquet  project, month (first day, UTC), commits, tags
        data/inputs/git_last.parquet      project, last_commit, last_tag, first_commit

Usage:
    python pipeline/git_activity.py [--source ../oss-score-validity] [--workers 8]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "data" / "inputs"


def git(gitdir: Path, *args: str) -> list[int]:
    out = subprocess.run(
        ["git", f"--git-dir={gitdir}", *args], capture_output=True, text=True, check=False
    )
    return [int(x) for x in out.stdout.split() if x.strip().lstrip("-").isdigit()]


# Events are read up to the outcome data freeze of the replication package. Later and clock-skewed
# commit dates (some clones carry dates weeks in the future) are dropped, not clamped.
FREEZE = int(datetime(2026, 11, 3, 23, 59, 59, tzinfo=UTC).timestamp())


def read(gitdir: Path) -> tuple[str, list[int], list[int]]:
    commits = [t for t in git(gitdir, "log", "--format=%ct", "HEAD") if 0 < t <= FREEZE]
    tags = [t for t in git(gitdir, "for-each-ref", "refs/tags", "--format=%(creatordate:unix)") if 0 < t <= FREEZE]
    return gitdir.name.removesuffix(".git"), commits, tags


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=os.environ.get("OSS_SCORE_VALIDITY", str(Path(__file__).resolve().parents[2] / "oss-score-validity")))
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    clones = sorted((Path(args.source).expanduser() / "data" / "raw" / "git").glob("*.git"))

    cohort = pd.concat(
        pd.read_csv(INPUTS / f"cohort_{d}.csv", usecols=["project"]) for d in ("2024-08-01", "2025-01-01")
    ).drop_duplicates()
    by_key = {p.replace("/", "__").lower(): p for p in cohort.project}

    activity, last = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for key, commits, tags in pool.map(read, clones):
            project = by_key.get(key.lower())
            if project is None:
                continue
            for kind, stamps in (("commits", commits), ("tags", tags)):
                if stamps:
                    months = pd.to_datetime(pd.Series(stamps), unit="s").dt.to_period("M")
                    for month, n in months.value_counts().items():
                        activity.append({"project": project, "month": month.start_time.tz_localize("UTC"), "kind": kind, "n": int(n)})
            last.append({
                "project": project,
                "first_commit": min(commits) if commits else None,
                "last_commit": max(commits) if commits else None,
                "last_tag": max(tags) if tags else None,
            })

    table = pd.DataFrame(activity)
    table = table.pivot_table(index=["project", "month"], columns="kind", values="n", fill_value=0).reset_index()
    table.columns.name = None
    for col in ("commits", "tags"):
        if col not in table:
            table[col] = 0
    table[["project", "month", "commits", "tags"]].to_parquet(INPUTS / "git_activity.parquet", index=False)
    pd.DataFrame(last).to_parquet(INPUTS / "git_last.parquet", index=False)
    print(f"{len(last)} projects with a clone, {len(table)} project-months")
    return 0


if __name__ == "__main__":
    sys.exit(main())
