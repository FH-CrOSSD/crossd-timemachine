#!/usr/bin/env python3
"""Every published OpenSSF Scorecard weekly scan of the CrOSSD panel, from the project's BigQuery table.

The project announced in August 2026 that the table is no longer available; in November 2026 it could still be read,
with scans up to 2026-08-24. This secures the panel's rows once: scan date, scanned commit, Scorecard version,
aggregate and check scores (no reasons or details). The table is partitioned by date and not clustered, so the query
reads every partition in the range whatever the project filter; the dry run prints the bytes before anything is billed.

A scan dated d runs for about a week, so build.py dates its values at d + 7 days, not at d.

Output: data/raw/scorecard_history_<accessed>.parquet (one row per project and scan date), or --name

The free BigQuery tier is 1 TiB of queries a month; the dry run shows the cost first. Collected in two parts on
2026-11-12: scans from 2024-03 on, then the earlier ones (`--first 2021-09-01 --last 2024-02-29`).

Usage:
    GOOGLE_CLOUD_PROJECT=<billing project> python pipeline/collect_scorecard_history.py --max-gb 80
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "data" / "inputs"
TABLE = "`openssf.scorecardcron.scorecard-v2`"


def calling_project() -> str:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    env = ROOT / ".env"
    if not project and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("GOOGLE_CLOUD_PROJECT="):
                project = line.split("=", 1)[1].strip()
    if not project:
        raise SystemExit("GOOGLE_CLOUD_PROJECT is not set (.env or environment)")
    return project


def names() -> dict[str, str]:
    """github.com/<lowercase name> -> panel project, including canonical names of renamed projects."""
    panel = json.loads((INPUTS / "index_20261103.json").read_text())["snapshots"]
    out = {f"github.com/{p.lower()}": p for p in panel}
    for path in sorted(INPUTS.glob("cohort_*.csv")):
        cohort = pd.read_csv(path)
        if "canonical" in cohort:
            for p, c in zip(cohort.project, cohort.canonical):
                if isinstance(c, str):
                    out.setdefault(f"github.com/{c.lower()}", p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--first", default="2024-03-01")
    ap.add_argument("--last", default="2026-11-03")
    ap.add_argument("--max-gb", type=float, default=80.0)
    ap.add_argument("--name", default="", help="output name; default scorecard_history_<accessed>")
    args = ap.parse_args()
    mapping = names()
    sql = f"""SELECT date, repo.name AS name, repo.commit AS commit, scorecard.version AS version, score,
                     ARRAY(SELECT AS STRUCT x.name AS check_name, x.score AS check_score FROM UNNEST(checks) x) AS checks
              FROM {TABLE}
              WHERE date BETWEEN @first AND @last AND LOWER(repo.name) IN UNNEST(@names)"""
    params = [bigquery.ScalarQueryParameter("first", "DATE", args.first),
              bigquery.ScalarQueryParameter("last", "DATE", args.last),
              bigquery.ArrayQueryParameter("names", "STRING", sorted(mapping))]
    client = bigquery.Client(project=calling_project())
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False, query_parameters=params))
    gigabytes = dry.total_bytes_processed / 1e9
    print(f"scanning {gigabytes:.1f} GB", flush=True)
    if gigabytes > args.max_gb:
        raise SystemExit(f"above --max-gb {args.max_gb}")
    table = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result().to_dataframe(
        create_bqstorage_client=False)
    rows = []
    for r in table.itertuples():
        row = {"project": mapping[r.name.lower()], "scan": str(r.date), "commit": r.commit, "version": r.version,
               "aggregate": r.score}
        row |= {c["check_name"]: c["check_score"] for c in r.checks}
        rows.append(row)
    out = pd.DataFrame(rows).drop_duplicates(["project", "scan"]).sort_values(["project", "scan"])
    accessed = datetime.now(UTC).strftime("%Y-%m-%d")
    path = ROOT / "data" / "raw" / f"{args.name or f'scorecard_history_{accessed}'}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    print(f"{path.relative_to(ROOT)}: {len(out)} rows, {out.project.nunique()} of {len(set(mapping.values()))} projects, "
          f"scans {out.scan.min()} to {out.scan.max()} ({out.scan.nunique()} dates)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
