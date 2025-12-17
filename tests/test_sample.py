# Helper Functions
import pytest
from tests.common.devices.fanout import FanoutHost
from tests.common.devices.sonic import SonicHost

pytestmark = [
    pytest.mark.topology('any')
]

# "device_serial_link": {
#     "bjw3-can-720dt-9": {
#         "1": {
#             "peerdevice": "bjw3-can-720dt-leaf-27",
#             "peerport": "1",
#             "baud_rate": "9600",
#             "flow_control": "0"
#         },


def test_set_loopback(duthosts, fanouthosts, conn_graph_facts):

    breakpoint()
    
    dut: SonicHost = duthosts[0]
    dut_name = dut.hostname

    fanout: FanoutHost = fanouthosts["bjw3-can-720dt-leaf-27"]

    # setup port loopback on fanout switch
    # fanout.set_loopback(1)
    fanout.host.shell("sudo socat -d -d FILE:/dev/C0-1,raw,echo=0,nonblock,b9600,cs8,parenb=0,cstopb=0,ixon=0,ixoff=0,crtscts=0 EXEC:'/bin/cat' & echo $!")

    dut.host.shell("echo 'Configuring DUT for loopback test'")

    # verify port loopback status on dut
    # dut connect to console line 1
    # dut send packet to console line 1
    # assert packet received on console line 1

def test_console_loopback(duthosts, fanouthosts):
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


def test_set_loopback(duthosts, fanouthosts, conn_graph_facts):
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