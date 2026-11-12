#!/usr/bin/env python3
"""Build the data files of the explorer from the frozen inputs in data/inputs/.

Every value becomes one dated reading: the time it was read from its source (`observed`), never the
snapshot it belongs to. A reading that cannot be dated is dropped. The web app shows a reading at t0
only if `observed <= t0` (web/src/lib/sql/readings_at.sql, tested in pipeline/tests/).

Events are dated facts after the fact (archived, gone, last commit, dormancy, advisories), read up
to the outcome data freeze of 3 Nov 2026. They do not depend on t0.

No person-level field leaves this script: no author, no login, no message.

Output (web/static/data/):
    projects.parquet   one row per project
    readings.parquet   project, instrument, component, value, note, observed, snapshot, evidence, source
    events.parquet     project, kind, date, title, detail, source
    activity.parquet   project, month, commits, tags
    components.parquet catalogue: label, unit, how to read, documented claim, backdating
    validity.parquet   one quoted sentence per tested score
    meta.json          build time, data freeze, input checksums

Usage:
    python pipeline/build.py
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "data" / "inputs"
RAW = ROOT / "data" / "raw"  # collected here (crawl_crossd.py, collect_scorecard_history.py), not copied
CROSSD_MONTHLY = RAW / "crossd_metrics_monthly.jsonl.gz"
CROSSD_REST = RAW / "crossd_metrics_rest.jsonl.gz"
SCORECARD_HISTORY = [RAW / "scorecard_history_early_2026-11-12.parquet", RAW / "scorecard_history_2026-11-12.parquet"]
OUT = ROOT / "web" / "static" / "data"

FREEZE = datetime(2026, 11, 3, 23, 59, 59, tzinfo=UTC).timestamp()
DAY = 86400.0
SCAN_WINDOW = 8 * DAY - 1  # a published Scorecard scan is read within a week after its date
CITATION = "Neumaier and Dam, Would the Score Have Warned Us?, under review; doi:10.5281/zenodo.24113633"

RECORDED, RECONSTRUCTED, NOT_BACKDATABLE = "recorded", "reconstructed", "not_backdatable"

# ---------------------------------------------------------------------------------------------
# Catalogue. Labels and units are ours; the claim column quotes the instrument's documentation
# (claims.csv of the replication package) where one exists.
# ---------------------------------------------------------------------------------------------

CROSSD = {
    # component: (label, unit, how to read)
    "maturity_level": ("Maturity level", "20–100", "higher means more mature"),
    "bus_factor": ("Bus factor", "people", "fewest contributors who made more than half of the contributions"),
    "elephant_factor": ("Elephant factor", "organisations", "fewest companies behind more than half of the contributions"),
    "support_rate": ("Support rate", "0–100", "issues and pull requests of the last 90 days with a response"),
    "criticality_score": ("Criticality score", "0–100", "higher means more critical"),
    "project_velocity_ratio_closed": ("Closed issues and pull requests", "%", "closed over all issues and pull requests"),
    "community_health": ("Community health", "0–100", "custom health percentage"),
    "first_response_days": ("First response", "days", "average days to a first response on issues"),
    "dependents_count": ("Dependents", "count", "dependents reported by GitHub"),
}

SCORECARD_CHECKS = [
    "Maintained", "Code-Review", "Dangerous-Workflow", "Token-Permissions", "Binary-Artifacts",
    "Pinned-Dependencies", "Security-Policy", "Vulnerabilities", "Branch-Protection", "Signed-Releases",
    "Packaging", "Fuzzing", "SAST", "License", "CII-Best-Practices", "CI-Tests", "Dependency-Update-Tool",
    "Contributors", "Webhooks", "SBOM",
]

CRITICALITY = {
    "default_score": ("score", "Criticality score", "0–1", "higher means more critical"),
    "contributor_count": ("contributor_count", "Contributors", "count", "signal of the score"),
    "org_count": ("org_count", "Organisations", "count", "signal of the score"),
    "commit_frequency": ("commit_frequency", "Commit frequency", "per week", "signal of the score"),
    "recent_release_count": ("recent_release_count", "Recent releases", "count", "signal of the score"),
    "updated_issues_count": ("updated_issues_count", "Updated issues", "count", "signal of the score"),
    "closed_issues_count": ("closed_issues_count", "Closed issues", "count", "signal of the score"),
    "issue_comment_frequency": ("issue_comment_frequency", "Comment frequency", "per issue", "signal of the score"),
    "dependent_count": ("dependent_count", "Mentions as dependency", "count", "signal of the score"),
    "updated_since": ("updated_since", "Months since update", "months", "signal of the score"),
    "created_since": ("created_since", "Age", "months", "signal of the score"),
}

OPENCODE = {
    "opencode_maintenance": ("maintenance", "Active maintenance badge", "level 0–3", "0 means no badge"),
    "opencode_security": ("security", "Security badge", "level 0–3", "0 means no badge"),
    "opencode_response_ok": ("response_ok", "Issue response criterion", "met or not", "1 means met"),
    "opencode_response_days": ("response_days", "Issue response", "days", "median days to a response"),
    "opencode_security_policy": ("security_policy", "Security policy", "present or not", "1 means present"),
    "opencode_reviewed_share": ("reviewed_share", "Reviewed changes", "share", "share of reviewed pull requests"),
    "opencode_branch_protection": ("branch_protection", "Branch protection", "present or not", "1 means present"),
}

INSTRUMENT_NAMES = {
    "crossd": "CrOSSD",
    "scorecard": "OpenSSF Scorecard",
    "criticality": "OpenSSF Criticality Score",
    "opencode": "openCode badges",
}


def ts(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return pd.Timestamp(value).tz_convert("UTC").timestamp() if pd.Timestamp(value).tzinfo else pd.Timestamp(value, tz="UTC").timestamp()


def number(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value)
    return None


def unwrap(value):
    """`bak` values are wrapped as {repo_id: value}."""
    if isinstance(value, dict) and len(value) == 1 and next(iter(value)).isdigit():
        return next(iter(value.values()))
    return value


def present(value) -> bool:
    return value is not None and value != {} and value != []


def reading(project, instrument, component, value, observed, evidence, source, snapshot=None, note=None) -> dict:
    return {
        "project": project, "instrument": instrument, "component": component,
        "value": value, "note": note, "observed": observed, "snapshot": snapshot,
        "evidence": evidence, "source": source,
    }


# ---------------------------------------------------------------------------------------------
# Readings
# ---------------------------------------------------------------------------------------------

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metric_lines():
    """The replication package's cache, then the monthly crawl (which skips keys of the cache)."""
    for path in (INPUTS / "metrics.jsonl.gz", CROSSD_MONTHLY, CROSSD_REST):
        if path.exists():
            with gzip.open(path, "rt") as fh:
                yield from fh


