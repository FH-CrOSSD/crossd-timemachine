# Data

Raw inputs are not tracked; the built data in `web/static/data/` is. One row per downloaded file: what it is, source, download date, SHA-256, licence.

| File | What it is | Source | Download date | SHA-256 | Licence |
|---|---|---|---|---|---|
| `inputs/cohort_2024-08-01.csv` | frozen cohort at 1 Aug 2024 | `oss-score-validity/analysis/01_cohort/cohort_2024-08-01.csv` | 2026-11-12 | `39df43f1c24ab76de6563f1f8555347e21b0ddde8282cc222910b6b55727612b` | replication package |
| `inputs/cohort_2025-01-01.csv` | robustness cohort at 1 Jan 2025 | `oss-score-validity/analysis/01_cohort/cohort_2025-01-01.csv` | 2026-11-12 | `7f4b4d9e2d740c85cfe19e9178334134b861d70acc63df56707e8f9c779387ec` | replication package |
| `inputs/measured_validity.csv` | measured validity per score (quoted, never recomputed) | `oss-score-validity/analysis/04_validity/measured_validity.csv` | 2026-11-12 | `85f483f40131b77cd72f8c493e58cfb6a1467bb8655d736dd0bf80ec1b291d69` | replication package |
| `inputs/claims.csv` | documented claims per component, quoted with source | `oss-score-validity/data/claims/claims.csv` | 2026-11-12 | `81f45f27d2bd708a76fd133b9e94bdb61e1d0d0728d2bbc3ee5120f4560d74d6` | per source |
| `inputs/backdating.csv` | which components can be backdated, and why | `oss-score-validity/data/probes/backdating.csv` | 2026-11-12 | `59b0777b29d54ae9d0bc1c5c0444c0c2a0e5c9889cae5c9f97dc2a207a6e9b79` | replication package |
| `inputs/attached_advisories_2024-08-01.parquet` | severe advisories attached to cohort projects, published 1 Aug 2024 to 31 Jul 2026 | `oss-score-validity/data/processed/attached_advisories_2024-08-01.parquet` | 2026-11-12 | `a7294df4929f91d06b82b614c12840f1a44db6ea0c0e3635d30337c99d080189` | OSV, per source database |
| `inputs/attached_advisories_2025-01-01.parquet` | the same for the robustness cohort, published in 2025 | `oss-score-validity/data/processed/attached_advisories_2025-01-01.parquet` | 2026-11-12 | `dc5596feb35b793a8028ff5d23e1e4802d1daa4e4ad3192ace29e787650e3252` | OSV, per source database |
| `inputs/opencode_2024-08-01.parquet` | openCode rules rebuilt at 1 Aug 2024 | `oss-score-validity/data/processed/features/opencode_2024-08-01.parquet` | 2026-11-12 | `38b8f9becac13f5b977ab44e518efc45d89e0bf5909501aa6982bd9d6988ab30` | replication package |
| `inputs/opencode_2025-01-01.parquet` | openCode rules rebuilt at 1 Jan 2025 | `oss-score-validity/data/processed/features/opencode_2025-01-01.parquet` | 2026-11-12 | `ee3979207e7e498aad47b13a10e3d7c7a1876e08ad98a864a4a5ab44e6a4ba96` | replication package |
| `inputs/scorecard_2024-08-01.parquet` | Scorecard checks rebuilt at the last commit before 1 Aug 2024 | `oss-score-validity/data/processed/features/scorecard_2024-08-01.parquet` | 2026-11-12 | `92346992bb72d3e991cef05cd9b186e408818a08158b5541b4183a9d73a3b1cc` | replication package |
| `inputs/scorecard_maintained_2025-01-01.parquet` | Scorecard Maintained rebuilt at 1 Jan 2025 | `oss-score-validity/data/processed/features/scorecard_maintained_2025-01-01.parquet` | 2026-11-12 | `a339739f05bc251f30b0309a6c9c607eb3b162fd744f4dc4c1c2e8b49655c04c` | replication package |
| `inputs/github_meta_2025-01-01.parquet` | GitHub metadata incl. archivedAt, read 2026-11-04 | `oss-score-validity/data/processed/github_meta_2025-01-01.parquet` | 2026-11-12 | `37eb452476c936c79bdf50c2920f6a40180672dcac16772e0810e22c7cfa8a2c` | GitHub terms |
| `inputs/scorecard_published_2024-07-29.parquet` | published Scorecard results, scan of 29 Jul 2024 | `oss-score-validity/data/processed/scorecard_published_2024-07-29.parquet` | 2026-11-12 | `196c9917b08c1dba2cdb3887f6fcb327318fba688571a6769ce17f03ed594352` | CDLA-Permissive-2.0 |
| `inputs/scorecard_published_2024-12-30.parquet` | published Scorecard results, scan of 30 Dec 2024 | `oss-score-validity/data/processed/scorecard_published_2024-12-30.parquet` | 2026-11-12 | `c9d61f3fc0d0ef1a2ef6b5b7cf0157016c3eb798458e1e554e1681c438397c4a` | CDLA-Permissive-2.0 |
| `inputs/history_cohort_2024-08-01.parquet` | published OpenSSF Criticality lists 2022-11 to 2025-07, cohort rows | `oss-score-validity/data/raw/criticality/history_cohort_2024-08-01.parquet` | 2026-11-12 | `164c6da77cb6e281412b21b8b9549384781f44c0cc4095c16924f371f36d8f1a` | Apache-2.0 (ossf/criticality_score) |
| `inputs/index_20261103.json` | CrOSSD project list and snapshot timestamps | `oss-score-validity/data/raw/crossd/index_20261103.json` | 2026-11-12 | `7b1005ae2b0ba89a8fbc77dbc17ba6e95c04dc034313e16974040af64f54f99e` | CrOSSD, free use (T. Dam, 2026-11-12) |
| `inputs/metrics.jsonl.gz` | raw /api/metrics responses, cache of 2026-11-03/04 | `oss-score-validity/data/raw/crossd/metrics.jsonl.gz` | 2026-11-12 | `4c140eb78860280840055da627d2cd05089f5c8c9f042a82d99ddd2d79007510` | CrOSSD, free use (T. Dam, 2026-11-12) |
| `inputs/gone_2024-08-01.jsonl` | Software Heritage visits of repositories gone from GitHub | `oss-score-validity/data/raw/github/gone_2024-08-01.jsonl` | 2026-11-12 | `dd13852b631e84b768b19704693d494c9d44007eb10a776978624075ca0aa86e` | CC-BY 4.0 |
| `inputs/published_2026-11-04.jsonl` | api.scorecard.dev, one request per cohort repository | `oss-score-validity/data/raw/scorecard/published_2026-11-04.jsonl` | 2026-11-12 | `cb86954b747c1f2f42fba53125afffad7cfe1e1d295535d5f49403cf4683a029` | CDLA-Permissive-2.0 |

