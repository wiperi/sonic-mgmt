# SONiC Console Switch Loopback/Bridge Test Utilities 需求说明

## 1. 背景与目标

SONiC 目前支持作为 **Console Switch（Console Server）** 使用。  
在 sonic-mgmt 测试框架中，已经有一套通用的 console 测试设计文档（`console_test_hld`），其中定义了大量串口相关的功能与测试线缆连接方式（test wiring）。

为了在新的物理拓扑 **`c0` / `c0-lo`** 上运行这些 console 测试，需要通过 **编程方式控制 console leaf fanout**，实现：

- 串口端口的 loopback（自回环）
- 串口端口之间的 bridge（互连）
- 串口端口到远端虚拟串口的 bridge（远程互连）

本需求说明文档的目标是定义三类 test utilities 的功能与约束：

- `set_loopback(port)`
- `bridge(port1, port2)`
- `bridge_remote(port1, remote_host_console_port)`

这些 utilities 将作为 SONiC console switch 功能测试的基础能力，供 pytest 测试用例调用。

---

## 2. 适用范围（Scope）

- 测试对象（DUT）：以 **Console Switch 模式运行的 SONiC 设备**（文档中称为 `C0`）。
- 物理拓扑：`c0`、`c0-lo` testbed。
- 功能范围：
  - 在 **console leaf fanout** 一侧，通过软件实现：
    - console 端口 loopback（单端口回环）
    - console 端口之间的互联（桥接）
    - console 端口与远端虚拟串口之间的互联（远程桥接）
  - 所有操作均通过 **socat** 等通用工具实现，不涉及人工改线。
- 不在本次范围内：
  - 硬件流控（RTS/CTS、DTR/DSR 等）相关测试的完全覆盖。
  - 修改 DUT 内部实现（仅通过外部 fanout + 工具对拓扑进行编程）。

---

## 3. 测试拓扑与前置条件

### 3.1 数据中心拓扑背景（T0/T1/T2）

在数据中心中，SONiC 设备通常部署在 T0/T1/T2 层：

- **T0（ToR）**：下联 servers，上联多台 T1。
- **T1**：下联多台 T0，上联多台 T2。
- **T2**：下联多台 T1，上联 Regional Gateway（T3）。

sonic-mgmt 的测试主要针对 SONiC 在这些层级（T0/T1/T2）上的功能行为。为了支持这类测试，需要通过模拟邻居设备和流量注入能力构建物理 testbed。

### 3.2 Physical testbed 结构（与 console 相关部分）

典型 physical testbed 包含以下组件：

- Test servers（测试服务器）
- Fanout switches
  - Root fanout（可选）
  - **Leaf fanout（本需求中的 console leaf fanout）**
- SONiC DUT（本场景为 console switch / console server）

关键点：

- 每一个 DUT port（或 console line）在物理上都连接至某一台 leaf fanout。
- 每个端口在 leaf fanout 上会被映射为一个可控端点，例如：
  - `/dev/ttyUSB<N>`，或
  - 形如 `/dev/C0-1 -> ttyUSB0` 的符号链接。

示例（实际已存在的环境）：

```bash
admin@bjw3-can-720dt-leaf-27:~$ ls -lh /dev/C* | sort
lrwxrwxrwx 1 root root 7 Dec  5 15:32 /dev/C0-10 -> ttyUSB9
lrwxrwxrwx 1 root root 7 Dec  5 15:32 /dev/C0-1  -> ttyUSB0
lrwxrwxrwx 1 root root 7 Dec  5 15:32 /dev/C0-2  -> ttyUSB1
...
```

### 3.3 拓扑 c0 / c0-lo 的 console 测试特点

* 在 `c0` 拓扑中，可以把 console leaf fanout 理解为一个可编程“扇出/矩阵”，所有 C0 的 console 线路都终止在这台 leaf fanout 上。
* 借助 `socat`，可以在 leaf fanout 上实现 **N×N 任意端口之间的逻辑连接**（any-to-any），无需实际重新插拔串口线缆。
* `c0-lo` 可以视为偏向 loopback/本地验证的变体拓扑，更强调单端口测试能力。