def crossd_readings() -> list[dict]:
    """Each component dated by the block it was read from: `bak.timestamp` or `metrics.timestamp`."""
    rows = []
    seen = set()
    for line in metric_lines():
        rec = json.loads(line)
        key = (rec["project"], rec["snapshot_ts"])
        if key in seen:
            continue
        seen.add(key)
        response = rec.get("response") or {}
        bak = response.get("bak") or {}
        top = response.get("metrics") or {}
        blocks = [("bak", bak, number(bak.get("timestamp"))), ("metrics", top, number(top.get("timestamp")))]

        def pick(name):
            for block_name, block, stamp in blocks:
                value = unwrap(block.get(name))
                if present(value):
                    return value, stamp, block_name
            return None, None, None

        fields = {
            "maturity_level": (pick("maturity_level"), None),
            "elephant_factor": (pick("elephant_factor"), None),
            "support_rate": (pick("support_rate"), None),
            "criticality_score": (pick("criticality_score"), None),
            "bus_factor": (pick("contributions_distributions"), "bus_factor_score"),
            "project_velocity_ratio_closed": (pick("project_velocity"), "ratio_closed_total"),
            "community_health": (pick("github_community_health_percentage"), "custom_health_score"),
            "first_response_days": (pick("issues"), "average_first_response_time_days"),
        }
        for component, ((raw, stamp, block_name), key) in fields.items():
            value = raw.get(key) if key and isinstance(raw, dict) else (None if key else raw)
            value = number(value)
            if value is None or stamp is None:
                continue
            rows.append(reading(rec["project"], "crossd", component, value, stamp, RECORDED,
                                f"CrOSSD /api/metrics, {block_name} block", snapshot=float(rec["snapshot_ts"])))
        dependents = number(top.get("dependents_count"))
        stamp = number(top.get("timestamp"))
        if dependents is not None and stamp is not None:
            rows.append(reading(rec["project"], "crossd", "dependents_count", dependents, stamp, RECORDED,
                                "CrOSSD /api/metrics, metrics block", snapshot=float(rec["snapshot_ts"])))
    return rows


