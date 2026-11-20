# Activity 3 - (re)create the input and output topics (run from project root, PowerShell).
$k = "/opt/kafka/bin"; $bs = "--bootstrap-server", "localhost:9092"
foreach ($g in "flink-vitals-monitor", "vitals-collector") {
    docker exec kafka "$k/kafka-consumer-groups.sh" @bs --delete --group $g 2>$null | Out-Null }
$topics = [ordered]@{ "patient-vitals" = 2; "vital-alerts" = 1; "episode-alerts" = 1; "patient-summaries" = 1; "ward-summaries" = 1 }
foreach ($t in $topics.Keys) { docker exec kafka "$k/kafka-topics.sh" @bs --delete --topic $t 2>$null | Out-Null }
Start-Sleep -Seconds 3
foreach ($t in $topics.Keys) {
    docker exec kafka "$k/kafka-topics.sh" @bs --create --topic $t --partitions $topics[$t] --replication-factor 1 }
docker exec kafka "$k/kafka-topics.sh" @bs --describe --topic patient-vitals
