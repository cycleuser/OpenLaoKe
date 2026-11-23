#!/bin/bash
# Run the single-round capability probe three times so each question's answer
# stability can be checked manually. Writes three separate result files.
set -e
BENCH=/Users/fred/Documents/GitHub/cycleuser/OpenLaoKe/bench
PY=/Users/fred/miniconda3/envs/dev/bin/python
for i in 1 2 3; do
  "$PY" "$BENCH/capability_probe2.py" \
    --target spark=http://127.0.0.1:8093/v1:spark-1.7b-q4 \
    --target lfm3=http://127.0.0.1:8088/v1:lfm3-1.7b-q4 \
    --max-tokens 1024 \
    --json "$BENCH/results/cap3-$i.json" > "$BENCH/results/cap3-$i.log" 2>&1
  echo "round $i done"
done
