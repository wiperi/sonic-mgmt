现成的fixture
    nbrhosts：获取所有neighbor hosts
    tbinfo：获取testbed信息
    duthosts：获取所有dut hosts
    vmhost: 获取can_server_9的host对象
    fanouthosts: 获取所有fanout hosts

自定义的fixture
    serial_fanouts: 获取serial fanout列表

    每个测试开始，确保dut上dce servcie正常运行

    每个测试结束，clear所有console link；关闭所有创建的桥接


helper
    get_serial_fanout(link_id): 看link_id连接在哪个fanout上，并返回对应的fanout host对象

    get_console_line_statuses(): 从cli获取所有配置的console link状态

    build_bridge(link_id)，将dut的serial port桥接到neighbor device的pty上

        首先，在neighbor devic上用socat建立一个 bridge （TCP listener port 8000 <-> PTY：/dev/ttyV0）

        然后，在serial fanout上，使用socat连接dut的serial port到neighbor 的 TCP 端口上

    build_console_bridge(duthost, fanouthost, vmhost, nbrhost, link_id)
        加入link_id = 2, 例子：

        1. 根据neighbor的名字，找到neighbor暴露给vm的port
            sudo virsh dumpxml VM04080 | grep -A5 serial
            读取到
                <serial type='tcp'>
                    <source mode='bind' host='127.0.0.1' service='7080' tls='no'/>
                    <protocol type='telnet'/>
                    <target type='isa-serial' port='0'>
                        <model name='isa-serial'/>
                    </target>
                    <alias name='serial0'/>
                </serial>
            获得port = 7080
        2. VM上
            socat -d -d -d TCP-LISTEN:17080,fork,reuseaddr TCP:127.0.0.1:7080 &
        3. fanout上
            socat -d -d -d FILE:/dev/C0-2,raw,echo=0 TCP:10.150.238.24:17080
        4. dut上
            connect line 2
            此时应该能看到login回显


test cases
    tset_oper_state_transition(...)

