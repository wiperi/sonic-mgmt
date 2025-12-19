# Helper Functions
import logging
import pytest
from tests.common.devices.fanout import FanoutHost
from tests.common.devices.sonic import SonicHost

pytestmark = [pytest.mark.topology("any")]

logger = logging.getLogger(__name__)

# "device_serial_link": {
#     "bjw3-can-720dt-9": {
#         "1": {
#             "peerdevice": "bjw3-can-720dt-leaf-27",
#             "peerport": "1",
#             "baud_rate": "9600",
#             "flow_control": "0"
#         },


def test_bridge(duthosts, fanouthosts, conn_graph_facts):
    dut_host: SonicHost = duthosts[0]

    # 找出console fanout
    console_fanouts: list[FanoutHost] = [
        fanout for fanout in fanouthosts.values() if type(fanout.host) is SonicHost and fanout.host.is_console_switch
    ]

    assert len(console_fanouts) > 0, "No console fanout found in testbed"

    fanout_host = console_fanouts[0].host
    if type(fanout_host) is not SonicHost:
        raise Exception(
            f"This fanout host, {fanout_host} should be SonicHost, but got {type(fanout_host)}"
        )

    rc, messae = fanout_host.bridge('1', '2')

    breakpoint()

    assert rc == 0, f"Failed to bridge ports on fanout: {messae}"

    test_cmd = (
        f'TEST_DATA="DATE_$(date +%Y%m%d%H%M%S)"; '
        f'TEST_FILE="/tmp/test_{1-2}.out"; '
        f"stty -F /dev/C0-{1} {9600} raw -echo cs8 -parenb -cstopb; "
        f"stty -F /dev/C0-{2} {9600} raw -echo cs8 -parenb -cstopb; "
        f'(timeout 3 cat /dev/C0-{2} > "$TEST_FILE" 2>/dev/null < /dev/null &); '
        f"sleep 0.5; "
        f'echo "$TEST_DATA" > /dev/C0-{1}; '
        f"sleep 1.5; "
        f'grep -Fq "$TEST_DATA" "$TEST_FILE" && echo "success" || echo "failed"; '
        f'rm -f "$TEST_FILE"'
    )

    res = dut_host.shell(test_cmd, module_ignore_errors=True)

    fanout_host.cleanup_all_console_sessions()
    
    


def tt_test_set_loopback(duthosts, fanouthosts):
    dut_host: SonicHost = duthosts[0]

    # 找出console fanout
    console_fanouts: list[FanoutHost] = [
        fanout for fanout in fanouthosts.values() if type(fanout.host) is SonicHost and fanout.host.is_console_switch
    ]

    assert len(console_fanouts) > 0, "No console fanout found in testbed"

    # 对于每个console fanout
    for console_fanout in console_fanouts:

        console_fanout_host = console_fanout.host

        if type(console_fanout_host) is not SonicHost:
            raise Exception(
                f"This fanout host, {console_fanout_host} should be SonicHost, but got {type(console_fanout_host)}"
            )

        fanout_side_loopback_ports = [
            (fanout_port, mapping.dut_port, mapping.baud_rate)
            for fanout_port, mapping in console_fanout.serial_port_map.items()
            if mapping is not None and mapping.dut_name == dut_host.hostname
        ]

        # 找到与host的连接port, baud_rate, flow_control
        # 信息在 FanoutHost::host_to_fanout_serial_port_map
        for fanout_port, dut_port, baud_rate in fanout_side_loopback_ports:
            rc, message = console_fanout_host.set_loopback(fanout_port, baud_rate)
            assert rc == 0, f"Failed to set loopback on port {fanout_port}: {message}"

        # dut测试所有console port回声正常
        # command: TEST_DATA="DATE_$(date +%s)"; TEST_FILE="/tmp/s_test.out"; stty -F /dev/C0-1 9600 raw -echo cs8 -parenb -cstopb; (timeout 3 cat /dev/C0-1 > "$TEST_FILE" 2>/dev/null < /dev/null &); sleep 0.5; echo "$TEST_DATA" > /dev/C0-1; sleep 1.5; grep -Fq "$TEST_DATA" "$TEST_FILE" && echo "success" || echo "failed"; rm -f "$TEST_FILE"
        failed_ports = []

        for fanout_port, dut_port, baud_rate in fanout_side_loopback_ports:
            test_cmd = (
                f'TEST_DATA="DATE_$(date +%Y%m%d%H%M%S)"; '
                f'TEST_FILE="/tmp/test_{dut_port}.out"; '
                f"stty -F /dev/C0-{dut_port} {baud_rate} raw -echo cs8 -parenb -cstopb; "
                f'(timeout 3 cat /dev/C0-{dut_port} > "$TEST_FILE" 2>/dev/null < /dev/null &); '
                f"sleep 0.5; "
                f'echo "$TEST_DATA" > /dev/C0-{dut_port}; '
                f"sleep 1.5; "
                f'grep -Fq "$TEST_DATA" "$TEST_FILE" && echo "success" || echo "failed"; '
                f'rm -f "$TEST_FILE"'
            )

            result = dut_host.shell(test_cmd, module_ignore_errors=True)
            if "success" not in result["stdout"]:
                failed_ports.append((dut_port, fanout_port))

        # fanout侧关闭所有loopback
        # call SonicHost::unset_loopback(self, port: int)
        for fanout_port, dut_port, baud_rate in fanout_side_loopback_ports:
            console_fanout_host.unset_loopback(fanout_port)

        # 检查测试结果
        assert len(failed_ports) == 0, f"Loopback test failed on ports: {failed_ports}"
