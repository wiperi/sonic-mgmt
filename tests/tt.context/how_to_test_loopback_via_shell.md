在 fanout 侧搭建 loopback 后，在 DUT 上可以使用以下 shell 命令测试 console loopback 是否工作正常：

## 1. 基本的 echo + read 测试

```bash
# 假设 console port 对应的设备是 /dev/ttyS0

# 配置串口参数（波特率115200，raw模式）
stty -F /dev/ttyS0 115200 raw -echo

# 方法1：后台读取 + 写入测试
timeout 2 cat /dev/ttyS0 > /tmp/console_output &
sleep 0.5
echo "TEST_LOOPBACK_123" > /dev/ttyS0
sleep 1
cat /tmp/console_output
# 应该看到 "TEST_LOOPBACK_123"
```

## 2. 使用 dd 命令测试

```bash
# 写入测试数据
echo "LOOPBACK_TEST" | dd of=/dev/ttyS0 bs=1 2>/dev/null

# 读取回环数据
dd if=/dev/ttyS0 of=/tmp/loopback_result bs=1 count=14 iflag=nonblock 2>/dev/null
cat /tmp/loopback_result
```

## 3. 单行命令测试

```bash
# 后台读取，前台写入，查看结果
(timeout 2 cat /dev/ttyS0 > /tmp/test.out &) && sleep 0.5 && echo "HELLO" > /dev/ttyS0 && sleep 1 && cat /tmp/test.out
```

## 4. 使用 socat 在 DUT 侧测试（如果DUT上有socat）

```bash
# 发送并接收
echo "TEST123" | socat - /dev/ttyS0,raw,echo=0,b115200,readbytes=7
```

## 5. 循环测试稳定性

```bash
#!/bin/bash
# 测试脚本
DEVICE=/dev/ttyS0
stty -F $DEVICE 115200 raw -echo

for i in {1..10}; do
    TEST_STRING="TEST_${i}_$(date +%s)"
    
    # 后台读取
    timeout 2 cat $DEVICE > /tmp/loop_test_$i &
    READ_PID=$!
    
    sleep 0.3
    
    # 写入
    echo "$TEST_STRING" > $DEVICE
    
    sleep 0.8
    
    # 验证
    RESULT=$(cat /tmp/loop_test_$i)
    if [ "$RESULT" == "$TEST_STRING" ]; then
        echo "Test $i: PASS"
    else
        echo "Test $i: FAIL (Expected: $TEST_STRING, Got: $RESULT)"
    fi
    
    rm -f /tmp/loop_test_$i
done
```

## 6. 实时监控方式

```bash
# 终端1：持续读取
cat /dev/ttyS0

# 终端2：发送数据
echo "Hello World" > /dev/ttyS0
# 应该在终端1看到输出
```

## 7. 使用 expect（如果可用）

```bash
# 虽然是脚本，但是纯shell可调用
cat > /tmp/test_loopback.exp << 'EOF'
#!/usr/bin/expect
set timeout 5
spawn -open [open /dev/ttyS0 w+]
send "TEST_STRING\n"
expect "TEST_STRING"
puts "Loopback working!"
EOF

chmod +x /tmp/test_loopback.exp
/tmp/test_loopback.exp
```

## 8. 检查串口配置

```bash
# 查看当前串口配置
stty -F /dev/ttyS0 -a

# 验证设备存在且可访问
ls -l /dev/ttyS0
[ -c /dev/ttyS0 ] && echo "Device exists" || echo "Device not found"

# 检查权限
[ -r /dev/ttyS0 ] && [ -w /dev/ttyS0 ] && echo "R/W OK" || echo "Permission issue"
```

## 9. 性能测试

```bash
# 发送大量数据测试
dd if=/dev/urandom bs=1024 count=10 | tee >(sha256sum) | dd of=/dev/ttyS0 &
dd if=/dev/ttyS0 bs=1024 count=10 | sha256sum
# 比较两个SHA值是否一致
```

## 10. 最简单的一键测试

```bash
# 一行命令测试loopback
TEST_DATA="LOOPBACK_$(date +%s)"; (timeout 3 cat /dev/ttyS0 | grep -m1 "$TEST_DATA" &) && sleep 0.5 && echo "$TEST_DATA" > /dev/ttyS0 && sleep 1 && echo "Loopback test PASSED" || echo "Loopback test FAILED"
```

## 注意事项

1. **设备路径**：根据实际情况修改 ttyS0，可能是 `/dev/ttyUSB0` 或其他
2. **波特率**：确保与 fanout 侧 socat 配置一致（如 115200）
3. **延迟**：给足够的 sleep 时间让数据传输完成
4. **超时**：使用 `timeout` 命令防止 cat 永久阻塞
5. **权限**：可能需要 `sudo` 访问串口设备

## 推荐的完整测试函数

```bash
test_console_loopback() {
    local DEVICE=$1
    local TEST_STRING="LOOPBACK_TEST_$(date +%s%N)"
    
    # 配置串口
    stty -F $DEVICE 115200 raw -echo 2>/dev/null || return 1
    
    # 清空缓冲
    timeout 0.1 cat $DEVICE > /dev/null 2>&1
    
    # 启动读取
    timeout 3 cat $DEVICE > /tmp/loopback_result 2>/dev/null &
    local CAT_PID=$!
    
    # 等待cat启动
    sleep 0.3
    
    # 发送测试数据
    echo "$TEST_STRING" > $DEVICE
    
    # 等待接收
    sleep 1
    
    # 检查结果
    local RESULT=$(cat /tmp/loopback_result 2>/dev/null)
    rm -f /tmp/loopback_result
    
    if [[ "$RESULT" == "$TEST_STRING" ]]; then
        echo "✓ Loopback test PASSED"
        return 0
    else
        echo "✗ Loopback test FAILED"
        echo "  Expected: $TEST_STRING"
        echo "  Got: $RESULT"
        return 1
    fi
}

# 使用
test_console_loopback /dev/ttyS0
```