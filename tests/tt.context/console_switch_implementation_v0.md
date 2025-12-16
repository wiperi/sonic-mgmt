# SONiC Console Switch功能实现文档

## 1. 概述

本文档描述了在 `SonicHost` 类中集成 Console Switch 功能的实现方案。该功能允许 SONiC 设备作为 Console Server 使用，通过编程方式在 console leaf fanout 上建立串口的 loopback 和 bridge 连接。

## 2. 设计决策

### 2.1 集成方式

**决策**：直接在 `SonicHost` 类中集成，而非创建子类

**理由**：
- Console switch 功能是 SONiC 设备的一种可选运行模式
- 通过构造函数参数控制功能开关，保持向后兼容
- 避免创建过多的子类层次
- 测试框架可以根据 testbed 配置灵活启用/禁用该功能

### 2.2 核心原则

1. **所有操作在 fanout 上执行**：不在 DUT 上运行任何 bridge/loopback 进程
2. **使用 socat 实现**：利用 socat 的灵活性和可靠性
3. **幂等性**：重复调用相同参数应该是安全的
4. **资源清理**：提供显式的清理方法和自动清理机制
5. **错误处理**：明确区分配置错误、网络错误和 DUT 错误

## 3. 架构设计

### 3.1 组件关系

```
┌─────────────────────────────────────────────────────────┐
│                     Test Case                           │
│                  (tests/console/)                        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                 SonicHost Instance                       │
│            (is_console_switch=True)                      │
│  ┌────────────────────────────────────────────────────┐ │
│  │ set_loopback(port)                                 │ │
│  │ unset_loopback(port)                               │ │
│  │ bridge(port1, port2)                               │ │
│  │ unbridge(port1, port2)                             │ │
│  │ bridge_remote(port1, remote_host_console_port)     │ │
│  │ unbridge_remote(port1)                             │ │
│  └────────────────────────────────────────────────────┘ │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Console Leaf Fanout Host                    │
│            (from fanouthosts fixture)                    │
│  ┌────────────────────────────────────────────────────┐ │
│  │ socat processes                                    │ │
│  │ - /dev/C0-1 <-> PTY (loopback)                     │ │
│  │ - /dev/C0-2 <-> /dev/C0-3 (bridge)                 │ │
│  │ - /dev/C0-4 <-> TCP:remote:port (remote bridge)    │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 3.2 数据流

#### Loopback 模式
```
DUT Console Port → /dev/C0-X (fanout) → socat loopback → /dev/C0-X (fanout) → DUT Console Port
```

#### Bridge 模式
```
DUT Port1 → /dev/C0-X (fanout) ←─socat─→ /dev/C0-Y (fanout) → DUT Port2
```

#### Remote Bridge 模式
```
DUT Port1 → /dev/C0-X (fanout) ←─socat + TCP─→ Remote Virtual Serial Port
```

## 4. 实现细节

### 4.1 构造函数修改

```python
def __init__(self, ansible_adhoc, hostname,
             shell_user=None, shell_passwd=None,
             ssh_user=None, ssh_passwd=None,
             is_console_switch=False):
    # ... 现有初始化代码 ...
    
    # Console switch specific initialization
    self._is_console_switch = is_console_switch
    self._console_loopback_sessions = {}  # {port: pid}
    self._console_bridge_sessions = {}    # {(port1, port2): pid}
    self._console_remote_sessions = {}    # {port: pid}
```

**新增参数**：
- `is_console_switch` (bool): 默认 `False`，表示该设备是否作为 console switch 运行

**新增实例变量**：
- `_is_console_switch`: 存储 console switch 模式状态
- `_console_loopback_sessions`: 跟踪 loopback 会话的 PID
- `_console_bridge_sessions`: 跟踪 bridge 会话的 PID
- `_console_remote_sessions`: 跟踪 remote bridge 会话的 PID

### 4.2 辅助方法

#### 4.2.1 获取 Fanout 设备路径

```python
def _get_console_fanout_device(self, port, fanouthosts, conn_graph_facts):
    """
    获取指定 console port 在 fanout 上的设备路径
    
    Args:
        port: Console line 编号或标识
        fanouthosts: fanout hosts fixture
        conn_graph_facts: connection graph facts
        
    Returns:
        tuple: (fanout_host, device_path)
        例如: (fanout_host_obj, "/dev/C0-1")
        
    Raises:
        ValueError: 如果 port 未在 conn_graph_facts 中映射
    """
    # 1. 从 conn_graph_facts 中查找该 port 对应的 fanout 和 fanout port
    # 2. 根据 fanout port 构建设备路径 (如 /dev/C0-{port})
    # 3. 返回 fanout host 对象和设备路径