def scorecard_readings() -> list[dict]:
    rows = []
    # Published weekly scans. A scan runs for about a week after its date: in the scan of 2024-07-29,
    # 405 of 856 scanned commits are younger than the scan day, by up to 5.8 days. So a scan is dated
    # at the end of the seventh day after its date, never at the scan date.
    for scan in ("2024-07-29", "2024-12-30"):
        table = pd.read_parquet(INPUTS / f"scorecard_published_{scan}.parquet")
        observed = pd.Timestamp(scan, tz="UTC").timestamp() + SCAN_WINDOW
        source = f"OpenSSF Scorecard, published scan of {scan}"
        for rec in table.to_dict("records"):
            rows.append(reading(rec["project"], "scorecard", "aggregate", number(rec["aggregate"]), observed, RECORDED, source))
            for check in SCORECARD_CHECKS:
                if check in rec and rec[check] is not None and not pd.isna(rec[check]):
                    value = float(rec[check])
                    rows.append(reading(rec["project"], "scorecard", check, None if value < 0 else value, observed,
                                        RECORDED, source, note="inconclusive" if value < 0 else None))
    # The other weekly scans, secured from BigQuery; the two frozen scans above take precedence on their dates.
    parts = [pd.read_parquet(path) for path in SCORECARD_HISTORY if path.exists()]
    if parts:
        history = pd.concat(parts).drop_duplicates(["project", "scan"])
        history = history[~history.scan.isin(["2024-07-29", "2024-12-30"])]
        for scan, table in history.groupby("scan"):
            observed = pd.Timestamp(scan, tz="UTC").timestamp() + SCAN_WINDOW
            source = f"OpenSSF Scorecard, published scan of {scan}"
            for rec in table.to_dict("records"):
                rows.append(reading(rec["project"], "scorecard", "aggregate", number(rec["aggregate"]), observed, RECORDED, source))
                for check in SCORECARD_CHECKS:
                    if check in rec and rec[check] is not None and not pd.isna(rec[check]):
                        value = float(rec[check])
                        rows.append(reading(rec["project"], "scorecard", check, None if value < 0 else value, observed,
                                            RECORDED, source, note="inconclusive" if value < 0 else None))
    with open(INPUTS / "published_2026-11-04.jsonl") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("status") != 200 or not rec.get("date"):
                continue
            # a full timestamp is the reading time; a bare date is a weekly scan, dated as above
            stamp = pd.Timestamp(rec["date"])
            observed = (stamp.tz_convert("UTC").timestamp() if stamp.tzinfo else
                        pd.Timestamp(rec["date"], tz="UTC").timestamp() + SCAN_WINDOW)
            source = f"api.scorecard.dev, result of {rec['date']}"
            rows.append(reading(rec["project"], "scorecard", "aggregate", number(rec.get("score")), observed, RECORDED, source))
            for check, value in (rec.get("checks") or {}).items():
                value = number(value)
                if value is None:
                    continue
                rows.append(reading(rec["project"], "scorecard", check, None if value < 0 else value, observed,
                                    RECORDED, source, note="inconclusive" if value < 0 else None))
    # Rebuilt at the last commit before a freeze date: dated by the freeze date, the end of the data used.
    for name, t0 in (("scorecard_2024-08-01", "2024-08-01"), ("scorecard_maintained_2025-01-01", "2025-01-01")):
        table = pd.read_parquet(INPUTS / f"{name}.parquet")
        cutoff = pd.Timestamp(t0, tz="UTC").timestamp()
        source = f"Scorecard v5.6.0 rebuilt at the last commit before {t0}"
        for rec in table.to_dict("records"):
            component = rec["component"].removeprefix("scorecard_")
            # the rebuilt aggregate covers only the backdatable checks: a different quantity, its own row
            component = {"maintained": "Maintained"}.get(component, component)
            if rec["evidence"] == NOT_BACKDATABLE:
                continue  # listed once per component in the catalogue, not as a reading
            rows.append(reading(rec["project"], "scorecard", component, number(rec["value"]), cutoff, RECONSTRUCTED, source))
    return rows


