# CrOSSD Time Machine

What did open-source health and security scores say about a project before things went wrong?
Pick a project and a past date t0. The page shows the CrOSSD metrics, the OpenSSF Scorecard, the OpenSSF
Criticality Score and the openCode badges as they were known at t0, and what happened to the project afterwards.

Nothing read after t0 appears on the left of the t0 line. Every value is dated by when it was read from its source,
not by the snapshot it belongs to, and the queries enforce this (the hindsight guard, tested in
`pipeline/tests/test_guard.py` and `web/src/lib/guard.test.ts`).

The explorer builds on the CrOSSD platform (https://health.crossd.tech, https://github.com/FH-CrOSSD) and on the
replication package of *Would the Score Have Warned Us? A Point-in-Time Validity Audit of Open-Source Health and
Security Scores* (Neumaier and Dam, under review; https://doi.org/10.5281/zenodo.24113633), whose measured validity
it quotes.

## Try it

Live: https://fh-crossd.github.io/crossd-timemachine/ (built from `main` by `.github/workflows/pages.yml`).

Video (3 min): https://youtu.be/SThzrXSXCBE

Archived at Zenodo: https://doi.org/10.5281/zenodo.24195169 (all versions; v1.0.0: https://doi.org/10.5281/zenodo.24195170)

Locally:

The built data is in the repository, so only Node.js (20.19 or newer) is needed:

```
cd web
npm ci
npm run dev
```

Then open http://localhost:5173. The page loads about 12 MB of Parquet into DuckDB in the browser; nothing is sent
anywhere. "How to read this page" at the top explains the terms. For a static copy, run `npm run build` and serve
`web/build/` from any web server; it makes no external request and runs offline.

## What it shows

- **What the scores said by t0.** For each instrument, the latest value read at or before t0, with its reading date
  and evidence type: recorded at the time, reconstructed from dated data, or not backdatable.
- **What happened next.** Archival, disappearance (dated by Software Heritage), twelve months without a commit or
  tag, severe advisories (OSV, CISA KEV) with their fix status, and the last commit, up to the data freeze on
  3 Nov 2026.
- **Lead time.** Under each outcome event, every tested score that stood at its operating point when the event
  happened, and since when, from readings made before the event.
- **Look-alikes.** At t0, the cohort of 1,687 projects split at each operating point, with the share of each group
  that failed or had an unfixed advisory by the data freeze. Descriptive.
- **Measured validity.** One sentence per tested score, quoted from the paper.

## Layout

- `pipeline/` data build (Python): collection, `build.py`, tests
- `web/` the explorer (SvelteKit, DuckDB-WASM); `web/static/data/` holds the built data
- `data/README.md` provenance of every input: source, date, SHA-256, licence

## Rebuild the data

The built data in `web/static/data/` is what the explorer uses. Rebuilding it from scratch needs the raw inputs listed
in `data/README.md`. Part of them can be collected again from public sources; part comes from the working copy of the
replication package, whose raw downloads are not redistributed (set `OSS_SCORE_VALIDITY` to its path).

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python pipeline/import_inputs.py              # frozen inputs, checked against their SHA-256
.venv/bin/python pipeline/git_activity.py               # commit and tag dates from the commit-only clones
.venv/bin/python pipeline/crawl_crossd.py               # CrOSSD /api/metrics, first snapshot per month (resumable)
.venv/bin/python pipeline/collect_scorecard_history.py  # published Scorecard scans from BigQuery (GOOGLE_CLOUD_PROJECT)
.venv/bin/python pipeline/build.py                      # web/static/data/
.venv/bin/python -m pytest pipeline/tests               # hindsight guard and agreement with the paper
```

## Licence

Code: MIT. Built data and documentation: CC BY 4.0, except the published OpenSSF Scorecard results
(CDLA-Permissive-2.0) and the OpenSSF Criticality Score values (Apache-2.0). Details in `LICENSE` and
`data/README.md`.

## Citation

See `CITATION.cff`. Please also cite the paper whose measured validity the explorer quotes.

## Acknowledgements

Funded by the Austrian Research Promotion Agency (FFG), project DigiSov-CrOSSD, no. 68758333, and the Internet
Stiftung (netidee), project CrOSSD2.