```

#### 4.2.2 清理已有会话

```python
def _cleanup_console_session(self, fanout_host, port_identifier):
    """
    清理指定端口上的已有 socat 会话
    
    Args:
        fanout_host: Fanout host 对象
        port_identifier: 端口标识符 (用于查找 PID 文件)
    """
    # 1. 查找 PID 文件 /tmp/console_{identifier}.pid
    # 2. 如果存在，读取 PID
    # 3. 检查进程是否存在
    # 4. 如果存在，发送 SIGTERM 杀死进程
    # 5. 删除 PID 文件
    # 6. 清理日志文件 (可选)
```

#### 4.2.3 验证 socat 可用性

```python
def _ensure_socat_available(self, fanout_host):
    """
    确保 fanout host 上安装了 socat
    
    Args:
        fanout_host: Fanout host 对象
        
    Returns:
        bool: True 如果 socat 可用
        
    Raises:
        RuntimeError: 如果 socat 不可用且无法安装
    """
    # 1. 检查 which socat
    # 2. 如果不存在，尝试安装 (apt-get install socat)
    # 3. 再次验证
```

### 4.3 核心方法实现

#### 4.3.1 set_loopback(port)

```python
def set_loopback(self, port, fanouthosts, conn_graph_facts):
    """
    为指定 console port 建立 loopback 连接
    
    在 console leaf fanout 上启动 socat 进程，实现数据回环：
    DUT 发送的数据会从同一端口收回
    
    Args:
        port: Console line 编号/标识
        fanouthosts: Fanout hosts fixture (from pytest)
        conn_graph_facts: Connection graph facts (from pytest)
        
    Returns:
        dict: {
            'status': 'success' or 'failed',
            'pid': socat 进程 PID,
            'device': fanout 设备路径,
            'message': 详细信息
        }
        
    Raises:
        ValueError: port 不在拓扑中
        RuntimeError: socat 启动失败
        
    Example:
        result = duthost.set_loopback(
            port=1,
            fanouthosts=fanouthosts,
            conn_graph_facts=conn_graph_facts
        )
    """
    if not self._is_console_switch:
        raise RuntimeError("This SonicHost is not configured as console switch")
    
    # 1. 获取 fanout host 和设备路径
    fanout_host, device_path = self._get_console_fanout_device(
        port, fanouthosts, conn_graph_facts
    )
    
    # 2. 确保 socat 可用
    self._ensure_socat_available(fanout_host)
    
    # 3. 清理已有的 loopback/bridge 会话
    self._cleanup_console_session(fanout_host, f"loopback_{port}")
    
    # 4. 构建 socat 命令
    # socat 使用 PTY + EXEC echo 实现回环
    # 或者使用两个 PTY 互相连接的方式
    socat_cmd = (
        f"nohup socat -d -d "
        f"{device_path},raw,echo=0,b115200 "
        f"PTY,link=/tmp/loopback_{port},raw,echo=0,b115200 "
        f"> /var/log/console_loopback_{port}.log 2>&1 & "
        f"echo $! > /tmp/console_loopback_{port}.pid"
    )
    
    # 5. 在 fanout 上执行命令
    result = fanout_host.shell(socat_cmd, module_ignore_errors=True)
    
    # 6. 验证启动成功
    # 读取 PID 文件并验证进程存在
    
    # 7. 记录会话信息
    # self._console_loopback_sessions[port] = pid
    
    # 8. 返回结果
