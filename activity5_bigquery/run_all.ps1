<#
  Activity 5 - complete pipeline from a clean start (run from the project root, PowerShell):
      powershell -ExecutionPolicy Bypass -File activity5_bigquery\run_all.ps1            # run everything
      powershell -ExecutionPolicy Bypass -File activity5_bigquery\run_all.ps1 -Capture   # + console screenshots
  Requires: Google Cloud CLI logged in (gcloud auth login), project bigdatasla in BigQuery Sandbox.
  bq_setup.ps1 deletes and recreates the weblogs dataset, so every run starts clean.
  Logs: evidence\act5\, screenshots: evidence\act5\screenshots\
#>
param([switch]$Capture)
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot; Set-Location $root
$env:Path = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin;" + $env:Path
$env:PYTHONIOENCODING = "utf-8"
$py = ".venv\Scripts\python.exe"; $ev = "evidence\act5"
New-Item -ItemType Directory -Force "$ev\screenshots" | Out-Null

function Step([string]$title, [string]$cmd, [string]$shot, [int]$cols = 160, [int]$lines = 45) {
    Write-Host "`n>>> $title" -ForegroundColor Cyan
    if ($Capture -and $shot) {
        & "$root\common\capture_console.ps1" -Command $cmd -OutFile "$ev\screenshots\$shot.png" -Cols $cols -Lines $lines -TimeoutSec 1200
    } else { Invoke-Expression $cmd }
}

# 0. environment check (gcloud installed, authenticated, correct project, billing disabled) ----------
$chk = "$ev\01_gcloud_check.log"
"### $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | gcloud environment check" | Out-File -Encoding utf8 $chk
foreach ($c in @("gcloud --version", "gcloud auth list", "gcloud config list",
                 "gcloud projects describe bigdatasla --format=`"table(projectId,name,projectNumber,lifecycleState)`"",
                 "gcloud billing projects describe bigdatasla --format=`"value(billingEnabled)`"",
                 "gcloud services list --enabled --project bigdatasla --filter=`"config.name:bigquery.googleapis.com`" --format=`"value(config.name)`"")) {
    Add-Content -Encoding utf8 $chk "`n> $c"
    Invoke-Expression "$c 2>&1" | ForEach-Object { "$_" } | Where-Object { $_ -notmatch "RemoteException" } | Add-Content -Encoding utf8 $chk
}
Step "0. gcloud environment" "Get-Content $chk" "gcloud_check" 130 40

Step "1. generate synthetic logs" "$py -u activity5_bigquery\generate_logs.py --log $ev\02_generate.log" "generate_console" 175 20
Step "2. parse logs (ETL)" "$py -u activity5_bigquery\parse_logs.py --log $ev\02b_parse.log" ""
Step "3. BigQuery dataset/table + batch load" "powershell -NoProfile -ExecutionPolicy Bypass -File activity5_bigquery\bq_setup.ps1" "bq_setup_console" 175 40
Step "4. sandbox limitation probes" "$py -u activity5_bigquery\sandbox_tests.py --log $ev\04_sandbox_tests.log" "sandbox_tests_console" 175 30
Step "5. analytical queries" "$py -u activity5_bigquery\run_queries.py --log $ev\05_queries.log" "queries_console" 180 60
Step "6. verification against local data" "$py -u activity5_bigquery\verify_results.py --log $ev\06_verification.log" "verification_console" 180 45
Step "7. cost estimate" "$py -u activity5_bigquery\cost_estimate.py --log $ev\07_cost_estimate.log" "cost_console" 160 40
Step "8. charts" "$py activity5_bigquery\charts.py" ""

# 9. bq command-line views of the cloud resources ----------------------------------------------
Step "9a. bq show table" "bq --project_id=bigdatasla show bigdatasla:weblogs.access_logs" "bq_show_table" 170 34
Step "9b. bq query from the CLI" "bq --project_id=bigdatasla --location=asia-south1 query --use_legacy_sql=false --nouse_cache 'SELECT status, COUNT(*) AS requests, ROUND(100*COUNT(*)/SUM(COUNT(*)) OVER(),2) AS pct FROM weblogs.access_logs GROUP BY status ORDER BY requests DESC LIMIT 10'" "bq_cli_query" 120 26
Step "9c. bq ls jobs" "bq --project_id=bigdatasla --location=asia-south1 ls -j -n 12" "bq_ls_jobs" 150 20
Write-Host "`nDONE - logs in $ev (no local services to stop: BigQuery is serverless)"
