param([string]$Start = '06:00', [string]$End = '22:00', [double]$Speed = 4)
<#
  Activity 2 - live demo for the viva: opens one window per component so the
  examiner can watch ingestion and alerting happen in real time.
  Run from the project root in PowerShell:
      docker compose --profile kafka up -d
      powershell -ExecutionPolicy Bypass -File activity2_kafka\run_demo.ps1
      powershell -ExecutionPolicy Bypass -File activity2_kafka\run_demo.ps1 -Start 08:00 -End 10:30 -Speed 6
  Demo outputs go to results\demo_*.csv, so the verified evidence files are never overwritten.
#>
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
# clean topics + consumer groups (same steps as setup_topics.sh, without needing bash)
$kbin = "/opt/kafka/bin"; $bs = "--bootstrap-server", "localhost:9092"
foreach ($g in "congestion-detector", "traffic-archiver", "operator-dashboard") {
    docker exec kafka "$kbin/kafka-consumer-groups.sh" @bs --delete --group $g 2>$null | Out-Null }
foreach ($t in "traffic-readings", "congestion-alerts") {
    docker exec kafka "$kbin/kafka-topics.sh" @bs --delete --topic $t 2>$null | Out-Null }
Start-Sleep -Seconds 3
docker exec kafka "$kbin/kafka-topics.sh" @bs --create --topic traffic-readings --partitions 3 --replication-factor 1
docker exec kafka "$kbin/kafka-topics.sh" @bs --create --topic congestion-alerts --partitions 1 --replication-factor 1
$py = "$root\.venv\Scripts\python.exe"
$res = "activity2_kafka\results"
$env:PYTHONIOENCODING = "utf-8"
function Open($title, $cmdArgs) {
    Start-Process conhost.exe -ArgumentList "powershell -NoExit -Command `"`$Host.UI.RawUI.WindowTitle='$title'; & '$py' -u $cmdArgs`""
}
Open "CONSUMER 1 - congestion detector" "activity2_kafka\congestion_detector.py --idle-exit 60 --out $res\demo_alerts.csv"
Open "CONSUMER 2 - archiver"            "activity2_kafka\archiver.py --idle-exit 60 --out $res\demo_ingested.csv"
Open "CONSUMER 3 - control room"        "activity2_kafka\alert_dashboard.py --idle-exit 120"
Start-Sleep -Seconds 5
Open "PRODUCER - junction sensors"      "activity2_kafka\producer.py --speed $Speed --start $Start --end $End"
Write-Host "Kafka-UI: http://localhost:8080   (consumer lag, topics, messages)"