```

**socat 命令解析**：
```bash
socat -d -d \
  /dev/C0-1,raw,echo=0,b115200 \
  PTY,link=/tmp/loopback_1,raw,echo=0,b115200
```
- `-d -d`: 双倍详细日志
- `/dev/C0-1,raw,echo=0,b115200`: 实际串口，raw模式，无回显，115200波特率
- `PTY,link=/tmp/loopback_1,raw,echo=0,b115200`: 创建伪终端，raw模式

**更简单的 loopback 方案**：
```bash
# 使用 EXEC 方式实现真正的回环
socat -d -d \
  /dev/C0-1,raw,echo=0,b115200 \
  EXEC:'/bin/cat'
```
这样所有从 `/dev/C0-1` 发送的数据都会被 cat 读取并立即写回。

#### 4.3.2 unset_loopback(port)

```python
def unset_loopback(self, port, fanouthosts, conn_graph_facts):
    """
    移除指定 port 的 loopback 配置
    
    Args:
        port: Console line 编号/标识
        fanouthosts: Fanout hosts fixture
        conn_graph_facts: Connection graph facts
        
    Returns:
        dict: {'status': 'success/failed', 'message': '...'}
    """
    if not self._is_console_switch:
        raise RuntimeError("This SonicHost is not configured as console switch")
    
    # 1. 获取 fanout host
    fanout_host, _ = self._get_console_fanout_device(
        port, fanouthosts, conn_graph_facts
    )
    
    # 2. 清理会话
    self._cleanup_console_session(fanout_host, f"loopback_{port}")
    
    # 3. 从跟踪字典中移除
    if port in self._console_loopback_sessions:
        del self._console_loopback_sessions[port]
    
    # 4. 返回结果
```

#### 4.3.3 bridge(port1, port2)

```python
def bridge(self, port1, port2, fanouthosts, conn_graph_facts):
    """
    在两个 console port 之间建立双向桥接
    
    Args:
        port1: 第一个 console line
        port2: 第二个 console line
        fanouthosts: Fanout hosts fixture
        conn_graph_facts: Connection graph facts
        
    Returns:
        dict: {
            'status': 'success/failed',
            'pid': socat PID,
            'devices': (device1, device2),
            'message': '...'
        }
        
    Raises:
        ValueError: 如果两个 port 不在同一个 fanout 上
        RuntimeError: socat 启动失败
        
    Example:
        result = duthost.bridge(
            port1=1,
            port2=2,
            fanouthosts=fanouthosts,
            conn_graph_facts=conn_graph_facts
        )
    """
    if not self._is_console_switch:
        raise RuntimeError("This SonicHost is not configured as console switch")
    
    # 1. 获取两个 port 的 fanout 和设备路径
    fanout_host1, device_path1 = self._get_console_fanout_device(
        port1, fanouthosts, conn_graph_facts
    )
    fanout_host2, device_path2 = self._get_console_fanout_device(
        port2, fanouthosts, conn_graph_facts
    )
    
    # 2. 验证两个 port 在同一 fanout (当前版本限制)
    if fanout_host1.hostname != fanout_host2.hostname:
        raise ValueError(
            f"Ports {port1} and {port2} are on different fanouts. "
            f"Cross-fanout bridging is not supported in this version."
        )
    
    # 3. 确保 socat 可用
    self._ensure_socat_available(fanout_host1)
    
    # 4. 清理两个端口上的已有会话
    self._cleanup_console_session(fanout_host1, f"loopback_{port1}")
    self._cleanup_console_session(fanout_host1, f"loopback_{port2}")
    self._cleanup_console_session(fanout_host1, f"bridge_{port1}_{port2}")
    
    # 5. 构建 socat 命令
    # socat 直接连接两个串口设备
    socat_cmd = (
        f"nohup socat -d -d "
        f"{device_path1},raw,echo=0,b115200 "
        f"{device_path2},raw,echo=0,b115200 "
        f"> /var/log/console_bridge_{port1}_{port2}.log 2>&1 & "
        f"echo $! > /tmp/console_bridge_{port1}_{port2}.pid"
    )
    
    # 6. 执行命令
    result = fanout_host1.shell(socat_cmd, module_ignore_errors=True)
    
    # 7. 验证并记录会话
    # self._console_bridge_sessions[(port1, port2)] = pid
    
    # 8. 返回结果
