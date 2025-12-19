    # -c platform_tests/link_flap/test_link_flap.py \


cd /home/cliffchen/sonic-mgmt-int/tests

./run_tests.sh \
    -c test_sample.py \
    -a False \
    -e --skip_sanity \
    -e --disable_loganalyzer \
    -f ../ansible/testbed.yaml \
    -i ../ansible/bjw3,../ansible/veos \
    -m individual \
    -n testbed-bjw3-can-mc0-720dt-9 \
    -O \
    -r \
    -t any,m0,mx,m1,t0,t1 \
    -u

# ./run_tests.sh \
#     -c telemetry/test_telemetry_poll.py \
#     -a False \
#     -e --skip_sanity \
#     -e --disable_loganalyzer \
#     -f ../ansible/vtestbed.yaml \
#     -i ../ansible/bjw2,../ansible/veos \
#     -m individual \
#     -n testbed-vms-kvm-t1-lag \
#     -O \
#     -r \
#     -t any,m0,mx,m1,t0,t1 \
#     -u

# ./run_tests.sh \
#     -c bgp/test_bgp_fact.py \
#     -e --skip_sanity \
#     -e --disable_loganalyzer \
#     -f ../ansible/testbed.yaml \
#     -i ../ansible/bjw,../ansible/veos \
#     -m individual \
#     -n <testbed-name> \
#     -o \
#     -O \
#     -t any,mx \
#     -u