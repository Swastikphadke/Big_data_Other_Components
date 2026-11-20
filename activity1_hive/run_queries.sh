#!/usr/bin/env bash
# Activity 1 - run every HiveQL analysis query through Beeline.
#   * human-readable table output  -> evidence/act1/queries/<query>.log
#   * machine-readable CSV results  -> activity1_hive/results/<query>.csv
# Run from the project root in Git Bash:   bash activity1_hive/run_queries.sh
set -euo pipefail
export MSYS_NO_PATHCONV=1            # stop Git Bash rewriting /opt/... paths
JDBC='jdbc:hive2://localhost:10000/'
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGDIR="$ROOT/evidence/act1/queries"; CSVDIR="$ROOT/activity1_hive/results"
mkdir -p "$LOGDIR" "$CSVDIR"
NOISE='SLF4J|Failed to create directory|No such file or directory$|^INFO  :|^WARN  :'

for f in "$ROOT"/activity1_hive/hql/queries/q*.hql; do
  name=$(basename "$f" .hql)
  echo ">> $name"
  {
    echo "### $(date '+%Y-%m-%d %H:%M:%S %Z') | beeline -u $JDBC -f /opt/assignment/hql/queries/$name.hql"
    docker exec hive4 beeline -u "$JDBC" -f "/opt/assignment/hql/queries/$name.hql" 2>&1 \
      | grep -vE "$NOISE" | sed 's/\x1b\[[0-9;]*[A-Za-z]//g'
  } > "$LOGDIR/$name.log"
  # CSV copy of the result set (skip EXPLAIN output)
  if [[ $name != *explain* ]]; then
    docker exec hive4 beeline -u "$JDBC" --silent=true --showHeader=true \
      --outputformat=csv2 -f "/opt/assignment/hql/queries/$name.hql" 2>/dev/null \
      | grep -vE "$NOISE|^$" > "$CSVDIR/$name.csv"
  fi
done
echo "Done. Logs: $LOGDIR   CSVs: $CSVDIR"
