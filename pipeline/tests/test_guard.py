"""The hindsight guard: nothing read after t0 may be returned for t0.

Runs the exact SQL files the web app runs (web/src/lib/sql/), with DuckDB, against planted rows and
against the built data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "web" / "src" / "lib" / "sql"
DATA = ROOT / "web" / "static" / "data"


def epoch(day: str) -> float:
    return datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp()


def connect(rows: list[dict]) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    frame = pd.DataFrame(rows)
    con.register("readings_frame", frame)
    con.execute("CREATE TABLE readings AS SELECT * FROM readings_frame")
    return con


def row(component, value, observed, snapshot=None, instrument="crossd", project="acme/widget"):
    return {"project": project, "instrument": instrument, "component": component, "value": value,
            "note": None, "observed": observed, "snapshot": snapshot, "evidence": "recorded", "source": "test"}


T0 = epoch("2024-08-01")

# The leak that hit 1,751 of 1,943 projects in the source study: a snapshot taken before t0
# whose values were read from GitHub after t0.
PLANTED = [
    row("bus_factor", 3.0, observed=epoch("2024-07-20"), snapshot=epoch("2024-07-19")),
    row("bus_factor", 1.0, observed=epoch("2024-08-06"), snapshot=epoch("2024-07-26")),  # leak
    row("maturity_level", 40.0, observed=epoch("2024-08-03"), snapshot=epoch("2024-07-30")),  # leak, only reading
    row("elephant_factor", 2.0, observed=T0, snapshot=epoch("2024-07-31")),  # exactly t0: allowed
    row("bus_factor", 9.0, observed=epoch("2024-07-20"), project="other/project"),
]


def test_latest_reading_is_the_last_one_read_by_t0():
    con = connect(PLANTED)
    out = con.execute((SQL / "readings_at.sql").read_text(), ["acme/widget", T0]).df()
    values = dict(zip(out.component, out.value))
    assert values == {"bus_factor": 3.0, "elephant_factor": 2.0}


def test_snapshot_before_t0_does_not_admit_a_later_reading():
    con = connect(PLANTED)
    out = con.execute((SQL / "readings_at.sql").read_text(), ["acme/widget", T0]).df()
    assert "maturity_level" not in set(out.component)
    assert (out.observed <= T0).all()


def test_series_stops_at_t0():
    con = connect(PLANTED)
    out = con.execute((SQL / "readings_until.sql").read_text(), ["acme/widget", "crossd", "bus_factor", T0]).df()
    assert list(out.value) == [3.0]


def test_other_projects_do_not_leak_in():
    con = connect(PLANTED)
    out = con.execute((SQL / "readings_at.sql").read_text(), ["acme/widget", epoch("2025-01-01")]).df()
    assert 9.0 not in set(out.value)


def test_values_at_takes_each_projects_last_reading_by_t0():
    con = connect(PLANTED)
    out = con.execute((SQL / "values_at.sql").read_text(), ["crossd", "bus_factor", T0]).df()
    assert dict(zip(out.project, out.value)) == {"acme/widget": 3.0, "other/project": 9.0}
    assert (out.observed <= T0).all()
    late_only = con.execute((SQL / "values_at.sql").read_text(), ["crossd", "maturity_level", T0]).df()
    assert late_only.empty


def test_reading_dates_carry_no_values():
    con = connect(PLANTED)
    out = con.execute((SQL / "reading_dates.sql").read_text(), ["acme/widget"]).df()
    assert list(out.columns) == ["instrument", "observed"]


@pytest.mark.skipif(not (DATA / "readings.parquet").exists(), reason="run pipeline/build.py first")
@pytest.mark.parametrize("day", ["2024-05-01", "2024-08-01", "2025-01-01", "2026-01-01"])
def test_built_data_never_returns_a_reading_after_t0(day):
    con = duckdb.connect()
    con.execute(f"CREATE VIEW readings AS SELECT * FROM '{DATA / 'readings.parquet'}'")
    projects = con.execute("SELECT DISTINCT project FROM readings USING SAMPLE 200 ROWS (reservoir, 7)").fetchall()
    sql = (SQL / "readings_at.sql").read_text()
    t0 = epoch(day)
    for (project,) in projects:
        out = con.execute(sql, [project, t0]).df()
        assert (out.observed <= t0).all(), project


@pytest.mark.skipif(not (DATA / "readings.parquet").exists(), reason="run pipeline/build.py first")
def test_every_built_reading_is_dated_and_typed():
    frame = pd.read_parquet(DATA / "readings.parquet")
    assert frame.observed.notna().all()
    assert set(frame.evidence) <= {"recorded", "reconstructed"}
    crossd = frame[frame.instrument == "crossd"]
    # CrOSSD values are dated by their reading, which never precedes the snapshot they belong to
    assert (crossd.observed >= crossd.snapshot - 60).all()


@pytest.mark.skipif(not (DATA / "readings.parquet").exists(), reason="run pipeline/build.py first")
def test_no_person_level_columns_leave_the_pipeline():
    for name in ("readings", "events", "projects", "activity"):
        columns = set(pd.read_parquet(DATA / f"{name}.parquet").columns)
        assert not columns & {"author", "committer", "login", "user", "email", "name"}, name