def criticality_readings() -> list[dict]:
    table = pd.read_parquet(INPUTS / "history_cohort_2024-08-01.parquet")
    rows = []
    for rec in table.to_dict("records"):
        observed = ts(rec["collection_date"])
        source = f"OpenSSF Criticality list, collected {pd.Timestamp(rec['collection_date']).date()}"
        for column, (component, *_rest) in CRITICALITY.items():
            value = number(rec.get(column)) if rec.get(column) is not pd.NA else None
            if value is None:
                continue
            rows.append(reading(rec["project"], "criticality", component, value, observed, RECORDED, source))
    return rows


def opencode_readings() -> list[dict]:
    rows = []
    for t0 in ("2024-08-01", "2025-01-01"):
        table = pd.read_parquet(INPUTS / f"opencode_{t0}.parquet")
        cutoff = pd.Timestamp(t0, tz="UTC").timestamp()
        source = f"openCode rules rebuilt from dated issues, pull requests and releases before {t0}"
        for rec in table.to_dict("records"):
            if rec["component"] not in OPENCODE or rec["evidence"] == NOT_BACKDATABLE:
                continue
            component = OPENCODE[rec["component"]][0]
            value = number(rec["value"])
            if value is None:
                continue
            rows.append(reading(rec["project"], "opencode", component, value, cutoff, RECONSTRUCTED, source))
    return rows


# ---------------------------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------------------------