---

## 4. 总体设计原则

1. **所有 loopback/bridge 操作必须在 console leaf fanout 上执行**

   * 在 fanout 主机上执行 `socat` 等命令；
   * 不在 DUT（C0）上运行任何桥接/回环进程。

2. **不依赖人工改线，实现“可编程接线矩阵”**

   * 所有“改线”通过 utilities 调用，在测试代码中自动完成。

3. **不要求硬件流控测试覆盖**

   * 当前范围内只保证数据链路（TX/RX）回环与互联；
   * RTS/CTS 等硬件流控行为不保证。

4. **幂等、可清理**

   * 每次建立 loopback/bridge 前先清理旧的同端口配置；
   * 退出/异常时必须能够释放资源、关闭 socat、释放串口。

5. **与 sonic-mgmt 测试基础设施对齐**

   * 利用现有 fixture：`fanouthosts`、`conn_graph_facts` 等；
   * 将 utilities 封装在 `tests/common/helpers/` 下，供 `tests/console/` 引用。

---

## 5. 接口定义（逻辑层）

> 以下接口是“逻辑需求定义”，具体实现语言以 sonic-mgmt 当前使用的 Python/pytest 栈为主。

### 5.1 `set_loopback(port)`

**用途**
对指定 console line 对应的端口建立 **逻辑 loopback**：
DUT 从该 line 发出的数据，会从同一 line 收回，用于 loopback 测试。

**输入**

* `port`：console line 编号或与 testbed topo 一致的逻辑标识（如 line index）。

**输出 / 行为**

* 在对应的 console leaf fanout 上：

  * 找到该 line 对应的设备端点（例如 `/dev/C0-1`）。
  * 启动一个后台进程，使用 socat + 伪终端 + echo 机制实现“发什么就回什么”的数据流。

**典型数据流逻辑（需求层描述）**

* DUT（C0）通过 console line `port` 把数据发到 leaf fanout 的 `/dev/C0-<port>`；
* leaf fanout 上的 loopback 逻辑读取这些数据，并原样写回同一设备；
* DUT 在同一 console line 上读取即可看到原样数据。

**前置条件**

* `port` 在当前 testbed 中存在，并能通过 `conn_graph_facts` 映射到 fanout + fanout 端口；
* fanout 主机上存在可访问的 `/dev/C0-<port>`（或等价设备名）；
* fanout 系统安装了 socat（或能通过 helper 自动部署）。

**错误处理**

* 若 `port` 未在 `conn_graph_facts` 中找到：
  → 在测试层触发 `pytest.skip`，并给出明确原因。
* 若 fanout 无法访问对应 `/dev` 设备，或打开失败：
  → 抛出异常/返回错误，并在日志中记录具体命令、stderr。
* 若 loopback 已经存在：

  * 需先执行清理逻辑（kill 旧的 socat 进程），再重建；
  * 确保行为幂等。

---

### 5.2 `bridge(port1, port2)`

**用途**
将两个 console line 对应的 port 做 **双向桥接**（cross-connect），模拟两条串口线直接互连的场景，用于交互类测试（例如“设备 A 通过 line1 与设备 B 通过 line2 通信”）。

**输入**

* `port1`：console line 1 标识。
* `port2`：console line 2 标识。

**输出 / 行为**

* 在 console leaf fanout 上：

  * 找到 `port1` 对应设备（例如 `/dev/C0-1`）；
  * 找到 `port2` 对应设备（例如 `/dev/C0-2`）；
  * 确认二者属于同一 fanout 主机；
  * 启动一个后台 socat 进程，将两个设备双向连接：

    > 逻辑上：`port1.TX → port2.RX`，`port2.TX → port1.RX`。

**前置条件**

* `port1`、`port2` 均在当前 topo 中已定义；
* 两个 port 映射到的 fanout host 相同（本版要求同一 leaf fanout）；
* 两个 `/dev` 设备均可访问；
* fanout 上有可用的 socat。

