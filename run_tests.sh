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