Collected here (`data/raw/`):

| File | What it is | Source | Download date | SHA-256 | Licence |
|---|---|---|---|---|---|
| `raw/crossd_metrics_monthly.jsonl.gz` | raw /api/metrics responses, first snapshot per project and month up to 2026-11-03, 36,997 responses, keys of the cache above skipped (`pipeline/crawl_crossd.py`) | CrOSSD API `health.crossd.tech/api` | 2026-11-12 | `f077bd058c7ec9b3bd326b8b4417fa251687386ef416ffdc64f35ae005848e6c` | CrOSSD, free use (T. Dam, 2026-11-12) |
| `raw/crossd_metrics_rest.jsonl.gz` | raw /api/metrics responses for every other snapshot of the frozen index up to 2026-11-03, 89,205 responses (`pipeline/crawl_crossd.py --every`) | CrOSSD API `health.crossd.tech/api` | 2026-11-12 | `0a56e5c4d73477b86389095b4f5ff1f3b6f2ae67cbed28d7b20bb6410fddf990` | CrOSSD, free use (T. Dam, 2026-11-12) |
| `raw/scorecard_history_early_2026-11-12.parquet` | published Scorecard weekly scans 2021-09-27 to 2024-02-19 of the panel, check scores only, 165,987 rows (`pipeline/collect_scorecard_history.py --first 2021-09-01 --last 2024-02-29`) | BigQuery `openssf.scorecardcron.scorecard-v2` | 2026-11-12 | `e0d3d00b67470a719ce3926cac98fe34ed4e9ea670949c59447af0bff2617730` | CDLA-Permissive-2.0 |
| `raw/scorecard_history_2026-11-12.parquet` | published Scorecard weekly scans 2024-03-18 to 2026-08-24 of the panel, check scores only, 195,912 rows (`pipeline/collect_scorecard_history.py`) | BigQuery `openssf.scorecardcron.scorecard-v2` | 2026-11-12 | `8218bfd78a460724e0dd0e79dbe371c6a46a7056da5d845b8883a0449e895aa1` | CDLA-Permissive-2.0 |

Derived, not checksummed (regenerated by the pipeline):

- `inputs/git_activity.parquet`, `inputs/git_last.parquet`: commit and tag dates per month, from the commit-only clones in
  `oss-score-validity/data/raw/git/` (read only), cut at the data freeze 2026-11-03. `pipeline/git_activity.py`.
- `web/static/data/*`: the explorer's files. `pipeline/build.py`.

`inputs/metrics.jsonl.gz` differs from the checksum in the replication package's `data/README.md` because that cache is
append-only and grew on 2026-11-04; the copy here was taken on 2026-11-12.
