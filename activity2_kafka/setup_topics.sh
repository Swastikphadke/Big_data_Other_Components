#!/usr/bin/env bash
# Activity 2 - (re)create topics and reset consumer groups for a clean run.
# Usage (project root, Git Bash):  bash activity2_kafka/setup_topics.sh
export MSYS_NO_PATHCONV=1
K="docker exec kafka /opt/kafka/bin"
BS="--bootstrap-server localhost:9092"
for g in congestion-detector traffic-archiver operator-dashboard audit-replay congestion-detector-scaleout; do
  $K/kafka-consumer-groups.sh $BS --delete --group $g >/dev/null 2>&1
done
for t in traffic-readings congestion-alerts; do
  $K/kafka-topics.sh $BS --delete --topic $t >/dev/null 2>&1
done
sleep 3
$K/kafka-topics.sh $BS --create --topic traffic-readings  --partitions 3 --replication-factor 1 \
   --config retention.ms=604800000
$K/kafka-topics.sh $BS --create --topic congestion-alerts --partitions 1 --replication-factor 1
$K/kafka-topics.sh $BS --list
$K/kafka-topics.sh $BS --describe --topic traffic-readings
$K/kafka-topics.sh $BS --describe --topic congestion-alerts
