# Big Data Systems (24CI51) Self-Learning Activity – Execution Playbook

**Audience:** an AI coding assistant (e.g. Claude Code) working on a student's Windows laptop, together with the
student. Read this file completely before doing anything. It distils one complete, audited run of this
assignment: what to build, which versions and settings work, how to verify results, how to collect honest
evidence, and the traps that cost hours. Use it to **build this student's own project** – never copy another
student's code, data, results or screenshots.

---

## 0. Ground rules (non-negotiable)

1. **The student's own work.** Write fresh code for this student, generate data with the student's own seeds
   and scenario details (different city/branch names, product lists, junctions, patients, IP pools, dates).
   Every number in the report must come from this student's executions.
2. **Never fabricate evidence.** No invented outputs, no mock screenshots, no "expected" values presented as
   results. Label every figure/table: **Verified** (from a run), **Design diagram**, **Hypothetical**
   (not deployed, e.g. production cost), **Superseded** (earlier run kept for transparency).
3. **Planted ground truth.** Synthetic data must contain documented, planted patterns/incidents so each
   prototype can be *validated* (precision/recall, recovered patterns), not just displayed. State clearly
   that findings are about synthetic data.
4. **Report honest negatives.** False alarms, queries that indexes don't speed up, superseded runs – keep and
   explain them. Do not tune the data or thresholds until results look perfect.
5. **Declaration of AI assistance** in the report (the student reviews and decides per course rules).
6. **Checkpoint with the student** after each phase/activity; do not start the next activity until the
   current one is executed, verified, documented and its containers are stopped.
7. **Never run destructive bulk deletes** (`rm -rf` on globs, `docker system prune`, killing processes you did
   not start). Overwrite files instead; ask the student when something must be removed.

---

## 1. Phased workflow

| Phase | Output | Exit criterion |
|---|---|---|
| 0 Environment check | versions, RAM, Docker status, Python path | all prerequisites confirmed |
| 1 Plan | short plan per activity (tools, data, evidence) agreed with the student | student approves |
| 2–6 Activities 1–5 | code, data, results CSVs, charts, logs, screenshots, README per activity | verification passes, containers stopped |
| 7 Audit | automated + manual audit, corrections | 0 open issues |
| 8 Report | DOCX (+PDF) | sections complete, rendered pages checked |

Recommended order: Hive → Kafka → Flink (reuses the Kafka service) → MongoDB → BigQuery.
Typical effort: environment 1–2 h, each activity 2–4 h of machine time, report 2–3 h.

**Project layout**
```
project/
  docker-compose.yml          # one file, one PROFILE per activity
  requirements.txt  .venv/
  common/                     # chartstyle.py, teelog.py, capture_console.ps1, capture_web.ps1
  activity1_hive/ activity2_kafka/ activity3_flink/ activity4_mongodb/ activity5_bigquery/
      README.md  *.py  data/  results/  charts/  (sql|hql|bq …)
  evidence/actN/              # logs (01_*.log …), screenshots/
  evidence/manifest.csv       # evidence register: activity, artefact, type, produced_by, status, notes
  audit/                      # audit.py, AUDIT_REPORT.md
  report/                     # figures.py, build_report.py, finalize.ps1
```

---

## 2. Environment (Windows 11, 8 GB RAM laptop – the realistic minimum)

* **Python trap:** `python` on PATH may be an old 2.7 bundled with other software. Run `py -0p` and use
  `py -3.12 -m venv .venv`; always call `.venv\Scripts\python.exe`.
* Libraries: pandas, numpy, matplotlib, pyarrow, confluent-kafka, pymongo, google-cloud-bigquery, db-dtypes
  (+ python-docx, pymupdf, defusedxml, lxml for the report).
* **Docker Desktop must be running** (`docker version` fails with a pipe error otherwise – start
  `Docker Desktop.exe`). Check the VM limit: `docker info` → MemTotal (typically ~3.75 GiB on 8 GB laptops).
* **One Docker Compose profile per activity** (`hive`, `kafka`, `flink`, `mongo`); start one, stop it
  (`docker compose --profile X down`) before the next. Host free RAM can drop below 1 GB (browsers!) –
  ask the student to close heavy apps before Flink.
