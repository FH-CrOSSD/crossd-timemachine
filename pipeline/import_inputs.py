#!/usr/bin/env python3
"""Copy the frozen inputs from the replication source into data/inputs/, read only at the source.

Each file is copied once and listed in data/inputs/MANIFEST.json with its source path and SHA-256.
A file that is already present with a different checksum stops the run: inputs are frozen, a changed
source must be a deliberate new import.

Usage:
    python pipeline/import_inputs.py [--source ../oss-score-validity]
"""

from __future__ import annotations

import argparse
import os
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "data" / "inputs"

# (path in the source repository, what it is, licence)
FILES = [
    ("data/raw/crossd/index_20261103.json", "CrOSSD project list and snapshot timestamps", "CrOSSD, free use (T. Dam, 2026-11-12)"),
    ("data/raw/crossd/strata/most-starred-repos.yaml", "CrOSSD crawl list, most-starred, of 2024-04-09", "Apache-2.0 (FH-CrOSSD/crossd)"),
    ("data/raw/crossd/strata/random-sample-repos.yaml", "CrOSSD crawl list, random sample, of 2024-04-09", "Apache-2.0 (FH-CrOSSD/crossd)"),
    ("data/raw/crossd/strata/netidee_configmap.yaml", "CrOSSD crawl list, netidee projects, from 2025-07", "Apache-2.0 (FH-CrOSSD/crossd)"),
    ("data/raw/crossd/metrics.jsonl.gz", "raw /api/metrics responses, cache of 2026-11-03/04", "CrOSSD, free use (T. Dam, 2026-11-12)"),
    ("analysis/01_cohort/cohort_2024-08-01.csv", "frozen cohort at 1 Aug 2024", "replication package"),
    ("analysis/01_cohort/cohort_2025-01-01.csv", "robustness cohort at 1 Jan 2025", "replication package"),
    ("data/raw/criticality/history_cohort_2024-08-01.parquet", "published OpenSSF Criticality lists 2022-11 to 2025-07, cohort rows", "Apache-2.0 (ossf/criticality_score)"),
    ("data/processed/scorecard_published_2024-07-29.parquet", "published Scorecard results, scan of 29 Jul 2024", "CDLA-Permissive-2.0"),
    ("data/processed/scorecard_published_2024-12-30.parquet", "published Scorecard results, scan of 30 Dec 2024", "CDLA-Permissive-2.0"),
    ("data/raw/scorecard/published_2026-11-04.jsonl", "api.scorecard.dev, one request per cohort repository", "CDLA-Permissive-2.0"),
    ("data/processed/features/scorecard_2024-08-01.parquet", "Scorecard checks rebuilt at the last commit before 1 Aug 2024", "replication package"),
    ("data/processed/features/scorecard_maintained_2025-01-01.parquet", "Scorecard Maintained rebuilt at 1 Jan 2025", "replication package"),
    ("data/processed/features/opencode_2024-08-01.parquet", "openCode rules rebuilt at 1 Aug 2024", "replication package"),
    ("data/processed/features/opencode_2025-01-01.parquet", "openCode rules rebuilt at 1 Jan 2025", "replication package"),
    ("data/processed/github_meta_2025-01-01.parquet", "GitHub metadata incl. archivedAt, read 2026-11-04", "GitHub terms"),
    ("data/raw/github/gone_2024-08-01.jsonl", "Software Heritage visits of repositories gone from GitHub", "CC-BY 4.0"),
    ("data/processed/attached_advisories_2024-08-01.parquet", "severe advisories attached to cohort projects, published 1 Aug 2024 to 31 Jul 2026", "OSV, per source database"),
    ("data/processed/attached_advisories_2025-01-01.parquet", "the same for the robustness cohort, published in 2025", "OSV, per source database"),
    ("data/probes/backdating.csv", "which components can be backdated, and why", "replication package"),
    ("data/claims/claims.csv", "documented claims per component, quoted with source", "per source"),
    ("analysis/04_validity/measured_validity.csv", "measured validity per score (quoted, never recomputed)", "replication package"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=os.environ.get("OSS_SCORE_VALIDITY", str(Path(__file__).resolve().parents[2] / "oss-score-validity")))
    args = ap.parse_args()
    source = Path(args.source).expanduser()
    INPUTS.mkdir(parents=True, exist_ok=True)
    manifest_path = INPUTS / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    for rel, what, licence in FILES:
        src = source / rel
        dst = INPUTS / Path(rel).name
        digest = sha256(src)
        known = manifest.get(dst.name)
        if known and known["sha256"] != digest:
            raise SystemExit(f"{rel}: source changed since import ({known['sha256'][:12]} -> {digest[:12]})")
        if not dst.exists() or sha256(dst) != digest:
            shutil.copy2(src, dst)
        manifest[dst.name] = known or {
            "source": f"oss-score-validity/{rel}",
            "what": what,
            "licence": licence,
            "imported": datetime.now(UTC).date().isoformat(),
            "sha256": digest,
        }
        print(f"{dst.name:52s} {digest[:16]}")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