**错误处理**

* 如果 `port1` 或 `port2` 未在 `conn_graph_facts` 中映射：
  → `pytest.skip` 或显式报错。
* 如果两个 port 映射到不同 fanout：
  → 当前版本直接报错或跳过（不跨 fanout 做桥接）。
* 启动前需调用通用清理逻辑：

  * 清除与 `port1`、`port2` 相关的已有 bridge/loopback；
  * 避免串口被多个 socat 同时占用。
* 运行中异常（例如设备被拔出）：

  * socat 会退出，测试侧需要在验证阶段能够感知连接失效（例如通过返回码/日志检查）。

---

### 5.3 `bridge_remote(port1, remote_host_console_port)`

**用途**
将本地 fanout 上的某个 console port 与 **远端虚拟串口** 互联，支持：

* SONiC console switch ↔ 远端虚拟 DTE 的交互测试；
* SONiC ↔ SONiC 通过串口互联等高级场景。

**输入**

* `port1`：本地 console line 标识。
* `remote_host_console_port`：远端虚拟串口描述，至少包括：

  * 远端主机地址；
  * 远端监听端口（TCP 端口号）；
  * 或其它可唯一定位远端虚拟串口的参数（可封装为结构体/配置对象）。

**输出 / 行为**

* 在本地 console leaf fanout 上：

  * 找到 `port1` 对应设备（`/dev/C0-<port1>` 等）；
  * 启动 socat，将该设备与 `TCP:remote_host:remote_port` 双向连接。
* 在远端主机上（由测试框架或外部脚本配合）：

  * 启动一个 socat 或等效组件：

    * 将 `TCP-LISTEN:<remote_port>` 与一个 PTY 或实际应用进程（虚拟 DTE）连接；
  * 这样 `port1` 上的数据会经过 TCP 到达远端虚拟串口，再由虚拟 DTE 消费/回应。

**前置条件**

* `port1` 在本地 topo 中存在并可映射；
* 远端主机可达（网络连通性）；
* 远端虚拟串口监听逻辑已经准备好（否则本地 `bridge_remote` 可以失败或等待超时）。

**错误处理**

* 若 `port1` 未映射：`pytest.skip` 或报错；
* 若本地无法连接远端 TCP 端口：

  * 返回错误，并在日志中记录错误信息（连接拒绝/超时等）；
* 若已有针对 `port1` 的其他 bridge / loopback：

  * 先执行清理再建立新的 remote bridge。

---

## 6. 与 sonic-mgmt 测试框架的集成要求

### 6.1 模块位置与封装

* 在 `tests/common/helpers/` 下新增模块，例如：

  * `tests/common/helpers/console_switch_utils.py`
* 对外暴露面向测试的简洁接口：

  * 函数形式：`set_loopback(duthost, port)` / `bridge(duthost, port1, port2)` / `bridge_remote(...)`
  * 或类封装：`ConsoleSwitchSession(duthost).bridge(...)`
* `tests/console/` 内的具体用例/fixture 尽量只调用这些接口，不直接拼接 socat 命令。

### 6.2 使用现有 fixture

* `fanouthosts`

  * 从中选择与当前 DUT（console switch）对应的 console leaf fanout host。
  * 用于在 fanout 上执行命令（如 `host.shell(cmd)`）。

* `conn_graph_facts`

  * 利用 `conn_graph_facts['device_conn'][console_dut][dut_port]` 获取：

    * `peerdevice`（fanout 名字）
    * `peerport`（fanout 端口 label）
  * 再由 fanout 端的 udev / 命名规则将 `peerport` 映射为 `/dev/C0-<line>` 或 `/dev/ttyUSB<N>`。

### 6.3 命令执行与权限控制

* 工具内部需封装远程命令执行，典型流程：

  * 通过 `fanouthost.shell()` / `fanouthost.command()` 执行 `socat` 和清理命令；
  * 如需 root 权限，支持 `become: true`（等效于 `sudo`）。
