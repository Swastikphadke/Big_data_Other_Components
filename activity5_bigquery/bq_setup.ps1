<#
  Activity 5 - create the BigQuery dataset/table and BATCH-LOAD the parsed logs.
  BigQuery Sandbox (no billing). Run from the project root in PowerShell after:
      .venv\Scripts\python.exe activity5_bigquery\generate_logs.py
      .venv\Scripts\python.exe activity5_bigquery\parse_logs.py
  Re-running drops and recreates the dataset (clean start).
#>
param([string]$Project = "bigdatasla", [string]$Dataset = "weblogs", [string]$Location = "asia-south1")
$ErrorActionPreference = "Continue"
[Threading.Thread]::CurrentThread.CurrentCulture = [Globalization.CultureInfo]::InvariantCulture   # 774,130 not 7,74,130
$env:Path = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin;" + $env:Path
$root = Split-Path -Parent $PSScriptRoot; Set-Location $root
$ev = "evidence\act5"; New-Item -ItemType Directory -Force "$ev\bq_json" | Out-Null
$log = "$ev\03_bq_setup.log"
function L($s) {   # write UTF-8 log + console; drop PowerShell stderr wrappers and bq progress spinner lines
    foreach ($x in @($s)) { $t = "$x"; if ($t -match "RemoteException|^\s*Waiting on .*RUNNING|^\s*$") { continue }
        Write-Output $t; Add-Content -Encoding utf8 -Path $log -Value $t } }
"### $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | activity5_bigquery\bq_setup.ps1  project=$Project dataset=$Dataset location=$Location" | Out-File -Encoding utf8 $log

L "`n> gcloud config get-value project / account"
L (gcloud config get-value project 2>$null); L (gcloud config get-value account 2>$null)
L "> billing enabled? $(gcloud billing projects describe $Project --format='value(billingEnabled)' 2>$null)"

L "`n> bq rm -r -f -d ${Project}:${Dataset}   (clean start, ignore 'not found')"
bq --project_id=$Project rm -r -f -d "${Project}:${Dataset}" 2>&1 | ForEach-Object { L "  $_" }

L "`n> bq mk --dataset --location=$Location ${Project}:${Dataset}"
bq --project_id=$Project --location=$Location mk --dataset --description "Synthetic web-server logs (24CI51 Activity 5)" "${Project}:${Dataset}" 2>&1 | ForEach-Object { L "  $_" }
bq --project_id=$Project show --format=prettyjson "${Project}:${Dataset}" | Out-File -Encoding utf8 "$ev\bq_json\dataset_weblogs.json"
$ds = Get-Content "$ev\bq_json\dataset_weblogs.json" -Raw | ConvertFrom-Json
L ("  location={0}  defaultTableExpirationMs={1} ({2:N0} days)  defaultPartitionExpirationMs={3}" -f $ds.location, $ds.defaultTableExpirationMs, ($ds.defaultTableExpirationMs / 86400000), $ds.defaultPartitionExpirationMs)

L "`n> bq mk --table (partitioned by DAY on ts, clustered by endpoint,status)"
bq --project_id=$Project mk --table --schema activity5_bigquery\bq\schema_access_logs.json `
   --time_partitioning_field ts --time_partitioning_type DAY --clustering_fields endpoint,status `
   --description "Parsed access logs of shop.example.in (synthetic)" "${Project}:${Dataset}.access_logs" 2>&1 | ForEach-Object { L "  $_" }

$job = "load_access_logs_" + (Get-Date -Format "yyyyMMdd_HHmmss")
L "`n> bq load (batch load job $job) data\processed\access_logs.csv.gz"
$t = Get-Date
bq --quiet --project_id=$Project --location=$Location --job_id=$job load --source_format=CSV --skip_leading_rows=1 --max_bad_records=0 `
   "${Project}:${Dataset}.access_logs" activity5_bigquery\data\processed\access_logs.csv.gz 2>&1 | ForEach-Object { L "  $_" }
L ("  wall time {0:N1} s" -f ((Get-Date) - $t).TotalSeconds)
bq --project_id=$Project --location=$Location show --format=prettyjson -j $job | Out-File -Encoding utf8 "$ev\bq_json\job_$job.json"
$j = Get-Content "$ev\bq_json\job_$job.json" -Raw | ConvertFrom-Json
L ("  job state={0} errors={1} inputFiles={2} inputFileBytes={3:N0} outputRows={4:N0} badRecords={5}" -f $j.status.state,
   ($j.status.errors | ConvertTo-Json -Compress), $j.statistics.load.inputFiles, [int64]$j.statistics.load.inputFileBytes,
   [int64]$j.statistics.load.outputRows, $j.statistics.load.badRecords)

bq --project_id=$Project show --format=prettyjson "${Project}:${Dataset}.access_logs" | Out-File -Encoding utf8 "$ev\bq_json\table_access_logs.json"
$tb = Get-Content "$ev\bq_json\table_access_logs.json" -Raw | ConvertFrom-Json
$exp = if ($tb.expirationTime) { [DateTimeOffset]::FromUnixTimeMilliseconds([int64]$tb.expirationTime).ToString("yyyy-MM-dd HH:mm 'UTC'") } else { "none" }
L ("`n  table: numRows={0:N0}  logical bytes={1:N0} ({2:N1} MiB)  partitioning={3}  clustering={4}  expirationTime={5}" -f [int64]$tb.numRows,
   [int64]$tb.numBytes, ([int64]$tb.numBytes / 1MB), ($tb.timePartitioning | ConvertTo-Json -Compress), ($tb.clustering.fields -join ","), $exp)
L "`n> bq ls ${Dataset}"
bq --project_id=$Project ls "${Project}:${Dataset}" 2>&1 | ForEach-Object { L "  $_" }