def events(projects: set[str]) -> pd.DataFrame:
    rows = []
    meta = pd.read_parquet(INPUTS / "github_meta_2025-01-01.parquet")
    for rec in meta.to_dict("records"):
        if rec["project"] not in projects:
            continue
        if isinstance(rec.get("archivedAt"), str) and rec["archivedAt"]:
            rows.append({"project": rec["project"], "kind": "archived", "date": ts(rec["archivedAt"]),
                         "title": "Archived on GitHub", "detail": "read-only from this date",
                         "source": "GitHub archivedAt, read 4 Nov 2026"})

    with open(INPUTS / "gone_2024-08-01.jsonl") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec["project"] not in projects:
                continue
            last = rec.get("last_full_visit")
            gone_seen = rec.get("first_not_found_after_last_full")
            if gone_seen:
                rows.append({"project": rec["project"], "kind": "gone", "date": ts(gone_seen),
                             "title": "Repository gone",
                             "detail": f"Software Heritage last found it on {pd.Timestamp(last).strftime('%-d %b %Y')}" if last else "",
                             "source": "Software Heritage visits"})
            else:
                rows.append({"project": rec["project"], "kind": "gone", "date": None,
                             "title": "Repository gone, date unknown",
                             "detail": "no longer on GitHub at the data freeze; no dated visit records its removal",
                             "source": "GitHub, Software Heritage"})

    last = pd.read_parquet(INPUTS / "git_last.parquet")
    for rec in last.to_dict("records"):
        if rec["project"] not in projects or pd.isna(rec["last_commit"]):
            continue
        commit = float(rec["last_commit"])
        tag = float(rec["last_tag"]) if not pd.isna(rec["last_tag"]) else None
        activity = max(commit, tag or 0)
        rows.append({"project": rec["project"], "kind": "last_commit", "date": commit,
                     "title": "Last commit before the data freeze", "detail": "default branch",
                     "source": "git history"})
        if activity + 365 * DAY <= FREEZE:
            rows.append({"project": rec["project"], "kind": "dormant", "date": activity + 365 * DAY,
                         "title": "Twelve months without a commit or tag",
                         "detail": "on the default branch; releases are not checked, so this is not the outcome definition of the paper",
                         "source": "git history"})

    advisories = pd.concat([
        pd.read_parquet(INPUTS / "attached_advisories_2024-08-01.parquet"),
        pd.read_parquet(INPUTS / "attached_advisories_2025-01-01.parquet"),
    ])
    advisories = advisories[advisories.project.isin(projects)]
    for (project, adv_id), group in advisories.groupby(["project", "id"]):
        first = group.iloc[0]
        packages = ", ".join(sorted(p for p in set(group.package.dropna()) if p))
        if group.in_kev.any():
            status = "listed in CISA KEV"
        elif group.no_fix_listed.any() and not group.fixed_versions.fillna("").str.len().gt(0).any():
            status = "no fixed version listed at the data freeze"
        elif group.fixed_versions.fillna("").str.len().gt(0).any():
            status = "fixed version listed"
        else:
            status = "fix status not known"
        rows.append({"project": project, "kind": "advisory", "date": ts(first.published_at),
                     "title": f"Severe advisory {adv_id}",
                     "detail": f"{packages}; {status}" if packages else status.capitalize(),
                     "source": "OSV, frozen 3 Nov 2026"})
    table = pd.DataFrame(rows)
    # GitHub metadata was read a day after the freeze; anything dated later is outside the record.
    late = table.date.notna() & (table.date > FREEZE)
    for rec in table[late].itertuples():
        print(f"  dropped, after the data freeze: {rec.project} {rec.kind}")
    return table[~late].reset_index(drop=True)


# ---------------------------------------------------------------------------------------------
# Catalogue and validity
# ---------------------------------------------------------------------------------------------

def catalogue() -> pd.DataFrame:
    claims = pd.read_csv(INPUTS / "claims.csv")
    backdating = pd.read_csv(INPUTS / "backdating.csv")
    claim_by = {(r.instrument, r.component): r.quote for r in claims.itertuples()}
    source_by = {r.quote: r.source_url for r in claims.itertuples()}
    rows = []
    for component, (label, unit, how) in CROSSD.items():
        key = {"bus_factor": "bus_factor_score", "project_velocity_ratio_closed": "project_velocity",
               "community_health": "github_community_health_percentage"}.get(component, component)
        rows.append({"instrument": "crossd", "component": component, "label": label, "unit": unit, "how": how,
                     "claim": claim_by.get(("CrOSSD", key)), "backdating": "recorded", "why": "stored at the time by CrOSSD"})
    sc_back = backdating[backdating.instrument == "Scorecard"].set_index("component")
    for check in ["aggregate", "aggregate_t0", *SCORECARD_CHECKS]:
        label = {"aggregate": "Aggregate, as published", "aggregate_t0": "Aggregate of the backdatable checks"}.get(
            check, check.replace("-", " ").capitalize())
        cls = sc_back["class"].get(check) if check in sc_back.index else None
        why = sc_back["why"].get(check) if check in sc_back.index else None
        if check == "aggregate":
            cls, why = None, "published scans only"
        if check == "aggregate_t0":
            cls, why = "rebuilt", "Scorecard weights over the seven checks that can be backdated, 50 of 120 weight points"
        rows.append({"instrument": "scorecard", "component": check, "label": label, "unit": "0–10",
                     "how": "higher is better", "claim": claim_by.get(("OpenSSF Scorecard", check)),
                     "backdating": {"rebuilt": "rebuilt", "partial": "partial", "none": "not_backdatable"}.get(cls, "published only"),
                     "why": why or "published scans only"})
    for _col, (component, label, unit, how) in CRITICALITY.items():
        rows.append({"instrument": "criticality", "component": component, "label": label, "unit": unit, "how": how,
                     "claim": claim_by.get(("OpenSSF Criticality Score", "score")) if component == "score" else None,
                     "backdating": "recorded", "why": "published lists, stored at the time"})
    oc_claims = {"maintenance": "Aktive Wartung L1", "security": "Sicherheit L1-L3"}
    for _full, (component, label, unit, how) in OPENCODE.items():
        rows.append({"instrument": "opencode", "component": component, "label": label, "unit": unit, "how": how,
                     "claim": claim_by.get(("openCode badges", oc_claims.get(component, ""))),
                     "backdating": "rebuilt", "why": "rules applied to dated issues, pull requests and releases"})
    table = pd.DataFrame(rows)
    table["instrument_name"] = table.instrument.map(INSTRUMENT_NAMES)
    table["claim_source"] = table.claim.map(source_by)
    return table


