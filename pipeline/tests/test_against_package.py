"""The explorer picks the same values as the paper at its two freeze dates.

The guard tests show that nothing late is returned; this shows that the right value is. It runs the web
app's SQL at t0 = 1 Aug 2024 and 1 Jan 2025 for every cohort project and compares with the frozen feature
tables of the replication source (read only). Skipped when the source repository is not present.

Known and accepted difference: CrOSSD `dependents_count` lives in the `metrics` block, which is read
within hours of its snapshot, while the paper takes all CrOSSD values from the one snapshot whose `bak`
block was read by t0. A later snapshot's `metrics` block can be read before t0 too, and the explorer,
dating each block on its own, shows that later reading.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(os.environ.get("OSS_SCORE_VALIDITY", ROOT.parent / "oss-score-validity")) / "data" / "processed" / "features"
DATA = ROOT / "web" / "static" / "data"
SQL = (ROOT / "web" / "src" / "lib" / "sql" / "readings_at.sql").read_text()

CHECKS = {
    "crossd": ("crossd", {c: c for c in [
        "maturity_level", "elephant_factor", "support_rate", "criticality_score", "bus_factor",
        "project_velocity_ratio_closed", "community_health", "first_response_days"]}),
    "criticality_published": ("criticality", {"openssf_criticality_published": "score"}),
    "opencode": ("opencode", {"opencode_maintenance": "maintenance", "opencode_security": "security",
                              "opencode_response_ok": "response_ok"}),
    "scorecard": ("scorecard", {"scorecard_Maintained": "Maintained", "scorecard_aggregate_t0": "aggregate_t0",
                                "scorecard_Code-Review": "Code-Review"}),
}

pytestmark = pytest.mark.skipif(
    not SOURCE.exists() or not (DATA / "readings.parquet").exists(), reason="source or build missing"
)


@pytest.fixture(scope="module")
def shown():
    con = duckdb.connect()
    con.execute(f"CREATE TABLE readings AS SELECT * FROM '{DATA / 'readings.parquet'}'")
    out = {}
    for t0 in ("2024-08-01", "2025-01-01"):
        stamp = pd.Timestamp(t0, tz="UTC").timestamp()
        cohort = pd.read_csv(ROOT / "data" / "inputs" / f"cohort_{t0}.csv").project
        out[t0] = pd.concat([con.execute(SQL, [p, stamp]).df() for p in cohort])
    return out


@pytest.mark.parametrize("t0", ["2024-08-01", "2025-01-01"])
@pytest.mark.parametrize("table", list(CHECKS))
def test_same_values_as_the_paper(shown, t0, table):
    path = SOURCE / f"{table}_{t0}.parquet"
    if not path.exists():
        pytest.skip(f"{path.name} not in the source")
    instrument, mapping = CHECKS[table]
    paper = pd.read_parquet(path)
    paper = paper[paper.component.isin(mapping)].assign(component=lambda f: f.component.map(mapping))
    mine = shown[t0][shown[t0].instrument == instrument][["project", "component", "value"]]
    joined = paper.merge(mine, on=["project", "component"], how="left", suffixes=("_paper", "_shown"))
    has_paper = joined.value_paper.notna()
    assert joined[has_paper].value_shown.notna().all(), "a value of the paper is missing"
    differ = has_paper & ((joined.value_paper - joined.value_shown).abs() > 1e-9)
    assert not differ.any(), joined[differ].head().to_string()
