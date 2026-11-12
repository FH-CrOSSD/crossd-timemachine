#!/usr/bin/env python3
"""Every number of the demo paper, as LaTeX macros, from the built data in web/static/data/.

Lead time and look-alikes follow the rules of web/src/lib/hindsight.ts: the unbroken run at or below the operating
point that still stands at the event, read before it; the cohort split at the operating point by each project's latest
reading at t0, events counted from t0 to the data freeze.

Output: paper/generated/numbers.tex

Usage:
    python pipeline/paper_numbers.py [--project minio/minio] [--event archived] [--t0 2024-08-01]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "static" / "data"
OUT = ROOT / "paper" / "generated" / "numbers.tex"
FAILURE = {"archived", "gone", "dormant"}
DAY = 86400


def thousands(v: float) -> str:
    return f"{int(round(v)):,}".replace(",", "{,}")


def day(ts: float) -> str:
    d = pd.Timestamp(ts, unit="s")
    return f"{d.day} {d:%B} {d.year}"


def months(seconds: float) -> str:
    return f"{round(seconds / DAY / 30.44)}"


def macro(name: str) -> str:
    return re.sub(r"[^A-Za-z]", "", name.title())


def lead(series: pd.DataFrame, flag_max: float) -> tuple[float, float] | None:
    values = series.dropna(subset=["value"]).sort_values("observed")
    if values.empty or values.value.iloc[-1] > flag_max:
        return None
    flagged = (values.value <= flag_max).to_numpy()
    i = len(values) - 1
    while i > 0 and flagged[i - 1]:
        i -= 1
    return float(values.observed.iloc[i]), float(values.observed.iloc[-1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", default="minio/minio")
    ap.add_argument("--event", default="archived")
    ap.add_argument("--t0", default="2024-08-01")
    ap.add_argument("--shot", default="2026-04-20", help="t0 of the screenshot")
    args = ap.parse_args()
    meta = json.loads((DATA / "meta.json").read_text())
    projects = pd.read_parquet(DATA / "projects.parquet")
    readings = pd.read_parquet(DATA / "readings.parquet")
    events = pd.read_parquet(DATA / "events.parquet")
    validity = pd.read_parquet(DATA / "validity.parquet")
    m: dict[str, str] = {}

    # The record
    m["Projects"] = thousands(len(projects))
    m["Cohort"] = thousands(projects.in_cohort.sum())
    m["Readings"] = thousands(len(readings))
    m["ReadingsMillions"] = f"{len(readings) / 1e6:.1f}"
    for inst, part in readings.groupby("instrument"):
        m[f"Readings{macro(inst)}"] = thousands(len(part))
        m[f"Projects{macro(inst)}"] = thousands(part.project.nunique())
    crossd = readings[readings.instrument == "crossd"]
    per = crossd.groupby("project")["observed"].nunique()
    m["CrossdDatesMedian"] = thousands(per.median())
    m["CrossdSnapshots"] = thousands(crossd.snapshot.dropna().nunique())
    lag = (crossd.observed - crossd.snapshot).dropna() / DAY
    lag = lag[lag >= 0]
    m["LagMedianDays"] = f"{lag.median():.1f}"
    m["LagMaxDays"] = thousands(lag.max())
    m["LagOverWeek"] = f"{100 * (lag > 7).mean():.0f}\\%"
    scans = readings[(readings.instrument == "scorecard") & readings.source.str.contains("published scan")]
    m["ScorecardScans"] = thousands(scans.source.nunique())
    m["ScorecardFirst"] = day(scans.observed.min() - 7 * DAY)
    m["ScorecardLast"] = day(scans.observed.max() - 7 * DAY)
    m["CrossdFirst"] = day(crossd.observed.min())
    m["Evidence"] = thousands(readings.evidence.nunique())
    m["Recorded"] = thousands((readings.evidence == "recorded").sum())
    m["Reconstructed"] = thousands((readings.evidence == "reconstructed").sum())
    m["Events"] = thousands(len(events))
    for kind, part in events.groupby("kind"):
        m[f"Events{macro(kind)}"] = thousands(len(part))
    m["Freeze"] = day(pd.Timestamp(meta["data_freeze"]).timestamp())
    m["DataMB"] = f"{sum(p.stat().st_size for p in DATA.glob('*')) / 1e6:.1f}"
    catalogue = pd.read_parquet(DATA / "components.parquet")
    m["ScorecardChecks"] = thousands(((catalogue.instrument == "scorecard") & ~catalogue.component.str.startswith("aggregate")).sum())
    m["Components"] = thousands(len(pd.read_parquet(DATA / "components.parquet")))
    m["Flags"] = thousands(validity.flag_max.notna().sum())

    # Measured validity, quoted from the paper through the sentences the page shows
    for v in validity.itertuples():
        found = re.search(r"AUROC ([0-9.]+) \(95% interval ([0-9.]+) to ([0-9.]+)\)", v.sentence)
        if found:
            key = macro(v.component)
            m[f"Valid{key}Auc"], m[f"Valid{key}Lo"], m[f"Valid{key}Hi"] = found.groups()

    # The walkthrough: lead times before one event of one project
    ev = events[(events.project == args.project) & (events.kind == args.event)].dropna(subset=["date"]).sort_values("date")
    if not ev.empty:
        when = float(ev.date.iloc[0])
        m["CaseEventDate"] = day(when)
        mine = readings[(readings.project == args.project) & (readings.observed < when)]
        leads = []
        for f in validity[validity.flag_max.notna() & (validity.against == "failure")].itertuples():
            run = lead(mine[(mine.instrument == f.instrument) & (mine.component == f.component)], f.flag_max)
            if run:
                leads.append((f.component, run))
        for component, (since, last) in leads:
            key = macro(component)
            m[f"CaseLead{key}Since"] = day(since)
            m[f"CaseLead{key}Months"] = months(when - since)
        m["CaseLeads"] = thousands(len(leads))
    t0_case = pd.Timestamp(args.t0, tz="UTC").timestamp()
    at = readings[(readings.project == args.project) & (readings.observed <= t0_case)].sort_values("observed")
    flagged_at = 0
    for f in validity[validity.flag_max.notna()].itertuples():
        last = at[(at.instrument == f.instrument) & (at.component == f.component)].dropna(subset=["value"]).tail(1)
        flagged_at += int(len(last) == 1 and last.value.iloc[0] <= f.flag_max)
    m["CaseFlagsAtTzero"] = thousands(flagged_at)
    shot = pd.Timestamp(args.shot, tz="UTC").timestamp()
    m["CaseShot"] = day(shot)
    if not ev.empty:
        m["CaseShotDaysBefore"] = thousands((float(ev.date.iloc[0]) - shot) / DAY)
    m["CaseFlagsAtTzeroWord"] = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}.get(flagged_at, thousands(flagged_at))
    m["FlagsWord"] = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}.get(int(validity.flag_max.notna().sum()), m["Flags"])
    m["CaseTzero"] = day(t0_case)
    m["CaseUnfixed"] = thousands(((events.project == args.project) & (events.kind == "advisory")
                                  & events.detail.str.contains("no fixed version", case=False)).sum())

    # Look-alikes at t0 for each operating point (descriptive, as the page shows them)
    t0 = pd.Timestamp(args.t0, tz="UTC").timestamp()
    cohort = set(projects[projects.in_cohort].project)
    dated = events.dropna(subset=["date"])
    for f in validity[validity.flag_max.notna() & validity.against.notna()].itertuples():
        hit_events = dated[(dated.date > t0) & (dated.kind.isin(FAILURE) if f.against == "failure" else
                                                 (dated.kind == "advisory") & dated.detail.str.contains("no fixed version|KEV", case=False))]
        hit = set(hit_events.project)
        part = readings[(readings.instrument == f.instrument) & (readings.component == f.component) & (readings.observed <= t0)]
        latest = part.sort_values("observed").groupby("project").tail(1)
        latest = latest[latest.project.isin(cohort) & latest.value.notna()]
        flagged = latest[latest.value <= f.flag_max]
        others = latest[latest.value > f.flag_max]
        key = macro(f.component)
        m[f"Alike{key}N"] = thousands(len(flagged))
        m[f"Alike{key}Share"] = f"{round(100 * flagged.project.isin(hit).mean()) if len(flagged) else 0}\\%"
        m[f"Alike{key}OthersN"] = thousands(len(others))
        m[f"Alike{key}OthersShare"] = f"{round(100 * others.project.isin(hit).mean()) if len(others) else 0}\\%"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["% Generated by pipeline/paper_numbers.py from web/static/data/. Do not edit."]
    lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(m.items())]
    OUT.write_text("\n".join(lines) + "\n")
    print(f"{OUT.relative_to(ROOT)}: {len(m)} macros")
    return 0


if __name__ == "__main__":
    sys.exit(main())
