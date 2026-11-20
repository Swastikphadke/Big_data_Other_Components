# Audit Report – Big Data Systems (24CI51) Self-Learning Activity

**Date:** 2026-11-03 · **Source of truth:** official assignment document (5 activities × 4 marks, common
assessment rubric, submission requirements) · **Scope:** all five activity directories, `evidence/`,
`evidence/manifest.csv`, READMEs, charts, screenshots.

## 1. Method
| Check | How | Result |
|---|---|---|
| A. Directory inventory | `audit/audit.py`: README, Python sources, data, results, charts, configuration files per activity | 7/7 OK |
| B. Manifest | every artefact in `evidence/manifest.csv` (79 entries) resolved on disk, including glob patterns, ranges and stated counts | 79/79 OK after corrections (§5) |
| C. Numbers | 40 key figures recomputed from the result CSVs / logs and searched for in the READMEs | 40/40 OK |
| D. Screenshots | file time of all 77 screenshots compared with the final verified run window of each activity; content of every BigQuery console screenshot inspected | 77/77 in window |
| E. Requirements | each self-learning task and expected outcome in the assignment mapped to artefacts (§3) | all covered (one gap fixed) |
| F. Technical accuracy | claims re-tested where possible (partitioner hash, Tez mode, sandbox limits, partition counts) | 2 inaccuracies found and corrected |
Full machine log: `audit/audit_log.txt`; check table: `audit/audit_checks.csv`.

## 2. Activity-wise verification
| | Act 1 Hive | Act 2 Kafka | Act 3 Flink | Act 4 MongoDB | Act 5 BigQuery |
|---|---|---|---|---|---|
| Executed for real | Hive 4.0.1 (Docker, Tez local mode) | Kafka 4.1.0 KRaft (Docker) | Flink 1.20.5 JM+TM (Docker) | MongoDB 8.0.34 (Docker) | Google BigQuery Sandbox, project bigdatasla, asia-south1 |
| Data | synthetic, 559,626 sales lines | synthetic, 11,520 sensor events | synthetic, 14,400 vital-sign readings | synthetic, 200,000 products | synthetic, 774,130 log lines |
| Final run | 18:50–19:00 | 19:18–19:31 | run 2, 20:08–20:16 | clean start 21:18–21:30 | clean start 22:03–22:07, console 22:23–22:39 |
| Independent check | planted patterns recovered; raw = curated row count | ground truth: 13/13 episodes, P 0.865 / R 0.979 | reference implementation: 12/12 episode events identical; 1,240/1,240 alerts | identical result counts before/after indexing; SQL = Mongo counts | 23/23 pandas + ground-truth checks |
| Charts | 6 | 6 | 7 | 5 | 9 + architecture |
| Screenshots | 8 | 15 | 13 (+12 superseded run 1) | 10 | 19 (10 CLI/console windows + 9 BigQuery console) |
| Logs | 2 + 12 query logs | 13 | 10 + JSON plan | 13 | 8 + BigQuery JSON metadata |

## 3. Assignment requirement coverage
| Activity / task (assignment wording) | Where satisfied |
|---|---|
| **A1** Study Hive architecture, HiveQL, warehousing | report §6.3 (technology study); two-layer warehouse design in `01_schema.hql` |
| A1 Create Hive tables | external raw table + ORC table partitioned by month (`hql/01_schema.hql`, `02_schema_load.log`) |
| A1 Revenue, top-selling products, branch-wise sales (+ peak hours, monthly trend from the problem statement) | q01–q12, `results/*.csv`, 6 charts |
| A1 Analyse and recommend inventory strategies; outcome "business insights" | **gap found**: README had no recommendations → added "Business insights and inventory recommendations" (derived only from q02–q10 results) |
| **A2** Study topics, producers, consumers, brokers | report §7.3; README architecture |
| A2 Simulate traffic data and publish to a topic | `traffic_model.py`, `producer.py`, 11,520 events |
| A2 Consumer to process events | detector, archiver, dashboard (3 consumer groups) |
| A2 Threshold-based congestion alerts | rules in `config.py`; 50 alert events; evaluation vs ground truth |
| **A3** Study Flink architecture / streaming | report §8.3 |
| A3 Simulate continuous vital-sign stream (HR, SpO₂, temperature) | `patient_model.py`, `vitals_producer.py` |
| A3 Flag readings outside demonstration thresholds | Q1 stateless filter, 1,240 reading alerts |
| A3 Alerts + window summaries; synthetic data, not clinical | Q2–Q5 (CEP episodes, 5-min and 15-min windows); disclaimer in data, code, logs, charts, README |
| **A4** Study document storage, collections, indexing, CRUD | report §9.3 |
| A4 Product catalogue as JSON-like documents | `generate_catalog.py`, validator in `setup_db.py` |
| A4 Insert, category / price-range search, stock update, delete discontinued | `crud_demo.py` (C1–C2, R1–R7, U1–U4, D1–D2) |
| A4 Compare document vs relational; outcome "query-performance observations" | `sql_compare.py`; `benchmark.py` (explain plans, 300 timed runs) |
| **A5** Explore a cloud platform; select managed storage and analytics | BigQuery (managed storage + analysis); GCS etc. proposed only |
| A5 Upload a server-log dataset; error frequencies, request volumes, time patterns | batch load job; Q01–Q15 |
| A5 Architecture, workflow, findings, estimated costs; visualisations | README, `a5_architecture.png`, 9 charts, `cost_estimate.py` (official catalog prices) |
| **Submission**: problem definition, technology study, implementation, results, analysis, conclusion | report chapters 6–10 contain each of the six components for every activity |