```

**socat 命令解析**：
```bash
socat -d -d \
  /dev/C0-1,raw,echo=0,b115200 \
  /dev/C0-2,raw,echo=0,b115200
```
这会在两个串口之间建立双向数据传输通道。

#### 4.3.4 unbridge(port1, port2)

```python
def unbridge(self, port1, port2, fanouthosts, conn_graph_facts):
    """
    移除两个 port 之间的 bridge 连接
    
    Args:
        port1: 第一个 console line
        port2: 第二个 console line
        fanouthosts: Fanout hosts fixture
        conn_graph_facts: Connection graph facts
        
    Returns:
        dict: {'status': 'success/failed', 'message': '...'}
    """
    if not self._is_console_switch:
        raise RuntimeError("This SonicHost is not configured as console switch")
    
    # 1. 获取 fanout host
    fanout_host, _ = self._get_console_fanout_device(
        port1, fanouthosts, conn_graph_facts
    )
    
    # 2. 清理会话 (支持双向查找)
    self._cleanup_console_session(fanout_host, f"bridge_{port1}_{port2}")
    self._cleanup_console_session(fanout_host, f"bridge_{port2}_{port1}")
    
    # 3. 从跟踪字典中移除
    if (port1, port2) in self._console_bridge_sessions:
        del self._console_bridge_sessions[(port1, port2)]
    if (port2, port1) in self._console_bridge_sessions:
        del self._console_bridge_sessions[(port2, port1)]
    
    # 4. 返回结果
```

#### 4.3.5 bridge_remote(port1, remote_host_console_port)

```python
def bridge_remote(self, port, remote_host, remote_port, 
                  fanouthosts, conn_graph_facts):
    """
    将本地 console port 与远端虚拟串口桥接
    
    Args:
        port: 本地 console line
        remote_host: 远端主机地址 (IP 或 hostname)
        remote_port: 远端 TCP 端口号
        fanouthosts: Fanout hosts fixture
        conn_graph_facts: Connection graph facts
        
    Returns:
        dict: {
            'status': 'success/failed',
            'pid': socat PID,
            'local_device': 本地设备路径,
            'remote_endpoint': 'remote_host:remote_port',
            'message': '...'
        }
        
    Example:
        result = duthost.bridge_remote(
            port=1,
            remote_host="10.0.0.100",
            remote_port=20001,
            fanouthosts=fanouthosts,
            conn_graph_facts=conn_graph_facts
        )
    """
    if not self._is_console_switch:
        raise RuntimeError("This SonicHost is not configured as console switch")
    
    # 1. 获取本地 fanout 和设备路径
    fanout_host, device_path = self._get_console_fanout_device(
        port, fanouthosts, conn_graph_facts
    )
    
    # 2. 确保 socat 可用
    self._ensure_socat_available(fanout_host)
    
    # 3. 清理已有会话
    self._cleanup_console_session(fanout_host, f"loopback_{port}")
    self._cleanup_console_session(fanout_host, f"remote_{port}")
    
    # 4. 构建 socat 命令
    # 将本地串口连接到远端 TCP 端口
    socat_cmd = (
        f"nohup socat -d -d "
        f"{device_path},raw,echo=0,b115200 "
        f"TCP:{remote_host}:{remote_port} "
        f"> /var/log/console_remote_{port}.log 2>&1 & "
        f"echo $! > /tmp/console_remote_{port}.pid"
    )
    
    # 5. 执行命令
    result = fanout_host.shell(socat_cmd, module_ignore_errors=True)
    
    # 6. 验证连接
    # 可以尝试检查 socat 进程状态和日志
    
    # 7. 记录会话
    # self._console_remote_sessions[port] = pid
    
    # 8. 返回结果
```

**socat 命令解析**：
```bash
socat -d -d \
  /dev/C0-1,raw,echo=0,b115200 \
  TCP:10.0.0.100:20001