* 内部必须做好：

  * PID 记录（例如在 fanout `/tmp/console_loopback_*.pid`、`/tmp/console_bridge_*.pid`）；
  * 日志输出位置（例如 `/var/log/console_socat_*.log`）。

---

## 7. 非功能性需求

### 7.1 幂等性与清理

* 所有 APIs 在相同参数下重复调用必须可预期：

  * 第一次：创建 loopback/bridge；
  * 第二次：若已有同配置存在，先清理旧进程再重建，或直接视作成功。
* 提供显式 teardown 能力：

  * 例如 `clear_loopback(port)` / `clear_bridge(port1, port2)`（可选）；
  * fixture 层可以使用 `yield` 或 context manager 自动清理。

### 7.2 并发与端口独占

* 同一时刻一个 `/dev/C0-X` 只能属于一条有效 loopback/bridge。
* 工具应在内部考虑简单的互斥机制：

  * 启动前检查端口是否已有 PID 记录；
  * 如存在，则 warn + 清理，或直接失败。

### 7.3 日志与可观测性

* 对每次操作应至少记录：

  * 操作类型（loopback/bridge/bridge_remote）；
  * 参与端口/远端地址；
  * 启动命令（或摘要）；
  * PID 与退出状态（失败时）。
* 在 pytest 失败时，可以辅助输出相关 log 片段，便于定位串口链路问题。

### 7.4 可靠性与错误信息

* 避免因 socat 命令错误导致整个测试进程 hang 死：

  * 设置合理的超时；
  * 使用非阻塞模式；
  * 在失败时快速返回、给出清晰 error message。
* 在 DUT 功能正常而 fanout 配置异常时，测试报告应尽量区分：

  * DUT 问题 vs. testbed/bridge 工具问题。

---

## 8. 限制与不在本次范围的内容

* **硬件流控（RTS/CTS/DTR/DSR）不在当前实现范围内**：

  * 当前 loopback/bridge 基于字节流（TX/RX）；
  * 不保证控制线透传及电气特性，相关 case 不在覆盖范围内。

* **跨 fanout 的串口桥接不在本版本要求中**：

  * 若未来存在多 fanout 复杂场景，可另行扩展 `bridge` 语义。

* **不修改 DUT 内部串口驱动/配置逻辑**：

  * 所有测试辅助能力通过 fanout 与外部工具实现。

---

## 9. 后续扩展与开放问题（Open Points）

* 是否需要支持特定平台的“硬件级 loopback”：

  * 某些 console-mux 可能提供 on-box 配置命令，可实现真·TX↔RX 短接；
  * 若平台支持，可在当前接口下增加 platform-specific 的优化实现。

* 远端虚拟串口的统一描述方式：

  * `remote_host_console_port` 是否设计成 struct，例如：

    * `{"host": "...", "tcp_port": 20001, "pty_link": "/tmp/..."}`
  * 以及是否需要 helper 协助远端启动 socat / 虚拟 DTE。

* 封装方式：

  * 是否需要在 `tests/console/fixtures.py` 中定义：

    * `loopback_session` fixture；
    * `bridge_session` fixture；
  * 方便用例使用 `with` / `yield` 自动建立和清理。

---

## 10. 总结

本需求说明文档定义了在 SONiC 作为 console switch 的场景下，基于 `c0/c0-lo` 拓扑和 console leaf fanout，实现三类测试用 utilities（`set_loopback`、`bridge`、`bridge_remote`）的功能与约束。

关键点包括：

* 所有 loopback/bridge 能力在 **leaf fanout 上通过 socat** 完成，不侵入 DUT；
* 基于现有 `fanouthosts`、`conn_graph_facts` 自动发现并操作对应的 `/dev/C0-*` 串口设备；
* 提供可编程、可清理、幂等的 testbed“虚拟改线”能力；
* 明确当前版本不覆盖硬件流控相关场景。

在此基础上，后续可以直接开展 Python helper 实现与 pytest fixture 集成工作。
