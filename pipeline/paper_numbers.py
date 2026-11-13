#!/usr/bin/env python3
"""Every number of the demo paper, as LaTeX macros, from the built data in web/static/data/.

Lead time and look-alikes follow the rules of web/src/lib/hindsight.ts: the unbroken run at or below the operating
point that still stands at the event, read before it; the cohort split at the operating point by each project's latest
reading at t0, events counted from t0 to the data freeze.

Output: paper/generated/numbers.tex

Usage:
    python pipeline/paper_numbers.py [--project minio/minio] [--second atlassian/react-beautiful-dnd] [--event archived] [--t0 2024-08-01]
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
    ap.add_argument("--second", default="atlassian/react-beautiful-dnd", help="second case of the walkthrough")
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

    # The walkthrough: lead times before one event of a project, and the scores at their operating point at t0
    words = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
    t0_case = pd.Timestamp(args.t0, tz="UTC").timestamp()

    def case(prefix: str, project: str, event: str) -> float | None:
        ev = events[(events.project == project) & (events.kind == event)].dropna(subset=["date"]).sort_values("date")
        when = float(ev.date.iloc[0]) if not ev.empty else None
        if when is not None:
            m[f"{prefix}EventDate"] = day(when)
            mine = readings[(readings.project == project) & (readings.observed < when)]
            leads = []
            for f in validity[validity.flag_max.notna() & (validity.against == "failure")].itertuples():
                run = lead(mine[(mine.instrument == f.instrument) & (mine.component == f.component)], f.flag_max)
                if run:
                    leads.append((f.component, run))
            for component, (since, last) in leads:
                key = macro(component)
                m[f"{prefix}Lead{key}Since"] = day(since)
                m[f"{prefix}Lead{key}Months"] = months(when - since)
            m[f"{prefix}Leads"] = thousands(len(leads))
        at = readings[(readings.project == project) & (readings.observed <= t0_case)].sort_values("observed")
        flagged_at = []
        for f in validity[validity.flag_max.notna()].itertuples():
            last = at[(at.instrument == f.instrument) & (at.component == f.component)].dropna(subset=["value"]).tail(1)
            if len(last) == 1 and last.value.iloc[0] <= f.flag_max:
                flagged_at.append(f)
        m[f"{prefix}FlagsAtTzero"] = thousands(len(flagged_at))
        m[f"{prefix}FlagsAtTzeroWord"] = words.get(len(flagged_at), thousands(len(flagged_at)))
        failure_at = [f for f in flagged_at if f.against == "failure"]
        m[f"{prefix}FailureFlagsAtTzeroWord"] = words.get(len(failure_at), thousands(len(failure_at)))
        m[f"{prefix}Unfixed"] = thousands(((events.project == project) & (events.kind == "advisory")
                                           & events.detail.str.contains("no fixed version", case=False)).sum())
        return when

    when = case("Case", args.project, args.event)
    shot = pd.Timestamp(args.shot, tz="UTC").timestamp()
    m["CaseShot"] = day(shot)
    if when is not None:
        m["CaseShotDaysBefore"] = thousands((when - shot) / DAY)
    m["FlagsWord"] = words.get(int(validity.flag_max.notna().sum()), m["Flags"])
    failure_flags = int((validity.flag_max.notna() & (validity.against == "failure")).sum())
    m["FailureFlagsWord"] = words.get(failure_flags, thousands(failure_flags))
    m["CaseTzero"] = day(t0_case)

    # The second case: flagged at t0, and Scorecard Maintained left its operating point between t0 and the event
    when = case("Second", args.second, args.event)
    if when is not None and "SecondLeadMaintainedSince" in m:
        maintained = readings[(readings.project == args.second) & (readings.instrument == "scorecard")
                              & (readings.component == "Maintained") & (readings.observed > t0_case)
                              & (readings.observed < when)].dropna(subset=["value"])
        m["SecondMaintainedBetween"] = f"{maintained.value.max():g}"

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

    # The CrOSSD record over time: projects read per week, by crawl list (figure in the platform section)
    lists = projects.set_index("project").stratum.fillna("later")
    for key, name in (("most_starred", "MostStarred"), ("random_sample", "RandomSample"), ("netidee", "Netidee"), ("later", "Later")):
        m[f"List{name}"] = thousands((lists == key).sum())
    monthly = crossd.assign(month=pd.to_datetime(crossd.observed, unit="s").dt.to_period("M").dt.start_time,
                            list=crossd.project.map(lists))
    table = monthly.groupby(["month", "list"]).project.nunique().unstack(fill_value=0)
    table = table.reindex(columns=["most_starred", "random_sample", "netidee", "later"], fill_value=0)
    freeze = pd.Timestamp(meta["data_freeze"])
    table = table[table.index + pd.offsets.MonthEnd(0) <= freeze]  # whole months only
    table.index = (table.index - pd.Timestamp("2024-01-01")).days  # days since 1 Jan 2024, for pgfplots
    OUT.parent.mkdir(parents=True, exist_ok=True)
    table.rename_axis("day").to_csv(OUT.parent / "crossd_monthly.csv")
    m["MonthlyMax"] = thousands(table.sum(axis=1).max())
    lines = ["% Generated by pipeline/paper_numbers.py from web/static/data/. Do not edit."]
    lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(m.items())]
    OUT.write_text("\n".join(lines) + "\n")
    print(f"{OUT.relative_to(ROOT)}: {len(m)} macros")
    return 0


if __name__ == "__main__":
    sys.exit(main())