## 4. Rubric readiness (per activity, 4 marks)
| Criterion (marks) | Evidence available for every activity | Assessment |
|---|---|---|
| Understanding of problem and technology (1) | problem definition, objectives, technology study and architecture in the report | ready |
| Solution design and implementation (1.5) | executed code on real engines, configuration files, documented procedure, clean-start scripts | ready |
| Results, analysis and interpretation (1) | result CSVs, charts, screenshots, quantitative evaluation against ground truth / reference implementations, honest negatives | ready |
| Documentation and conclusions (0.5) | READMEs with viva notes, limitations, conclusions; evidence register | ready |

## 5. Issues found and corrections made
| # | Activity | Issue | Type | Correction |
|---|---|---|---|---|
| 1 | 2 | README stated the producer partitions keys with **murmur2**; the producer is librdkafka, whose default partitioner is CRC32 (`consistent_random`). Re-tested: CRC32(key) % 3 reproduces all 12 observed key→partition assignments; murmur2 does not | technical inaccuracy | README corrected |
| 2 | 5 | README and architecture diagram listed "no Cloud Storage bucket" under **verified** sandbox limits; this was never tested (deliberately – no resources were to be created) | over-claim | reworded as "not tested / deliberately not used"; diagram regenerated |
| 3 | 1 | Task 4 / expected outcome (inventory recommendations, business insights) not documented | missing requirement | section added, every number traceable to q02–q10 |
| 4 | 4 | Benchmark table rounded medians (e.g. 3.05 ms shown as 3.1) | precision | table now shows the exact values from `benchmark_summary.csv` |
| 5 | 3 | manifest said 8 Flink UI screenshots; 9 exist | manifest count | corrected |
| 6 | 5 | 9 BigQuery console screenshots not yet in the manifest; file names had a doubled `.png.png` extension | manifest / naming | added; renamed (content unchanged, SHA-256 prefixes in `audit/renamed_files.txt`) |
| 7 | 2, 5 | several manifest entries used shorthand (`_A/_B`, mixed relative paths) | manifest wording | rewritten as explicit paths |
No measured result, CSV, log or screenshot was altered.

## 6. Disclosures kept as they are (honest negatives, not defects)
* A2: one false-alarm congestion alert (J09, true peak speed 21.5 km/h vs 20 km/h threshold).
* A3: run 1 superseded (quadratic CEP pattern caused back pressure) – kept in a separate, labelled folder; one failed checkpoint whose cause had left Flink's history; REST metric store returned no per-subtask metrics.
* A4: Q5/Q6 show no index benefit (×0.9, within run-to-run variation); a test run earlier gave ×70/×52 for Q1/Q4 vs ×57.8/×49.3 in the clean run.
* A5: one false-positive spike (29 Oct 15:45, z = 4.1); I2 detected as two incidents; detector thresholds calibrated on the same week.
* Two blank console captures (A4 benchmark, A5 setup) were replaced by console windows displaying the genuine log files; both are labelled as such in the manifest.
* Web-UI screenshots (HiveServer2, Kafka-UI, Flink) were captured with headless Microsoft Edge from the running services; console screenshots are real console windows captured programmatically.

## 7. Recommended before submission
1. **Declaration of assistance.** The implementation, execution and evidence capture were carried out with an AI coding assistant on the student's machine. The report contains a declaration section for this; keep it unless the course rules say otherwise, and make sure you can explain every component (viva notes in each README).
2. Fill in the cover-page placeholders (name, USN, semester/section, faculty, date).
3. Screenshots show the Windows user/host name (`Admin@DESKTOP-4S43LMM`) and the Google account e-mail; acceptable for a course report, but be aware they are visible.
4. The BigQuery tables expire automatically 60 days after their partition dates (around 25–31 Dec 2026); demonstrate before then or reload with `run_all.ps1`.

## 8. Readiness assessment
All five activities are implemented, executed on the real technologies, verified, and documented with
traceable evidence. After the corrections in §5 the evidence set is complete and internally
consistent. **Ready for the consolidated report.**
