#!/usr/bin/env python3
"""CrOSSD readings over time: /api/metrics per panel project, the first snapshot of each month or every snapshot.

The cache of the replication package holds the snapshots around its two freeze dates and 93 long series. This crawl
adds one snapshot per project and calendar month, from the frozen snapshot index (`inputs/index_20261103.json`), up to
the data freeze. Responses are stored as returned; dating by `bak.timestamp` / `metrics.timestamp` happens in build.py.

Append-only and resumable: keys already in either cache are skipped, results are flushed every 200 responses.

With --every, the remaining snapshots follow, so every snapshot of the frozen index is read once.

Outputs (one gzip member per flush):
  data/raw/crossd_metrics_monthly.jsonl.gz   first snapshot per month
  data/raw/crossd_metrics_rest.jsonl.gz      every other snapshot (--every)

Usage:
    python pipeline/crawl_crossd.py --workers 4
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "data" / "inputs"
MONTHLY = ROOT / "data" / "raw" / "crossd_metrics_monthly.jsonl.gz"
REST = ROOT / "data" / "raw" / "crossd_metrics_rest.jsonl.gz"
API = os.environ.get("CROSSD_API", "https://health.crossd.tech/api")
FREEZE = datetime(2026, 11, 3, 23, 59, 59, tzinfo=UTC).timestamp()


def cached_keys(path: Path) -> set[tuple[str, float]]:
    keys = set()
    if path.exists():
        with gzip.open(path, "rt") as fh:
            for line in fh:
                rec = json.loads(line)
                keys.add((rec["project"], rec["snapshot_ts"]))
    return keys


def wanted(every: bool = False) -> list[tuple[str, float]]:
    snapshots = json.loads((INPUTS / "index_20261103.json").read_text())["snapshots"]
    keys = []
    for project, stamps in snapshots.items():
        seen = set()
        for ts in sorted(t for t in stamps if t <= FREEZE):
            month = datetime.fromtimestamp(ts, UTC).strftime("%Y-%m")
            if every or month not in seen:
                seen.add(month)
                keys.append((project, ts))
    return keys


def post(session: requests.Session, project: str, ts: float, tries: int = 5):
    for attempt in range(tries):
        try:
            resp = session.post(f"{API}/metrics", json={"term": project, "timestamp": ts}, timeout=120)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                return None
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError(f"{project} {ts}: no answer after {tries} tries")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--every", action="store_true", help="every snapshot, not only the first per month")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many requests (0: all)")
    args = ap.parse_args()
    OUT = REST if args.every else MONTHLY
    done = cached_keys(INPUTS / "metrics.jsonl.gz") | cached_keys(MONTHLY) | cached_keys(REST)
    todo = [k for k in wanted(args.every) if k not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} snapshots to fetch with {args.workers} workers", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    buffer, failed, count, start = [], [], 0, time.time()

    def flush() -> None:
        if buffer:
            with gzip.open(OUT, "at") as fh:
                fh.writelines(json.dumps(r) + "\n" for r in buffer)
            buffer.clear()

    with ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(post, session, p, ts): (p, ts) for p, ts in todo}
        for fut in as_completed(futures):
            project, ts = futures[fut]
            try:
                buffer.append({"project": project, "snapshot_ts": ts, "response": fut.result(),
                               "fetched": datetime.now(UTC).isoformat()})
            except RuntimeError as err:
                failed.append(str(err))
            count += 1
            if len(buffer) >= 200:
                flush()
            if count % 1000 == 0:
                rate = count / (time.time() - start)
                print(f"{count}/{len(todo)}, {rate:.1f}/s, {len(failed)} failed", flush=True)
    flush()
    print(f"done: {count} requests, {len(failed)} failed", flush=True)
    for line in failed[:20]:
        print(line)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