```
将本地串口设备连接到远程 TCP 端口。

#### 4.3.6 unbridge_remote(port)

```python
def unbridge_remote(self, port, fanouthosts, conn_graph_facts):
    """
    移除 port 的 remote bridge 配置
    
    Args:
        port: Console line
        fanouthosts: Fanout hosts fixture
        conn_graph_facts: Connection graph facts
        
    Returns:
        dict: {'status': 'success/failed', 'message': '...'}
    """
    if not self._is_console_switch:
        raise RuntimeError("This SonicHost is not configured as console switch")
    
    # 1. 获取 fanout host
    fanout_host, _ = self._get_console_fanout_device(
        port, fanouthosts, conn_graph_facts
    )
    
    # 2. 清理会话
    self._cleanup_console_session(fanout_host, f"remote_{port}")
    
    # 3. 从跟踪字典中移除
    if port in self._console_remote_sessions:
        del self._console_remote_sessions[port]
    
    # 4. 返回结果
```

#### 4.3.7 清理所有 Console 会话

```python
def cleanup_all_console_sessions(self, fanouthosts, conn_graph_facts):
    """
    清理所有 console switch 相关的会话
    
    用于测试清理或异常恢复
    
    Args:
        fanouthosts: Fanout hosts fixture
        conn_graph_facts: Connection graph facts
        
    Returns:
        dict: {
            'loopback_cleaned': [...],
            'bridge_cleaned': [...],
            'remote_cleaned': [...]
        }
    """
    if not self._is_console_switch:
        return {'message': 'Not a console switch'}
    
    result = {
        'loopback_cleaned': [],
        'bridge_cleaned': [],
        'remote_cleaned': []
    }
    
    # 清理所有 loopback 会话
    for port in list(self._console_loopback_sessions.keys()):
        try:
            self.unset_loopback(port, fanouthosts, conn_graph_facts)
            result['loopback_cleaned'].append(port)
        except Exception as e:
            logging.warning(f"Failed to clean loopback {port}: {e}")
    
    # 清理所有 bridge 会话
    for (port1, port2) in list(self._console_bridge_sessions.keys()):
        try:
            self.unbridge(port1, port2, fanouthosts, conn_graph_facts)
            result['bridge_cleaned'].append((port1, port2))
        except Exception as e:
            logging.warning(f"Failed to clean bridge {port1}-{port2}: {e}")
    
    # 清理所有 remote bridge 会话
    for port in list(self._console_remote_sessions.keys()):
        try:
            self.unbridge_remote(port, fanouthosts, conn_graph_facts)
            result['remote_cleaned'].append(port)
        except Exception as e:
            logging.warning(f"Failed to clean remote bridge {port}: {e}")
    
    return result