* Google Cloud CLI for Activity 5 (`winget install Google.CloudSDK`); the student logs in in the browser.

### Shell and tooling traps (each cost real time)
| Trap | Fix |
|---|---|
| Git Bash rewrites `/opt/...` in `docker exec` args to `C:/Program Files/Git/opt/...` ("No FileSystem for scheme C") | `export MSYS_NO_PATHCONV=1` |
| `bash` typed in PowerShell resolves to WSL (no distro → error) | use Git Bash explicitly or write PowerShell equivalents |
| PowerShell 5.1: native stderr becomes error records; with `$ErrorActionPreference='Stop'` any `docker compose` progress message aborts the script | use `Continue`, redirect `2>$null`, check `$LASTEXITCODE` |
| `Tee-Object` in PS 5.1 writes UTF-16; culture `en-IN` prints 7,74,130 | give every script a `--log` option that mirrors stdout to a UTF-8 file (small `teelog.py`); set InvariantCulture in PS scripts |
| Piping text from PowerShell to a native exe adds a UTF-8 BOM (`bq query` → "Illegal input character \357") | run BigQuery from Python (see A5) |
| `cmd /c "... | \"C:\Program Files\...\""` quoting breaks | avoid shell piping; let programs write their own logs |
| PowerShell `-like 'name[22]*'` treats `[22]` as a wildcard class | use `.StartsWith()` / `.Contains()` |
| Editing Python/JS source through a heredoc'd Python script turns `"\n"` into real newlines → syntax errors | use the editor tool for edits containing escapes |
| pandas 3 infers datetime resolution; `astype('int64')//10**6` gives nonsense | `.dt.as_unit("ms").astype("int64")` |
| Long-running commands time out the tool | run in background and watch a progress log with a bounded wait |

### Evidence capture that is genuine
* **Logs:** every script prints a header `### <timestamp> | $ python <argv>` and tees to `evidence/actN/NN_name.log`.
* **Console screenshots:** run the command in a *real new console window* (start `conhost.exe powershell
  -NoExit -EncodedCommand …`), wait for a marker file, capture the window with the Win32 `PrintWindow`
  API (no foreground needed), save PNG, close the window. Print a header line with date/time,
  `user@host` and the command. **Keep consoles ≤ 180 columns** – wider windows produce a blank 1 KB image.
  If a capture fails and the run cannot be repeated without changing data, capture a console window that
  *displays the genuine log file* and label it exactly that way.
* **Web UIs** (HiveServer2 :10002, Kafka-UI :8080, Flink :8081): headless Edge
  `msedge --headless=new --user-data-dir=<temp> --window-size=1600,1000 --virtual-time-budget=20000
  --screenshot=<file> <url>`. A separate `--user-data-dir` is required if Edge is open. Streaming pages
  (Kafka-UI "Messages") render only a spinner – skip them.
* **Cloud console screenshots** need the student's browser login – give the student an exact list.
* Inspect every screenshot after capture; delete or relabel wrong ones; never keep screenshots of failed runs
  as evidence (move superseded runs to a clearly named folder if they are instructive).
* **Clean-start runs:** for each activity write `run_all.ps1` that rebuilds from scratch (drop volume /
  dataset), runs every step with `--log`, and optionally `-Capture` (screenshots). Final evidence should come
  from that single clean run.

### Charts
One shared style module; colour by role (one sequential hue for magnitude, a highlight colour for the
point of interest, reserved red for alerts); never dual axes – use small multiples; every chart footnote
names its source CSV/query; open and look at each PNG (label overlaps, clipped titles, log scale with
stacked bars is misleading).

---

## 3. Activity blueprints