OUTCOME_TEXT = {
    "O1": "archival or twelve months of dormancy within 24 months",
    "O1c_share": "half or more of external issues left unanswered for 90 days",
    "O2b": "a severe advisory left without a fixed version",
    "I1b": "dependents two years later",
}

VALIDITY_KEYS = {
    "scorecard_Maintained": ("scorecard", "Maintained"),
    "scorecard_aggregate_t0": ("scorecard", "aggregate_t0"),
    "opencode_maintenance": ("opencode", "maintenance"),
    "opencode_security": ("opencode", "security"),
    "opencode_response_ok": ("opencode", "response_ok"),
    "maturity_level": ("crossd", "maturity_level"),
    "bus_factor": ("crossd", "bus_factor"),
    "elephant_factor": ("crossd", "elephant_factor"),
    "support_rate": ("crossd", "support_rate"),
    "criticality_score": ("crossd", "criticality_score"),
    "openssf_criticality_published": ("criticality", "score"),
}


# Documented operating points as the paper reads them (measured_validity.csv, column operating_point): a value at or
# below `flag_max` is a warning. `against` names the events that count as the outcome in the explorer: failure
# (archived, gone with a date, dormant) or an advisory left without a fix; the issue outcome is not an event here.
FLAGS = {
    "Scorecard Maintained = 0": (0.0, "Maintained = 0", "failure"),
    "openCode maintenance, no badge": (0.0, "no maintenance badge", "failure"),
    "CrOSSD bus factor at most 1": (1.0, "bus factor at most 1", "failure"),
    "CrOSSD elephant factor at most 1": (1.0, "elephant factor at most 1", "failure"),
    "openCode response criterion failed": (0.0, "response criterion failed", None),
    "openCode security, no badge": (0.0, "no security badge", "advisory"),
}