```

## 5. socat 命令详解

### 5.1 Loopback 实现方案对比

#### 方案 A: PTY + cat
```bash
socat /dev/C0-1,raw,echo=0,b115200 EXEC:'/bin/cat'
```
**优点**：简单、真正的回环
**缺点**：cat 可能会缓冲数据

#### 方案 B: 双 PTY 交叉连接
```bash
socat /dev/C0-1,raw,echo=0,b115200 PTY,link=/tmp/loop1,raw,echo=0 &
PID1=$!
socat PTY,link=/tmp/loop2,raw,echo=0 /tmp/loop1,raw,echo=0 &
PID2=$!
```
**优点**：更灵活，可以插入中间层
**缺点**：复杂，需要管理多个进程

#### 推荐方案 C: PIPE
```bash
socat /dev/C0-1,raw,echo=0,b115200 PIPE:/tmp/loopback_pipe_1
```
**优点**：系统开销小，性能好
**缺点**：需要管理 PIPE 文件

### 5.2 串口参数说明

- `raw`: 原始模式，不做字符转换
- `echo=0`: 禁用回显
- `b115200`: 波特率 115200（常用值：9600, 19200, 38400, 57600, 115200）
- `cs8`: 8位数据位（默认）
- `parenb=0`: 无奇偶校验（默认）
- `cstopb=0`: 1位停止位（默认）

### 5.3 调试参数

- `-d`: 输出错误信息
- `-d -d`: 输出详细信息
- `-d -d -d`: 输出非常详细的信息（包括数据传输）
- `-d -d -d -d`: 输出所有细节（用于深度调试）

## 6. 错误处理策略

### 6.1 错误分类

| 错误类型 | 处理方式 | 测试行为 |
|---------|---------|---------|
| Port 未在拓扑中 | `ValueError` | `pytest.skip` |
| Fanout 不可达 | `RuntimeError` | 测试失败，记录 fanout 问题 |
| socat 未安装 | 自动安装 | 如安装失败则 skip |
| socat 启动失败 | `RuntimeError` | 测试失败，输出详细日志 |
| 远端 TCP 连接失败 | `RuntimeError` | 测试失败，检查远端服务 |
| 串口设备不存在 | `ValueError` | `pytest.skip` 或失败 |
| 端口被占用 | 自动清理旧会话 | 重试 |

### 6.2 错误信息要求

每个错误都应该包含：
1. 错误类型
2. 涉及的端口/设备
3. 底层命令输出
4. 建议的排查步骤

示例：
```python
raise RuntimeError(
    f"Failed to start loopback on port {port}. "
    f"Device: {device_path}, "
    f"Command: {socat_cmd}, "
    f"Output: {result['stderr']}, "
    f"Suggestion: Check if device exists and socat is working"
)
```

## 7. 日志和可观测性

### 7.1 日志文件

在 fanout 上创建以下日志文件：
- `/var/log/console_loopback_{port}.log`: loopback 会话日志
- `/var/log/console_bridge_{port1}_{port2}.log`: bridge 会话日志
- `/var/log/console_remote_{port}.log`: remote bridge 会话日志

### 7.2 PID 文件

在 fanout 上创建以下 PID 文件：
- `/tmp/console_loopback_{port}.pid`
- `/tmp/console_bridge_{port1}_{port2}.pid`
- `/tmp/console_remote_{port}.pid`

### 7.3 测试日志

在测试代码中记录：
```python
logging.info(f"Setting up loopback on port {port}")
logging.info(f"Fanout: {fanout_host.hostname}, Device: {device_path}")
logging.info(f"Socat command: {socat_cmd}")
logging.info(f"Socat PID: {pid}")
```

失败时：
```python
logging.error(f"Failed to setup loopback on port {port}")
logging.error(f"Fanout: {fanout_host.hostname}")
logging.error(f"Stderr: {result['stderr']}")
logging.error(f"Check fanout log: /var/log/console_loopback_{port}.log")
```

## 8. 测试用例集成

### 8.1 Fixture 定义

在 `tests/console/conftest.py` 中：

```python
import pytest

@pytest.fixture(scope="function")
def console_switch_session(duthosts, enum_rand_one_per_hwsku_frontend_hostname,
                           fanouthosts, conn_graph_facts):
    """
    提供一个自动清理的 console switch 会话管理器
    """
    duthost = duthosts[enum_rand_one_per_hwsku_frontend_hostname]
    
    # 确保 DUT 配置为 console switch
    if not duthost._is_console_switch:
        pytest.skip("DUT is not configured as console switch")
    
    # 会话跟踪
    sessions = {
        'loopbacks': [],
        'bridges': [],
        'remotes': []
    }
    
    yield {
        'duthost': duthost,
        'fanouthosts': fanouthosts,
        'conn_graph_facts': conn_graph_facts,
        'sessions': sessions
    }
    
    # 自动清理
    logging.info("Cleaning up console switch sessions...")
    duthost.cleanup_all_console_sessions(fanouthosts, conn_graph_facts)
```

### 8.2 测试用例示例

```python
def test_console_loopback_basic(console_switch_session):
    """
    测试基本的 loopback 功能
    """
    session = console_switch_session
    duthost = session['duthost']
    
    # 设置 loopback
    result = duthost.set_loopback(
        port=1,
        fanouthosts=session['fanouthosts'],
        conn_graph_facts=session['conn_graph_facts']
    )
    
    assert result['status'] == 'success'
    session['sessions']['loopbacks'].append(1)
    
    # 在 DUT 上发送数据
    # ...验证数据回环...
    
    # 清理会在 fixture teardown 中自动完成


