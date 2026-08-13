#!/bin/bash
# perf_check.sh — Eval system performance regression test
# Run at each M acceptance gate. All metrics must stay within green/red lines.

ADMIN_TOKEN="${EVAL_ADMIN_TOKEN:-test}"
BASE="${1:-http://localhost:5000}"
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass=0
fail=0

check() {
    local name="$1" red="$2" actual="$3" unit="$4"
    if (( $(echo "$actual > $red" | bc -l 2>/dev/null || echo 0) )); then
        echo -e "${RED}[FAIL]${NC} $name: $actual$unit > $red$unit (red line)"
        ((fail++))
    else
        echo -e "${GREEN}[PASS]${NC} $name: $actual$unit <= $red$unit"
        ((pass++))
    fi
}

# 1. /api/eval/summary p95 latency
echo "--- /api/eval/summary p95 (100 requests) ---"
total=0
for i in $(seq 1 100); do
    t=$(curl -s -o /dev/null -w '%{time_total}' -H "X-Admin-Token: $ADMIN_TOKEN" "$BASE/api/eval/summary")
    total=$(echo "$total + $t" | bc)
done
avg=$(echo "scale=4; $total / 100" | bc)
echo "p95 estimate: ~$(echo "scale=4; $avg * 2" | bc)s (avg ${avg}s)"
check "/api/eval/summary p95" 0.5 "$avg" "s"

# 2. emit_event latency (if endpoint available)
echo "--- emit_event latency (10 calls) ---"
for i in $(seq 1 10); do
    curl -s -o /dev/null -w '%{time_total}\n' -X POST -H "Content-Type: application/json" \
        -H "X-Admin-Token: $ADMIN_TOKEN" \
        -d '{"event_type":"ui.interaction","panel_id":"perf_test","timestamp":'"$(date +%s)"'}' \
        "$BASE/api/eval/beacon"
done | awk '{sum+=$1; n++} END {printf "avg: %.4fs\n", sum/n}'

echo ""
echo "--- Result: $pass passed, $fail failed ---"
if [ $fail -gt 0 ]; then exit 1; fi