def validity() -> pd.DataFrame:
    """One sentence per tested score, numbers quoted from measured_validity.csv, never recomputed."""
    table = pd.read_csv(INPUTS / "measured_validity.csv")
    rows = []
    for r in table.itertuples():
        instrument, component = VALIDITY_KEYS[r.component]
        outcome = OUTCOME_TEXT.get(r.outcome, r.outcome)
        if not pd.isna(r.auroc):
            measure = f"AUROC {r.auroc:.2f} (95% interval {r.auroc_lo:.2f} to {r.auroc_hi:.2f})"
        else:
            measure = f"rank correlation {r.rank_correlation:.2f}"
        verdict = "warned" if r.warns else "did not warn"
        sentence = (f"Measured at 1 Aug 2024 on {r.n:,} projects against {outcome}, this score {verdict}: "
                    f"{measure}.")
        flag_max, flag_label, against = FLAGS[r.operating_point] if isinstance(r.operating_point, str) else (None, None, None)
        rows.append({"instrument": instrument, "component": component, "outcome": r.outcome,
                     "sentence": sentence, "citation": CITATION, "warns": bool(r.warns),
                     "flag_max": flag_max, "flag_label": flag_label, "against": against,
                     "sensitivity": None if pd.isna(r.sensitivity) else float(r.sensitivity),
                     "specificity": None if pd.isna(r.specificity) else float(r.specificity)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    readings = pd.DataFrame(crossd_readings() + scorecard_readings() + criticality_readings() + opencode_readings())
    readings = readings[readings.observed.notna()]
    readings = readings.drop_duplicates(["project", "instrument", "component", "observed", "value"])
    # t0 never passes the data freeze, so a reading dated after it could never be shown: drop it, say so
    late = readings.observed > FREEZE
    if late.any():
        print(f"  dropped {late.sum():,} readings dated after the data freeze:")
        print(readings[late].groupby(["instrument", "source"]).size().to_string())
    readings = readings[~late]

    cohorts = {d: pd.read_csv(INPUTS / f"cohort_{d}.csv") for d in ("2024-08-01", "2025-01-01")}
    index = json.loads((INPUTS / "index_20261103.json").read_text())["snapshots"]
    projects = pd.DataFrame({"project": sorted(set(readings.project))})
    c1 = cohorts["2024-08-01"].set_index("project")
    projects["stratum"] = projects.project.map(c1.stratum).fillna(
        projects.project.map(cohorts["2025-01-01"].set_index("project").stratum))
    projects["in_cohort"] = projects.project.isin(c1.index)
    projects["gone_now"] = projects.project.map(c1.gone_now).fillna(False).astype(bool)
    projects["snapshots"] = projects.project.map(lambda p: len(index.get(p, [])))
    span = readings[readings.instrument == "crossd"].groupby("project")["observed"].agg(["min", "max", "count"])
    # which event sources were collected for the project: commit history and GitHub metadata exist
    # only for the two cohorts of the replication package
    projects["has_git"] = projects.project.isin(set(pd.read_parquet(INPUTS / "git_last.parquet").project))
    projects["has_meta"] = projects.project.isin(set(pd.read_parquet(INPUTS / "github_meta_2025-01-01.parquet").project))
    projects["first_reading"] = projects.project.map(span["min"])
    projects["last_reading"] = projects.project.map(span["max"])
    projects["crossd_readings"] = projects.project.map(span["count"]).fillna(0).astype(int)

    names = set(projects.project)
    readings = readings[readings.project.isin(names)]
    event_table = events(names)
    activity = pd.read_parquet(INPUTS / "git_activity.parquet")
    activity = activity[activity.project.isin(names) & (activity.month >= pd.Timestamp("2022-01-01", tz="UTC"))].copy()
    activity["month"] = activity.month.map(lambda m: m.timestamp())

    readings.to_parquet(OUT / "readings.parquet", index=False, compression="zstd")
    projects.to_parquet(OUT / "projects.parquet", index=False, compression="zstd")
    event_table.to_parquet(OUT / "events.parquet", index=False, compression="zstd")
    activity.to_parquet(OUT / "activity.parquet", index=False, compression="zstd")
    catalogue().to_parquet(OUT / "components.parquet", index=False)
    validity().to_parquet(OUT / "validity.parquet", index=False)
    manifest = json.loads((INPUTS / "MANIFEST.json").read_text())
    (OUT / "meta.json").write_text(json.dumps({
        "built": datetime.now(UTC).isoformat(timespec="seconds"),
        "data_freeze": "2026-11-03",
        "t0_min": "2024-04-01",
        "t0_max": "2026-11-03",
        "citation": CITATION,
        "inputs": {k: v["sha256"] for k, v in manifest.items()}
        | {p.name: sha256(p) for p in (CROSSD_MONTHLY, CROSSD_REST, *SCORECARD_HISTORY) if p.exists()},
    }, indent=2) + "\n")

    print(f"projects  {len(projects):>8,}  ({projects.in_cohort.sum():,} in the cohort of 1 Aug 2024)")
    print(f"readings  {len(readings):>8,}")
    print(readings.groupby(["instrument", "evidence"]).size().to_string())
    print(f"events    {len(event_table):>8,}")
    print(event_table.kind.value_counts().to_string())
    for path in sorted(OUT.glob("*")):
        print(f"  {path.name:20s} {path.stat().st_size / 1e6:6.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
