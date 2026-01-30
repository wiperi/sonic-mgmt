    # -c platform_tests/link_flap/test_link_flap.py \


cd /home/cliffchen/sonic-mgmt-int/tests

./run_tests.sh \
    -c console/test_get_nb.py \
    -a False \
    -e --skip_sanity \
    -e --disable_loganalyzer \
    -e "--neighbor_type=sonic" \
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


# smoke test debug
# python3 -m pytest test_pretest.py      --inventory=../ansible/veos,../ansible/bjw2 --host-pattern=all --testbed=testbed-bjw2-can-t1-8102-5     --testbed_file=../ansible/testbed.yaml --log-cli-level=warning --log-file-level=debug     --kube_master=unset --showlocals --assert=plain --show-capture=no -rav     --ignore=ptftests --ignore=acstests --ignore=saitests --ignore=scripts --ignore=k8s --ignore=sai_qualify      --log-file='logs/test_pretest|||testbed-bjw2-can-t1-8102-5.log' --junit-xml='logs/test_pretest|||testbed-bjw2-can-t1-8102-5.xml'  --topology t1,any --py_saithrift_url=http://10.150.22.222/pipelines/Networking-acs-buildimage-Official/broadcom/internal/latest/target/debs/bookworm/python-saithrift_0.9.4_amd64.deb --deep_clean --sad_case_list=sad_bgp,sad_lag_member,sad_lag,sad_vlan_port,sad_inboot --allow_recover

# bjw-can-7250-1 test
# python3 -m pytest test_pretest.py      --inventory=../ansible/veos,../ansible/bjw --host-pattern=all --testbed=bjw-can-7250-1     --testbed_file=../ansible/testbed.yaml --log-cli-level=warning --log-file-level=debug     --kube_master=unset --showlocals --assert=plain --show-capture=no -rav     --ignore=ptftests --ignore=acstests --ignore=saitests --ignore=scripts --ignore=k8s --ignore=sai_qualify      --log-file='logs/test_pretest|||bjw-can-7250-1.log' --junit-xml='logs/test_pretest|||bjw-can-7250-1.xml'  --topology t1,any --py_saithrift_url=http://10.150.22.222/pipelines/Networking-acs-buildimage-Official/broadcom/internal/latest/target/debs/bookworm/python-saithrift_0.9.4_amd64.deb --deep_clean --sad_case_list=sad_bgp,sad_lag_member,sad_lag,sad_vlan_port,sad_inboot --allow_recover
