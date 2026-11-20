<#
  Activity 4 - complete pipeline FROM A CLEAN START (run from the project root, PowerShell):
      powershell -ExecutionPolicy Bypass -File activity4_mongodb\run_all.ps1            # run everything
      powershell -ExecutionPolicy Bypass -File activity4_mongodb\run_all.ps1 -Capture   # + console screenshots
  Steps: wipe MongoDB volume -> start mongod -> generate data -> create validated collection + load ->
         benchmark (before / create indexes / after) -> validation demo -> CRUD + aggregations ->
         relational comparison -> charts -> mongosh checks -> stop container.
  Logs go to evidence\act4\, screenshots (with -Capture) to evidence\act4\screenshots\.
#>
param([switch]$Capture, [switch]$KeepRunning)
# "Continue": Windows PowerShell 5.1 turns any stderr text of native tools (docker prints progress there)
# into an error record; with "Stop" that would abort the script. Real failures are checked explicitly.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = ".venv\Scripts\python.exe"
$ev = "evidence\act4"
New-Item -ItemType Directory -Force "$ev\screenshots" | Out-Null
$env:PYTHONIOENCODING = "utf-8"

function Step([string]$title, [string]$cmd, [string]$shot, [int]$cols = 150, [int]$lines = 45) {
    Write-Host "`n>>> $title" -ForegroundColor Cyan
    if ($Capture -and $shot) {
        & "$root\common\capture_console.ps1" -Command $cmd -OutFile "$ev\screenshots\$shot.png" -Cols $cols -Lines $lines -TimeoutSec 1200
    } else {
        Invoke-Expression $cmd
    }
}

# 0. clean start ------------------------------------------------------------------------------
Write-Host ">>> clean start: removing container and mongo_data volume" -ForegroundColor Cyan
docker compose --profile mongo down -v 2>$null | Out-Null
docker compose --profile mongo up -d 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }
$ok = $false
foreach ($i in 1..30) {
    if ((docker exec mongodb mongosh --quiet --eval "db.runCommand({ping:1}).ok" 2>$null) -match "1") { $ok = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ok) { throw "mongod did not become ready" }
"### $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | clean start: docker compose --profile mongo down -v; up -d" | Out-File -Encoding utf8 "$ev\00_clean_start.log"
docker volume ls --filter name=mongo_data | Out-File -Append -Encoding utf8 "$ev\00_clean_start.log"
docker exec mongodb mongosh --quiet --eval "db.adminCommand({listDatabases:1}).databases.map(d=>d.name)" | Out-File -Append -Encoding utf8 "$ev\00_clean_start.log"

# 1-6. pipeline ----------------------------------------------------------------------------------
Step "1. generate synthetic catalog" "$py -u activity4_mongodb\generate_catalog.py --log $ev\01_generate.log" ""
Step "2. create validated collection + bulk load" "$py -u activity4_mongodb\setup_db.py --log $ev\02_setup_db.log" "setup_db_console" 150 40
Step "3. benchmark before/after indexing" "$py -u activity4_mongodb\benchmark.py --log $ev\03_benchmark.log" "benchmark_console" 245 40
Step "4. schema validation demo" "$py -u activity4_mongodb\validation_demo.py --log $ev\04_validation_demo.log" "validation_console" 175 32
Step "5. CRUD + aggregations" "$py -u activity4_mongodb\crud_demo.py --log $ev\05_crud_demo.log" "crud_console" 175 60
Step "6. document vs relational comparison" "$py -u activity4_mongodb\sql_compare.py --log $ev\06_sql_compare.log" "sql_compare_console" 175 45
Step "7. charts" "$py activity4_mongodb\charts.py" ""

# 8. checks from the MongoDB shell ----------------------------------------------------------------
docker cp activity4_mongodb\mongosh\. mongodb:/scripts | Out-Null
foreach ($m in "m1_overview", "m2_explain", "m3_validation", "m4_aggregate") {
    $log = "$ev\07_mongosh_$m.log"
    "### $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | docker exec mongodb mongosh --quiet /scripts/$m.js" | Out-File -Encoding utf8 $log
    docker exec mongodb mongosh --quiet "/scripts/$m.js" | Out-File -Append -Encoding utf8 $log
    Step "8. mongosh $m" "docker exec mongodb mongosh --quiet /scripts/$m.js" "mongosh_$m" 150 48
}
"### $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | docker stats --no-stream" | Out-File -Encoding utf8 "$ev\08_docker_stats.log"
docker stats --no-stream --format "{{.Name}}  mem={{.MemUsage}}  cpu={{.CPUPerc}}" | Out-File -Append -Encoding utf8 "$ev\08_docker_stats.log"
Step "9. container resources" "docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}'" "docker_stats" 110 8

if (-not $KeepRunning) {
    docker compose --profile mongo stop 2>$null | Out-Null
    Write-Host "`nmongodb container stopped (data volume kept; use 'docker compose --profile mongo up -d' to restart)"
}
Write-Host "`nDONE - logs in $ev"