def test_console_bridge_bidirectional(console_switch_session):
    """
    测试两个端口之间的双向通信
    """
    session = console_switch_session
    duthost = session['duthost']
    
    # 设置 bridge
    result = duthost.bridge(
        port1=1,
        port2=2,
        fanouthosts=session['fanouthosts'],
        conn_graph_facts=session['conn_graph_facts']
    )
    
    assert result['status'] == 'success'
    session['sessions']['bridges'].append((1, 2))
    
    # 验证双向通信
    # ...
```

## 9. 配置集成

### 9.1 Testbed 配置

在 testbed YAML 中标识 console switch：

```yaml
# testbed.yaml
- conf-name: c0-testbed-01
  duts:
    - hostname: console-switch-01
      console_switch: true  # 新增字段
      # ... 其他配置 ...
```

### 9.2 初始化时读取配置

在测试框架中：

```python
# 在创建 SonicHost 实例时
def create_duthost(ansible_adhoc, hostname, testbed_config):
    is_console_switch = testbed_config.get('console_switch', False)
    
    return SonicHost(
        ansible_adhoc,
        hostname,
        is_console_switch=is_console_switch
    )
```

## 10. 性能和资源考虑

### 10.1 资源消耗

每个 socat 进程：
- 内存：约 1-2 MB
- CPU：空闲时接近 0%，数据传输时 <5%
- 文件描述符：2-4 个

在 fanout 上可以同时运行数十个 socat 进程而不影响性能。

### 10.2 并发限制

- 建议同一时刻不超过 32 个活跃 socat 会话
- 每个串口设备同一时刻只能有一个 socat 进程

### 10.3 超时设置

- socat 启动超时：5 秒
- TCP 连接超时：10 秒
- 进程清理超时：3 秒

## 11. 限制和已知问题

### 11.1 当前版本限制

1. **不支持跨 fanout bridge**：`port1` 和 `port2` 必须在同一个 fanout 上
2. **不支持硬件流控**：RTS/CTS、DTR/DSR 信号不透传
3. **固定波特率**：当前硬编码为 115200，未来可以参数化
4. **单 fanout 假设**：假设每个 DUT 的所有 console port 都在一个 fanout 上

### 11.2 未来改进方向

1. 支持可配置的串口参数（波特率、数据位、校验位等）
2. 支持跨 fanout 的 remote bridge
3. 提供会话监控和健康检查
4. 支持流控信号透传
5. 提供性能统计（吞吐量、延迟等）

## 12. 安全考虑

### 12.1 权限要求

- Fanout 上执行命令可能需要 sudo 权限（访问 `/dev/ttyUSB*`）
- 需要确保测试框架对 fanout 有足够的访问权限

### 12.2 资源隔离

- 使用唯一的 PID 文件名防止冲突
- 日志文件使用端口号区分
- 确保测试结束后清理所有资源

### 12.3 错误恢复

- 异常退出时通过 pytest fixture 自动清理
- 提供手动清理脚本用于紧急情况

## 13. 总结

本实现方案通过在 `SonicHost` 类中集成 console switch 功能，提供了一套完整的、基于 socat 的串口 loopback 和 bridge 测试能力。

**关键特性**：
- ✅ 向后兼容（通过构造函数参数控制）
- ✅ 幂等性（重复调用安全）
- ✅ 自动清理（fixture 集成）
- ✅ 完善的错误处理
- ✅ 详细的日志和可观测性
- ✅ 易于集成到现有测试框架

**实现优先级**：
1. 核心方法：`set_loopback`, `bridge`（高优先级）
2. 清理方法：`unset_loopback`, `unbridge`（高优先级）
3. 辅助方法：设备路径获取、会话清理（高优先级）
4. 远程 bridge：`bridge_remote`, `unbridge_remote`（中优先级）
5. 高级功能：监控、统计、可配置参数（低优先级）

**下一步行动**：
1. 在 `sonic.py` 中实现核心方法
2. 创建测试 fixture
3. 编写单元测试
4. 集成到现有 console 测试用例
5. 文档和示例更新
