# Helper Functions
import logging
from re import S
import pytest
from tests.common.devices.fanout import FanoutHost
from tests.common.devices.sonic import SonicHost

pytestmark = [
    pytest.mark.topology('any')
]

logger = logging.getLogger(__name__)

# "device_serial_link": {
#     "bjw3-can-720dt-9": {
#         "1": {
#             "peerdevice": "bjw3-can-720dt-leaf-27",
#             "peerport": "1",
#             "baud_rate": "9600",
#             "flow_control": "0"
#         },


def tt_test_set_loopback(duthosts, fanouthosts, conn_graph_facts):

    
    dut: SonicHost = duthosts[0]

    fanout: SonicHost = fanouthosts["bjw3-can-720dt-leaf-27"].host


    result = fanout.set_loopback(1)

    breakpoint()

    assert result['status'] == 'success', f"Failed to set loopback on fanout: {result.get('message', '')}"

    dut.shell("cat /dev/C0-1 > /tmp/serial_output.txt &", module_ignore_errors=True)

    dut.shell("printf 'hello world' > /dev/C0-1", module_ignore_errors=True)

    result = dut.shell("cat /tmp/serial_output.txt", module_ignore_errors=True)

    assert "hello world" in result['stdout'], f"Expected 'hello world' in serial output, got: {result['stdout']}"

    fanout.shell("sudo pkill socat", module_ignore_errors=True)

def test_set_loopback_v2(duthosts, fanouthosts, conn_graph_facts):
    dut_host: SonicHost = duthosts[0]

    # 找出console fanout
    console_fanouts: list[FanoutHost] = [fanout for fanout in fanouthosts.values() if fanout.host.is_console_switch]
    
    assert len(console_fanouts) > 0, "No console fanout found in testbed"

    # 对于每个console fanout
    for console_fanout in console_fanouts:

        console_fanout_host = console_fanout.host

        if type(console_fanout_host) is not SonicHost:
            raise Exception(f'This fanout host, {console_fanout_host} should be SonicHost, but got {type(console_fanout_host)}')

        fanout_side_loopback_ports = [(fanout_port, mapping.dut_port, mapping.baud_rate) for fanout_port, mapping in console_fanout.serial_port_map.items() if mapping is not None and mapping.dut_name == dut_host.hostname]

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
                f'stty -F /dev/C0-{dut_port} {baud_rate} raw -echo cs8 -parenb -cstopb; '
                f'(timeout 3 cat /dev/C0-{dut_port} > "$TEST_FILE" 2>/dev/null < /dev/null &); '
                f'sleep 0.5; '
                f'echo "$TEST_DATA" > /dev/C0-{dut_port}; '
                f'sleep 1.5; '
                f'grep -Fq "$TEST_DATA" "$TEST_FILE" && echo "success" || echo "failed"; '
                f'rm -f "$TEST_FILE"'
            )
            
            result = dut_host.shell(test_cmd, module_ignore_errors=True)
            if 'success' not in result['stdout']:
                failed_ports.append((dut_port, fanout_port))
        
        # fanout侧关闭所有loopback
        # call SonicHost::unset_loopback(self, port: int)
        for fanout_port, dut_port, baud_rate in fanout_side_loopback_ports:
            console_fanout_host.unset_loopback(fanout_port)
        
        # 检查测试结果
        assert len(failed_ports) == 0, \
            f"Loopback test failed on ports: {failed_ports}"
    


def tt_test_console_loopback_V0(duthosts, fanouthosts):
    dut = duthosts[0]
    
    # 1. 在后台启动读取进程
    dut.host.shell("timeout 10 cat /dev/C0-1 > /tmp/serial_output.txt &")
    
    # 2. 给设备一点时间准备
    import time
    time.sleep(1)
    
    # 3. 写入测试数据
    test_message = "hello world"
    dut.host.shell(f"echo '{test_message}' > /dev/C0-1")
    
    # 4. 等待数据传输
    time.sleep(2)
    
    # 5. 读取接收到的数据
    result = dut.host.shell("cat /tmp/serial_output.txt")
    received = result['stdout'].strip()
    
    # 6. 验证
    assert test_message in received, f"Expected '{test_message}', got '{received}'"
    
    # 7. 清理
    dut.host.shell("pkill -f 'cat /dev/C0-1'", module_ignore_errors=True)
    dut.host.shell("rm -f /tmp/serial_output.txt")


def tt_test_set_loopback_V4(duthosts, fanouthosts, conn_graph_facts):
    dut = duthosts[0]
    fanout = fanouthosts['bjw3-can-720dt-leaf-27']
    
    # 在 fanout 上启动 loopback (socat)
    fanout.host.shell(
        "sudo nohup socat -d -d "
        "FILE:/dev/C0-1,raw,echo=0,nonblock,b9600 "
        "EXEC:'/bin/cat' "
        "> /tmp/loopback_1.log 2>&1 & echo $! > /tmp/loopback_1.pid"
    )
    
    try:
        # 在 DUT 上启动后台读取
        dut.host.shell("timeout 10 cat /dev/console > /tmp/console_output.txt &")
        time.sleep(1)
        
        # 写入测试数据
        test_data = "TEST_LOOPBACK_DATA"
        dut.host.shell(f"echo '{test_data}' > /dev/console")
        time.sleep(2)
        
        # 验证收到数据
        result = dut.host.shell("cat /tmp/console_output.txt")
        assert test_data in result['stdout']
        
    finally:
        # 清理 fanout loopback
        fanout.host.shell("sudo kill $(cat /tmp/loopback_1.pid 2>/dev/null) 2>/dev/null", 
                         module_ignore_errors=True)
        fanout.host.shell("sudo rm -f /tmp/loopback_1.pid /tmp/loopback_1.log")
        
        # 清理 DUT
        dut.host.shell("pkill -f 'cat /dev/console'", module_ignore_errors=True)
        dut.host.shell("rm -f /tmp/console_output.txt")