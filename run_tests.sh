#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <test_case>"
    echo "Example: $0 console/test_console_monitor.py"
    exit 1
fi

# Remove "tests/" prefix from the test case path if present
TEST_CASE=$(echo "$1" | sed 's|^tests/||' | sed 's|^\./tests/||')

docker exec --user cliffchen -ti sonic-mgmt-cliffchen bash -c \
    "cd /home/cliffchen/sonic-mgmt-int/tests && ./run_tests.sh \
    -c $TEST_CASE \
    -a False \
    -e --skip_sanity \
    -e --disable_loganalyzer \
    -e '--neighbor_type=sonic' \
    -e '--disable_memory_utilization' \
    -f ../ansible/testbed.yaml \
    -i ../ansible/bjw3,../ansible/veos \
    -m individual \
    -n testbed-bjw3-can-mc0-720dt-9 \
    -O \
    -r \
    -t any,m0,mx,m1,t0,t1 \
    -u"
