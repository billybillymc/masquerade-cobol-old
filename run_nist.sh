#!/bin/bash
cd /tmp/nist_batch
PASS=0
FAIL=0
RUN=0
for bin in /tmp/nist_NC*; do
    [ -x "$bin" ] || continue
    rm -f report.log
    timeout 5 "$bin" >/dev/null 2>&1
    if [ -s report.log ]; then
        RUN=$((RUN+1))
        p=$(grep -c ' PASS ' report.log)
        f=$(grep -c 'FAIL\*' report.log)
        PASS=$((PASS+p))
        FAIL=$((FAIL+f))
    fi
done
echo "NC: run=$RUN pass=$PASS fail=$FAIL"