### Activity 1 – Apache Hive: supermarket sales
* **Image:** `apache/hive:4.0.1`, env `SERVICE_NAME=hiveserver2`, `SERVICE_OPTS=-Xmx2g`, ports 10000/10002,
  bind-mount the activity folder to `/opt/assignment`. Embedded Derby metastore, Tez **local mode**
  (`tez.local.mode=true` in the image's hive-site.xml). Wait for readiness by polling `beeline -e 'SELECT 1'`.
* **Data (generator, fixed seed, ~200k invoices → ~500k+ line items):** branches with different footfall,
  ~100+ products with **fixed realistic prices** (random prices produce ₹376 toothpaste), category purchase
  frequencies × lognormal product spread (a Pareto spread made one product 18 % of all units – unrealistic),
  hour-of-day profile with an evening peak, weekend factor, festive month uplift, summer categories,
  2 planted slow movers. Save `planted_patterns.json`. CSV without header into `data/raw/`.
* **Design:** EXTERNAL TEXTFILE `sales_raw` (LOCATION `file:///opt/assignment/data/raw`, schema-on-read) →
  managed ORC (ZLIB) table partitioned by `sale_month` filled with dynamic-partition
  `INSERT OVERWRITE … PARTITION (sale_month)`; derived columns (amount, hour, day type) computed once.
* **Queries (~12):** KPIs, top products by revenue and by units, branch revenue with
  `SUM(SUM(x)) OVER ()` share, peak hours, monthly trend with `LAG`, category seasonality pivot, top-3 per
  branch with `RANK`, slow movers, weekday vs weekend, payment mix, `EXPLAIN DEPENDENCY` with a month filter
  (shows only one partition read). Run each through Beeline twice: table output → log, `--outputformat=csv2`
  → results CSV.
* **Observations worth explaining (verified in a real run):** Hive 4 reports the "managed" ORC table as
  `EXTERNAL_TABLE` with `TRANSLATED_TO_EXTERNAL=TRUE`; `COUNT(*)` on the curated table is answered from
  metastore statistics without a Tez job (so don't claim a scan speed-up from it – the verified ORC gain is
  storage, ~10× smaller).
* **Do not forget task 4 / expected outcome:** a **business-insights and inventory-recommendations** table,
  every row tied to a query result (restock before peak, festive buffer stock, summer stock, branch
  allocation, slow movers). This was the one requirement found missing in the audit of the reference run.
* Evidence: Beeline consoles (partitions + row counts with Tez DAG, a branch query, the EXPLAIN), HS2 Web UI.

### Activity 2 – Apache Kafka: traffic congestion alerts
* **Image:** `apache/kafka:4.x` (KRaft, no ZooKeeper). Setting *any* `KAFKA_*` env replaces the default
  config, so set the full KRaft config: `NODE_ID`, `PROCESS_ROLES=broker,controller`, listeners
  `PLAINTEXT://:9092,DOCKER://:29092,CONTROLLER://:9093`, advertised `PLAINTEXT://localhost:9092,
  DOCKER://kafka:29092` (second listener lets other containers – Kafka-UI, Flink – connect), protocol map,
  controller listener, quorum voters, replication factors 1, `AUTO_CREATE_TOPICS_ENABLE=false`,
  `KAFKA_HEAP_OPTS=-Xms256m -Xmx512m`. Optional Kafka-UI (`ghcr.io/kafbat/kafka-ui`, JAVA_OPTS -Xmx256m)
  for screenshots.
* **Topics:** readings topic with 3 partitions, alerts topic with 1; setup script also deletes old consumer
  groups so runs start clean.
* **Model with ground truth:** junction classes (heavy/medium/light), morning + evening demand peaks,
  speed falls with volume/capacity, noise; planted **incident** (low speed + low count = blockage) and one
  **single faulty sensor reading** that must NOT trigger an alert. Keep noise-free values as ground truth.
  Check each "light" junction really never congests (one did in the reference run → fix before evidence).
* **Producer:** confluent-kafka, key = junction id, `acks=all`, `enable.idempotence=True`, small
  `linger.ms`, lz4; replay a day at N simulated minutes per real second; delivery callback counts per
  partition.
* **Consumers (3 groups):** detector (rolling window of last 5 readings per junction; rules on averages:
  congestion = speed < T1 and count ≥ C1; incident = speed < T2 and count < C2; severity bands; CLEAR only
  above a higher speed → hysteresis; publishes OPEN/ESCALATE/CLEAR to the alerts topic), archiver (stores
  every reading with partition, offset, CreateTime → latency), operator dashboard (reads alerts). Use an
  idle-exit timeout so consumers finish on their own. Add `--no-publish` for experiments.
* **Evaluate:** integrity (generated = ingested, no duplicates, per-key order), latency percentiles,
  minute-level precision/recall and per-episode detection delay vs ground truth, false alarms explained
  (a junction whose true peak speed sits just above the threshold will alarm – keep it as a finding).
* **Demos:** replay with a new group id (reads from offset 0), scale-out with two detectors in one group
  (show partition assignment, `kafka-consumer-groups --describe` while running, prove alerts are identical).
* **Fact check:** librdkafka (confluent-kafka) uses the `consistent_random` partitioner = **CRC32(key) %
  partitions**, not murmur2 (Java client). Verify with the observed key→partition mapping. With few keys
  partitions are uneven – explain it.
* Capture consumer-group lag *during* the run (console + Kafka-UI). A viva demo script should write to
  separate `demo_*` files so it never overwrites evidence.

### Activity 3 – Apache Flink: patient vital signs (synthetic, educational thresholds)
* **Memory first:** default Flink (JM ~1.6 GB + TM ~1.7 GB) + Kafka does not fit an 8 GB laptop. Use
  JM `jobmanager.memory.process.size: 768m`, TM `taskmanager.memory.process.size: 1152m`,
  `taskmanager.memory.managed.fraction: 0.1`, 2 slots, parallelism 2; start containers one by one and log
  host-free/VM memory; set an abort threshold. Measured peak in the reference run ≈ 2.1 GB total.
* **Image:** Dockerfile `FROM flink:1.20.x` + `apt-get install python3 python3-pip` + `pip install
  apache-flink==<same 1.20.x>` + `flink-sql-connector-kafka-3.4.0-1.20.jar` into `/opt/flink/lib`
  (PyFlink 1.20 needs Python ≤ 3.11 → run the PyFlink client inside the container, Ubuntu jammy has 3.10).
  Submit with `docker exec <jm> flink run -d -py /opt/…/job.py`.
* **Data:** ~10 patients, a reading every few seconds over ~2 h; planted **sustained** episodes
  (tachycardia, desaturation, gradual fever, multi-vital, noisy bradycardia), **transient** bursts (6–8
  readings) and **isolated** single spikes; delivery delays: most on time, ~10 % out of order within the
  watermark bound, ~0.5 % very late beyond it. Send in **arrival order**. At the end send one
  end-of-stream marker **per partition** with a later event time (watermark = min over partitions, so final
  windows only close this way); filter the marker out first in the job.
* **Job (Table API/SQL, one StatementSet):** Kafka source with `WATERMARK FOR event_time AS event_time -
  INTERVAL '30' SECOND` and Kafka metadata (timestamp, partition, offset); Q1 stateless filter → reading
  alerts; unpivot vitals → `OVER (PARTITION BY patient, vital ORDER BY event_time ROWS BETWEEN 11 PRECEDING
  AND CURRENT ROW)` score = abnormal count; Q2 onset and Q3 resolution with **MATCH_RECOGNIZE**; Q4 per-patient
  TUMBLE 5 min; Q5 ward TUMBLE 15 min. Sinks = Kafka topics; a host collector writes CSVs. Checkpoint every 10 s.
* **Two design traps (both hit in the reference run):**
  1. "N consecutive abnormal readings" misses noisy episodes (a bradycardia at ~46 bpm vs 50 threshold breaks
     every few readings). Use a **score with hysteresis**: onset when ≥ 9 of last 12 abnormal after ≤ 3;
     resolved when ≤ 3. Check this offline on the generated data *before* running Flink.
  2. Pattern `(S X* L)` starts a partial match at every high-score row → quadratic work during a long episode
     → Match operator 100 % busy, back pressure, stalled watermarks, missing events. **Anchor patterns at a
     calm row:** onset `(L M* S)`, resolved `(L M* S X* R)`.
* **Verify:** independent pandas reference that simulates the watermark from the actual Kafka delivery order
  (per-partition max event time − bound, min over partitions) → predicts which rows are late for row-ordered
  operators vs windows; compare episode events (should be identical), window counts, reading alerts (all
  abnormal readings incl. very late ones, because the stateless filter needs no watermark), latency
  (stateless ≈ tens of ms; event-time ops ≈ watermark delay).
* **Flink REST quirks:** right after start the metric store returns zeros (warm up, then read); per-subtask
  metrics may be empty in Docker – job-level `read-records`/`write-records` from `/jobs/<id>` after the job is
  idle are reliable (e.g. OVER in = readings × 3, out = in − late rows × 3). Web-UI URL patterns:
  `#/job/running/<jid>/overview`, `…/overview/<vertexId>/watermarks`, `…/backpressure`, `…/checkpoints`.
* Disclaimer "synthetic data, educational thresholds, not a clinical tool" in data, code, logs, charts, README.

### Activity 4 – MongoDB: e-commerce catalogue
* **Image:** `mongo:8.0`, command `--wiredTigerCacheSizeGB 0.25`, port `127.0.0.1:27017`, named volume
  (clean start = `down -v`). Use mongosh inside the container for shell evidence (`docker cp` scripts in).
* **Data (~200k products, ~11 categories):** common core + category-specific `specs` + embedded `variants`
  for apparel/footwear. Realism checks that caught errors: model series must belong to the brand and the
  category (no "Vivo Pixel", no TV series on earbuds), Apple-only CPUs only on Apple, TV price scales with size,
  appliance capacity units (kg vs litres vs ton), sport ↔ item ↔ price consistency. Inspect samples per
  category before loading.
* **Validator:** `$and: [$jsonSchema(required core fields, types, min 0, enums, SKU pattern), {$expr: {$gte:
  ["$mrp","$price"]}}]`, `validationLevel: strict`, `validationAction: error`; `specs` only `bsonType:
  object`. Demo: several invalid writes rejected (code 121, parse `errInfo` recursively to show field +
  rule), an invalid update rejected, duplicate SKU rejected (E11000 via unique index), a document with new
  attributes accepted; delete the test doc so the dataset is unchanged.
* **Benchmark (identical conditions):** drop secondary indexes, `planCacheClear`, warm the cache with a full
  scan, 3 warm-ups + 25 timed runs per query (consume the cursor), `explain` with `executionStats`; create
  indexes (unique sku, single field, compound `{category, price}` following ESR, text, partial on active stock,
  descending rating) and repeat. Include queries that should **not** benefit (low selectivity, no usable
  index). Report docs/keys examined, server ms and client medians; don't call 0.9× a slowdown if within
  run-to-run variation – report both runs if they differ. Explain server time vs transfer/decode time.
* **CRUD:** insert_one/many, find by _id/sku, category + price range sorted, nested spec filter, `$elemMatch`
  on variants, `$text` search, atomic conditional stock decrement (no oversell), `$addToSet`/`$set`,
  `arrayFilters` + pipeline update recompute, `update_many` restock via partial index, `delete_many`
  discontinued; aggregation reports (`$group`, `$bucket`).
* **Relational comparison:** export the same data to SQLite (products + EAV specs + variants + tags).
  **Performance trap:** inserting ~2M rows with indexes and FK checks on a memory-starved laptop took 23
  minutes – stream in chunks, `PRAGMA journal_mode=OFF; synchronous=OFF`, build secondary indexes after the
  load (→ ~30 s). Compare counts of equivalent queries (must match), rows needed (1 doc vs N joined rows),
  schema evolution; timings only as an observation (in-process SQLite vs MongoDB over TCP is not fair).
* Clean-start `run_all.ps1` (wipe volume → generate → load → benchmark → validation → CRUD → compare → charts →
  mongosh checks). Benchmark console output is wide – cap console width or the capture is blank.

### Activity 5 – Cloud analytics on Google BigQuery Sandbox (no billing)
* **Verify first:** `gcloud auth list`, `gcloud config get-value project`, `gcloud projects describe <id>`,
  `gcloud billing projects describe <id>` → `billingEnabled: False`, `bq query --dry_run 'SELECT 1'`. The
  student does the browser login. Never enable billing or create Cloud Storage buckets.
* **Sandbox reality (verify empirically, harmlessly):** tables/partitions expire after 60 days → **generate
  log dates inside the last few weeks** (year-old partitioned data would be deleted on load); DML and
  streaming inserts are refused ("not allowed in the free tier") – test with a zero-row `INSERT … SELECT …
  WHERE FALSE` and `insert_rows_json` into a temporary probe table, then delete it. Do not claim limits you
  did not test (e.g. Cloud Storage) – say "not tested".
* **Data:** a week of Apache combined-format logs (+ response ms), ~700k+ lines, daily cycle, endpoint mix,
  bots restricted to public pages, IP pool; planted incidents: outage (5xx on payment/checkout), bad deployment
  (500 on one API), credential stuffing (bursts of 401 on POST /login with some successes), scraper with 429
  throttling, vulnerability scanner (/.env, /wp-login.php …, 404/403), traffic peak. Attackers from
  documentation ranges 203.0.113.0/24, 198.51.100.0/24. A few truncated lines to test the parser.
* **ETL + load:** regex parser → typed CSV.gz (+ rejected lines file); table schema JSON with REQUIRED core
  fields; **partition DAY(ts), cluster by endpoint, status**; `bq load --source_format=CSV
  --skip_leading_rows=1` (batch load job, free). Location e.g. `asia-south1`. Save dataset/table/job JSON.
* **Queries:** run from Python with `google-cloud-bigquery` and credentials from `gcloud auth
  print-access-token` (avoids the PowerShell BOM problem and returns job stats); `use_query_cache=False`;
  record job id, bytes processed/billed, slot ms, elapsed. Analyses: overview, status codes, top endpoints
  with p50/p95 (`APPROX_QUANTILES`), errors by endpoint, hourly/daily volume, weekday×hour profile, busiest
  5-min windows, top IPs with max requests/minute, 5-min failure series, failure-spike detection, brute force,
  scanners, high-rate automation, user-agent classes, `INFORMATION_SCHEMA.JOBS_BY_USER`.
* **Spike-detector trap:** a rolling mean/stddev of the previous hour lets an outage inflate its own baseline
  (self-masking → only 1 bucket flagged). Use expected failures = requests × failure rate of the previous ~24 h
  *excluding the last hour*, Poisson z = (obs − exp)/√exp ≥ 4 and ≥ 8 failures, merge buckets ≤ 10 min apart.
  Report false positives and incidents split in two.
* **BigQuery SQL trap:** correlated subqueries referencing other tables are rejected → aggregate in a CTE and
  join.
* **Cost facts to measure:** every query is billed at least 10 MiB; partition filters aligned to UTC days read
  1 partition, an IST day spans 2 UTC partitions (the console shows 8 partitions for 7 IST days); adding a long
  string column multiplies bytes (columnar billing); clustering does not help tiny partitions.
* **Prices:** pricing web pages may be unreadable for tools; the Cloud Billing Catalog API works with the gcloud
  token (`GET https://cloudbilling.googleapis.com/v1/services` → BigQuery `24E6-581D-38E5`, Cloud Storage
  `95FF-2EF5-5EA1` → `/skus?currencyCode=USD`; **don't** send `x-goog-user-project`, it requires enabling the
  Billing API). Cost section: Part A actual (Sandbox, USD 0 with % of free tiers) and Part B **hypothetical**
  production scenario with explicit assumptions and SKU ids.
* **Verify:** recompute every query result with pandas from the local CSV (IST conversion, 5-min buckets,
  regexes, the detector) and compare row by row; reconcile ground-truth counts with parser-rejected lines.
* **Architecture diagram:** solid = services actually used, dashed = proposed (GCS landing zone, scheduled
  loads, Looker Studio, Cloud Monitoring).
* **Student-captured console screenshots:** Sandbox banner + Explorer, table Schema, Details (partitioning,
  clustering, expiry, rows), a query with Results and Job information (bytes processed/billed), Execution
  details. Remind the student to save them as `.png` (not `.png.png`).

---

## 4. Audit before writing the report
Write `audit/audit.py` (read-only) and fix documentation until it reports 0 issues:
1. Inventory per activity (README, code, data, results, charts, config).
2. Every manifest artefact resolves on disk (handle globs, ranges like `q01..q12`, stated counts).
3. 30–40 key numbers recomputed from CSV/logs and found verbatim in READMEs (rounding mismatches count).
4. Screenshot timestamps fall inside each activity's final-run window.
5. Requirement matrix: every task and expected outcome in the teacher's document → artefact/section.
6. Re-test technical claims experimentally where possible (partitioner hash, engine mode, sandbox limits).
Write `audit/AUDIT_REPORT.md` (method, activity-wise verification, coverage, issues + corrections,
disclosures, readiness). Never alter measured results – only documentation.

---

## 5. The consolidated report
**Structure:** Cover (placeholders: Student Name, USN, Semester and Section, Faculty Name, Submission Date) →
Declaration (incl. AI assistance, synthetic data) → Executive Summary (table per activity) → Table of Contents,
List of Figures, List of Tables → 1 Introduction & Objectives (scenarios table, evidence-label legend, rubric
mapping) → 2 Execution Environment (versions table, environment diagram, memory management, evidence
method) → 3–7 one chapter per activity with **x.1 Problem Definition, x.2 Objectives, x.3 Technology Study,
x.4 Architecture and Working (diagram), x.5 Implementation and Procedure, x.6 Code/Queries/Configuration
(excerpts), x.7 Results and Sample Outputs (tables from CSV, charts, screenshots), x.8 Analysis and
Interpretation, x.9 Limitations and Improvements, x.10 Conclusion, + rubric coverage table** (Understanding 1,
Design & implementation 1.5, Results & analysis 1, Documentation & conclusions 0.5) → 8 Comparative Analysis
(table: role, processing model, data model, query interface, observed latency, scaling, fault tolerance,
strength/weakness observed) → 9 Overall Conclusion → References (official docs + the Hive, Kafka, Flink, Dremel
papers) → Appendices: A source code, B configuration, C evidence register, D audit summary, E reproduction guide.

**How to build it (worked):** python-docx script that reads result CSVs at build time (numbers cannot drift),
custom caption styles "Figure Caption"/"Table Caption" so Word builds lists of figures/tables with
`TOC \t "Figure Caption,1"`, header text + "Page X of Y" footer fields, first-page different, tables with header
row repeat, evidence label in every caption. Then Word COM: open → update the three TOC fields →
`UpdatePageNumbers` → save → export PDF.

**Report-building traps:**
* Put **each code line in its own paragraph** – one multi-page paragraph full of line breaks makes Word's
  field update/pagination effectively hang.
* python-docx's template opens in **Compatibility Mode** (14); call `SetCompatibilityMode(15)` before export.
* Word's PDF export can stall indefinitely if the default printer is a virtual driver (e.g. AnyDesk Printer).
  Test-export pages 1–5 first with a time limit; if it hangs, have the student open the DOCX and use
  **File › Save As › PDF** (or switch the default printer to "Microsoft Print to PDF" – the student's decision).
  Don't kill Word processes you did not start; quit your own automation instance through COM (`Quit(0)`).
* Validate the DOCX (schema validator), render sample PDF pages to PNG (PyMuPDF) and look at them.

---

## 6. Final checklist
- [ ] Each activity: README (architecture, run steps, verified results, issues & decisions, limitations, viva questions)
- [ ] Every task and expected outcome in the teacher's document covered (Hive recommendations!)
- [ ] Evidence register complete; audit 0 issues; screenshots genuine and correctly labelled
- [ ] Containers stopped; BigQuery dataset noted to expire after 60 days
- [ ] Report: all sections, captions with labels, rubric tables, declaration, placeholders for the student to fill
- [ ] DOCX + PDF produced (or PDF via File › Save As)
- [ ] Student briefed on viva notes
