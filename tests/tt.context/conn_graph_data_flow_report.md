# sonic-mgmt 连接图数据流分析报告

## 目录
1. [概述](#概述)
2. [数据流架构图](#数据流架构图)
3. [第一阶段：CSV文件（数据源）](#第一阶段csv文件数据源)
4. [第二阶段：Graph Utils（数据解析与处理）](#第二阶段graph-utils数据解析与处理)
5. [第三阶段：Ansible模块（数据封装）](#第三阶段ansible模块数据封装)
6. [第四阶段：测试fixtures（数据使用）](#第四阶段测试fixtures数据使用)
7. [完整数据流示例](#完整数据流示例)
8. [总结](#总结)

---

## 概述

sonic-mgmt项目使用一套精心设计的数据流系统来管理测试环境的拓扑信息。数据从CSV文件开始，经过多层处理，最终被测试用例使用。整个流程体现了"分离关注点"和"模块化"的设计原则。

**核心流程：**
```
CSV文件 → graph_utils.py → conn_graph_facts.py(Ansible) → conn_graph_facts.py(pytest) → 测试用例
```

---

## 数据流架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    第一阶段：数据源层                              │
│                                                                 │
│  /ansible/files/                                               │
│  ├── graph_groups.yml           (定义图组织结构)                 │
│  ├── sonic_lab_devices.csv      (设备信息)                      │
│  ├── sonic_lab_links.csv        (设备连接关系)                   │
│  ├── sonic_lab_pdu_links.csv    (PDU电源连接)                   │
│  ├── sonic_lab_console_links.csv (控制台连接)                   │
│  ├── sonic_lab_bmc_links.csv    (BMC连接)                       │
│  └── sonic_lab_l1_links.csv     (L1交换机连接)                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                 第二阶段：数据解析与处理层                          │
│                                                                 │
│  /ansible/module_utils/graph_utils.py                          │
│  ├── class LabGraph                                            │
│  │   ├── __init__()              (初始化，读取CSV)              │
│  │   ├── read_csv_files()        (读取所有CSV文件)              │
│  │   ├── csv_to_graph_facts()    (转换为内部数据结构)            │
│  │   └── build_results()         (构建最终结果)                 │
│  └── find_graph()                (查找匹配的图组)                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                  第三阶段：Ansible模块封装层                       │
│                                                                 │
│  /ansible/library/conn_graph_facts.py                          │
│  ├── main()                      (模块入口)                     │
│  │   ├── 解析参数 (host/hosts/anchor/filepath/group)            │
│  │   ├── 调用 find_graph() 或创建 LabGraph                      │
│  │   └── 调用 build_results() 生成 ansible_facts               │
│  └── 返回 ansible_facts 给调用者                                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                  第四阶段：测试Fixture层                          │
│                                                                 │
│  /tests/common/fixtures/conn_graph_facts.py                    │
│  ├── @pytest.fixture conn_graph_facts     (主fixture)          │
│  ├── @pytest.fixture fanout_graph_facts   (fanout设备)         │
│  ├── get_graph_facts()                    (调用Ansible模块)     │
│  └── key_convert2str()                    (数据类型转换)        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                       测试用例使用                                │
│                                                                 │
│  测试用例通过pytest fixture获取拓扑信息                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 第一阶段：CSV文件（数据源）

### 1.1 文件组织结构

CSV文件位于 `/ansible/files/` 目录下，按照图组（graph group）进行组织。

**graph_groups.yml** 定义了可用的图组：
```yaml
---
  - lab
  - snappi-sonic
```

每个图组包含一套完整的CSV文件，命名格式为 `sonic_{group}_{type}.csv`：

| 文件名模式 | 说明 | 示例 |
|-----------|------|------|
| `sonic_{group}_devices.csv` | 设备信息 | `sonic_lab_devices.csv` |
| `sonic_{group}_links.csv` | 设备间连接 | `sonic_lab_links.csv` |
| `sonic_{group}_pdu_links.csv` | PDU电源连接 | `sonic_lab_pdu_links.csv` |
| `sonic_{group}_console_links.csv` | 控制台连接 | `sonic_lab_console_links.csv` |
| `sonic_{group}_bmc_links.csv` | BMC连接 | `sonic_lab_bmc_links.csv` |
| `sonic_{group}_l1_links.csv` | L1交换机连接 | `sonic_lab_l1_links.csv` |

### 1.2 数据格式详解

#### 1.2.1 设备信息 (devices.csv)

```csv
Hostname,ManagementIp,HwSku,Type,Protocol,Os
str-msn2700-01,10.251.0.188/23,Mellanox-2700,DevSonic,,sonic
str-7260-10,10.251.0.13/23,Arista-7260QX-64,FanoutLeaf,,sonic
str-7260-11,10.251.0.234/23,Arista-7260QX-64,FanoutRoot,,eos
str-acs-serv-01,10.251.0.245/23,TestServ,Server,,ubuntu
pdu-1,192.168.9.2,Apc,Pdu,snmp,
console-1,192.168.10.1/23,Cisco,ConsoleServer,ssh,sonic
```

**字段说明：**
- `Hostname`: 设备主机名（唯一标识符）
- `ManagementIp`: 管理IP地址（可带子网掩码）
- `HwSku`: 硬件型号
- `Type`: 设备类型（DevSonic/FanoutLeaf/FanoutRoot/Server/Pdu/ConsoleServer等）
- `Protocol`: 通信协议（如snmp, ssh）
- `Os`: 操作系统（sonic/eos/ubuntu等）

#### 1.2.2 连接信息 (links.csv)

```csv
StartDevice,StartPort,EndDevice,EndPort,BandWidth,VlanID,VlanMode,AutoNeg
str-msn2700-01,Ethernet0,str-7260-10,Ethernet1,40000,1681,Access,on
str-msn2700-01,Ethernet4,str-7260-10,Ethernet2,40000,1682,Access,on
str-7260-11,Ethernet30,str-7260-10,Ethernet64,40000,1681-1712,Trunk,on
```

**字段说明：**
- `StartDevice/EndDevice`: 连接两端的设备名
- `StartPort/EndPort`: 连接端口名
- `BandWidth`: 带宽（如40000表示40G）
- `VlanID`: VLAN ID（可以是范围如"1681-1712"）
- `VlanMode`: VLAN模式（Access/Trunk）
- `AutoNeg`: 自动协商（on/off）

**可选字段：**
- `StartVlanID/EndVlanID`: 两端不同的VLAN ID
- `StartVlanMode/EndVlanMode`: 两端不同的VLAN模式
- `StartVrf/EndVrf`: VRF名称
- `StartPortMac/EndPortMac`: MAC地址
- `FECDisable`: 是否禁用FEC

### 1.3 数据特点

1. **结构化存储**：使用CSV格式，易于编辑和版本控制
2. **关系模型**：devices定义实体，links定义关系
3. **分组管理**：通过group机制支持多套测试环境
4. **扩展性**：支持多种辅助连接（PDU、Console、BMC、L1）

---

## 第二阶段：Graph Utils（数据解析与处理）

### 2.1 核心类：LabGraph

位置：`/ansible/module_utils/graph_utils.py`

LabGraph类是数据处理的核心，负责将CSV数据转换为结构化的Python对象。

#### 2.1.1 初始化流程

```python
class LabGraph(object):
    SUPPORTED_CSV_FILES = {
        "devices": "sonic_{}_devices.csv",
        "links": "sonic_{}_links.csv",
        "pdu_links": "sonic_{}_pdu_links.csv",
        "console_links": "sonic_{}_console_links.csv",
        "bmc_links": "sonic_{}_bmc_links.csv",
        "l1_links": "sonic_{}_l1_links.csv",
    }

    def __init__(self, path, group):
        self.path = path                    # CSV文件路径
        self.group = group                  # 图组名（如"lab"）
        
        # 构建CSV文件路径字典
        self.csv_files = {
            k: os.path.join(self.path, v.format(group)) 
            for k, v in self.SUPPORTED_CSV_FILES.items()
        }
        
        # 缓存：端口别名映射
        self._cache_port_alias_to_name = {}
        self._cache_port_name_to_alias = {}
        
        # 数据存储
        self.csv_facts = {}      # 原始CSV数据
        self.graph_facts = {}    # 处理后的图数据
        
        # 执行数据加载
        self.read_csv_files()
        self.csv_to_graph_facts()
```

#### 2.1.2 读取CSV文件

```python
def read_csv_files(self):
    """读取所有CSV文件到csv_facts字典"""
    for k, v in self.csv_files.items():
        if os.path.exists(v):
            self.csv_facts[k] = self.read_csv_file(v)
        else:
            logging.debug("Missing file {}".format(v))
            self.csv_facts[k] = {}

def read_csv_file(self, v):
    """读取单个CSV文件，返回字典列表"""
    with open(v) as csvfile:
        reader = csv.DictReader(csvfile)
        return [row for row in reader]
```

**数据结构示例（csv_facts）：**
```python
{
    "devices": [
        {"Hostname": "str-msn2700-01", "ManagementIp": "10.251.0.188/23", ...},
        {"Hostname": "str-7260-10", "ManagementIp": "10.251.0.13/23", ...}
    ],
    "links": [
        {"StartDevice": "str-msn2700-01", "StartPort": "Ethernet0", ...},
        ...
    ],
    "pdu_links": [...],
    "console_links": [...],
    "bmc_links": [...],
    "l1_links": [...]
}
```

#### 2.1.3 数据转换：csv_to_graph_facts()

这是最核心的数据处理方法，将CSV数据转换为易于查询的图结构。

##### A. 处理设备信息

```python
def csv_to_graph_facts(self):
    devices = {}
    for entry in self.csv_facts["devices"]:
        management_ip = entry["ManagementIp"]
        
        # 解析管理IP，提取IP地址和网关
        if len(management_ip.split("/")) > 1:
            iface = ipaddress.ip_interface(six.text_type(management_ip))
            entry["mgmtip"] = str(iface.ip)
            entry["ManagementGw"] = str(iface.network.network_address + 1)
        
        # 设置默认值
        if entry["Type"].lower() not in ["pdu", "consoleserver", "mgmttstorrouter"]:
            if "CardType" not in entry:
                entry["CardType"] = "Linecard"
            if "HwSkuType" not in entry:
                entry["HwSkuType"] = "predefined"
        
        devices[entry["Hostname"]] = entry
    
    self.graph_facts["devices"] = devices
```

**转换结果：**
```python
{
    "str-msn2700-01": {
        "Hostname": "str-msn2700-01",
        "ManagementIp": "10.251.0.188/23",
        "mgmtip": "10.251.0.188",
        "ManagementGw": "10.251.0.1",
        "HwSku": "Mellanox-2700",
        "Type": "DevSonic",
        "Os": "sonic",
        "CardType": "Linecard",
        "HwSkuType": "predefined"
    }
}
```

##### B. 处理连接信息

连接处理是最复杂的部分，涉及：
- 端口别名到端口名的转换（Sonic设备）
- VLAN解析和处理
- VRF处理
- 创建双向连接映射

```python
# 核心数据结构初始化
links = {}              # 设备连接字典
linked_ports = {}       # 支持多对端口的连接
port_vlans = {}         # 端口VLAN配置
vrfs = {}              # VRF信息
port_vrfs = {}         # 端口VRF映射

# 按设备分组连接
links_group_by_devices = {}
ports_group_by_devices = {}

for entry in self.csv_facts["links"]:
    # 收集每个设备的所有连接和端口
    ...
```

**端口名称转换：**
```python
# 检测是否需要将端口别名转换为端口名
convert_alias_to_name = []
for device, start_ports in links_group_by_devices.items():
    if self.graph_facts["devices"][device].get("Os", "").lower() == "sonic":
        # 判断是使用别名还是名称
        if all([port in self._get_port_alias_set(device) 
                for port in ports_group_by_devices[device]]):
            convert_alias_to_name.append(device)
```

**VLAN处理：**
```python
def _port_vlanlist(self, vlanrange):
    """将VLAN范围字符串转换为列表
    
    输入: "1-10,20,30-40"
    输出: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 31, ..., 40]
    """
    vlans = []
    for vlanid in list(map(str.strip, vlanrange.split(','))):
        if vlanid.isdigit():
            vlans.append(int(vlanid))
        elif '-' in vlanid:
            vlanlist = list(map(str.strip, vlanid.split('-')))
            vlans.extend(list(range(int(vlanlist[0]), int(vlanlist[1]) + 1)))
    return sorted(set(vlans))
```

**构建连接字典：**
```python
for link in self.csv_facts["links"]:
    start_device = link["StartDevice"]
    end_device = link["EndDevice"]
    start_port = link["StartPort"]
    end_port = link["EndPort"]
    
    # 端口名称转换（如需要）
    if link["StartDevice"] in convert_alias_to_name:
        start_port = self._port_alias_to_name(link["StartDevice"], link['StartPort'])
    
    # 创建连接信息
    start_port_linked_port = {
        "peerdevice": end_device,
        "peerport": end_port,
        "speed": band_width,
        "fec_disable": fec_disable
    }
    
    # 双向存储
    links[start_device][start_port] = start_port_linked_port
    links[end_device][end_port] = end_port_linked_port
    
    # VLAN配置
    port_vlans[start_device][start_port] = {
        "mode": start_vlan_mode,
        "vlanids": start_vlan_id,
        "vlanlist": self._port_vlanlist(start_vlan_id),
    }
```

**最终数据结构（graph_facts["links"]）：**
```python
{
    "str-msn2700-01": {
        "Ethernet0": {
            "peerdevice": "str-7260-10",
            "peerport": "Ethernet1",
            "speed": "40000",
            "autoneg": "on",
            "fec_disable": False
        },
        "Ethernet4": {...}
    },
    "str-7260-10": {
        "Ethernet1": {
            "peerdevice": "str-msn2700-01",
            "peerport": "Ethernet0",
            ...
        }
    }
}
```

##### C. 处理辅助连接

**Console连接：**
```python
console_links = {}
for entry in self.csv_facts["console_links"]:
    start_device = entry["EndDevice"]  # 被管理的设备
    console_links[start_device] = {
        "ConsolePort": {
            "baud_rate": entry.get("BaudRate", None),
            "peerdevice": entry["StartDevice"],  # Console服务器
            "peerport": entry["StartPort"],
            "proxy": entry["Proxy"],
            "type": entry["Console_type"],
            "menu_type": entry["Console_menu_type"],
        }
    }
self.graph_facts["console_links"] = console_links
```

**PDU连接（支持双电源）：**
```python
pdu_links = {}
for entry in self.csv_facts["pdu_links"]:
    start_device = entry["EndDevice"]
    start_port = entry["EndPort"]  # 如PSU1
    feed = entry.get("EndFeed", "N/A")  # A或B电源
    
    pdu_links_of_feed = {
        "peerdevice": entry["StartDevice"],
        "peerport": entry["StartPort"],
        "feed": feed,
    }
    # 按设备->PSU->Feed组织
    pdu_links[start_device][start_port][feed] = pdu_links_of_feed
```

**L1交换机连接：**
```python
from_l1_links = {}  # L1 -> 设备
to_l1_links = {}    # 设备 -> L1

for entry in self.csv_facts["l1_links"]:
    device_name = entry["StartDevice"]
    l1_name = entry["EndDevice"]
    
    # 支持多通道端口（用|分隔）
    if "|" in l1_port:
        lanes = l1_port.split("|")
        for lane in lanes:
            from_l1_links[l1_name][lane] = {
                "peerdevice": device_name,
                "peerport": device_port
            }
    else:
        from_l1_links[l1_name][l1_port] = {...}
    
    to_l1_links[device_name][device_port] = {
        "peerdevice": l1_name,
        "peerport": l1_port if "|" not in l1_port else l1_port.split("|"),
    }
```

#### 2.1.4 构建结果：build_results()

这个方法根据指定的主机名列表，从graph_facts中提取相关数据。

```python
def build_results(self, hostnames, ignore_error=False):
    """为指定主机构建结果
    
    Args:
        hostnames: 主机名列表
        ignore_error: 是否忽略错误
        
    Returns:
        (success, results): 元组，成功标志和结果字典
    """
    device_info = {}
    device_conn = {}
    device_port_vlans = {}
    device_vlan_list = {}
    device_vlan_range = {}
    device_console_link = {}
    device_pdu_links = {}
    device_bmc_link = {}
    # ... 更多字典
    
    for hostname in hostnames:
        # 获取设备信息
        device = self.graph_facts["devices"].get(hostname, None)
        if device is None and not ignore_error:
            return (False, "Cannot find device {}".format(hostname))
        
        device_info[hostname] = device
        device_conn[hostname] = self.graph_facts["links"].get(hostname, {})
        device_port_vlans[hostname] = self.graph_facts["port_vlans"].get(hostname, {})
        
        # 计算VLAN列表
        vlan_list = []
        for port_info in device_port_vlans[hostname].values():
            vlan_list.extend(port_info["vlanlist"])
        vlan_list = natsorted(vlan_list)
        device_vlan_list[hostname] = vlan_list
        device_vlan_range[hostname] = self._convert_list2range(vlan_list)
        
        # 处理console/PDU/BMC连接
        device_console_link[hostname] = self.graph_facts["console_links"].get(hostname, {})
        device_pdu_links[hostname] = self.graph_facts["pdu_links"].get(hostname, {})
        ...
    
    # 收集所有device_开头的变量
    results = {k: v for k, v in locals().items()
               if (k.startswith("device_") and v)}
    
    return (True, results)
```

**返回结果示例：**
```python
{
    "device_info": {
        "str-msn2700-01": {
            "Hostname": "str-msn2700-01",
            "ManagementIp": "10.251.0.188/23",
            "HwSku": "Mellanox-2700",
            ...
        }
    },
    "device_conn": {
        "str-msn2700-01": {
            "Ethernet0": {"peerdevice": "str-7260-10", "peerport": "Ethernet1", ...}
        }
    },
    "device_port_vlans": {
        "str-msn2700-01": {
            "Ethernet0": {"mode": "Access", "vlanids": "1681", "vlanlist": [1681]}
        }
    },
    "device_vlan_list": {
        "str-msn2700-01": [1681, 1682, 1683, ...]
    },
    "device_vlan_range": {
        "str-msn2700-01": ["1681-1712"]
    },
    "device_console_link": {...},
    "device_pdu_links": {...},
    "device_bmc_link": {...}
}
```

### 2.2 辅助函数：find_graph()

位置：`/ansible/library/conn_graph_facts.py`

```python
def find_graph(hostnames, part=False):
    """查找包含目标设备的图文件
    
    Args:
        hostnames: 主机名列表
        part: 是否允许部分匹配（80%以上）
        
    Returns:
        LabGraph实例或None
    """
    # 读取图组配置
    graph_group_file = os.path.join(LAB_GRAPHFILE_PATH, LAB_GRAPH_GROUPS_FILE)
    with open(graph_group_file) as fd:
        graph_groups = yaml.safe_load(fd)
    
    target_graph = None
    target_group = None
    
    # 遍历所有图组
    for group in graph_groups:
        logging.debug("Looking at graph files of group {} for hosts {}".format(group, hostnames))
        lab_graph = LabGraph(LAB_GRAPHFILE_PATH, group)
        graph_hostnames = set(lab_graph.graph_facts["devices"].keys())
        
        if not part:
            # 精确匹配：所有主机都在图中
            if set(hostnames) <= graph_hostnames:
                target_graph = lab_graph
                target_group = group
                break
        else:
            # 部分匹配：80%以上的主机在图中
            THRESHOLD = 0.8
            in_graph_hostnames = set(hostnames).intersection(graph_hostnames)
            if len(in_graph_hostnames) * 1.0 / len(hostnames) >= THRESHOLD:
                target_graph = lab_graph
                target_group = group
                break
    
    return target_graph
```

**查找逻辑：**
1. 读取`graph_groups.yml`获取所有图组
2. 对每个图组创建`LabGraph`实例
3. 检查请求的主机名是否在该图组中
4. 返回第一个匹配的图

---

## 第三阶段：Ansible模块（数据封装）

### 3.1 模块概述

位置：`/ansible/library/conn_graph_facts.py`

这是一个标准的Ansible模块，将LabGraph的功能封装为Ansible可调用的形式。

### 3.2 模块参数

```python
module = AnsibleModule(
    argument_spec=dict(
        host=dict(required=False),           # 单个主机（向后兼容）
        hosts=dict(required=False, type='list'),  # 主机列表
        filepath=dict(required=False),       # CSV文件路径
        group=dict(required=False),          # 图组名
        anchor=dict(required=False, type='list'),  # 锚点主机（返回整个图）
        ignore_errors=dict(required=False, type='bool', default=False),
    ),
    mutually_exclusive=[['host', 'hosts', 'anchor']],
    supports_check_mode=True
)
```

**参数说明：**
- `host`: 单个主机名（已弃用，保留用于向后兼容）
- `hosts`: 主机名列表（推荐使用）
- `filepath`: CSV文件路径（测试时使用，覆盖默认路径）
- `group`: 指定图组（如不指定，自动查找）
- `anchor`: 锚点主机列表（用于获取整个图，如配置根交换机）
- `ignore_errors`: 遇到错误时是否继续

**互斥关系：** `host`、`hosts`、`anchor`三者只能指定一个。

### 3.3 执行流程

```python
def main():
    module = AnsibleModule(...)
    m_args = module.params
    anchor = m_args['anchor']
    
    # 1. 确定目标主机
    if m_args['hosts']:
        hostnames = m_args['hosts']
    elif m_args['host']:
        hostnames = [m_args['host']]
    else:
        hostnames = []  # 返回整个图
    
    try:
        # 2. 设置文件路径（支持pytest调用）
        if m_args["filepath"]:
            global LAB_GRAPHFILE_PATH
            LAB_GRAPHFILE_PATH = m_args['filepath']
        
        # 3. 获取LabGraph实例
        if m_args["group"]:
            # 指定了group，直接创建
            lab_graph = LabGraph(LAB_GRAPHFILE_PATH, m_args["group"])
        else:
            # 未指定group，自动查找
            target = anchor if anchor else hostnames
            lab_graph = find_graph(target)
        
        # 4. 处理未找到图的情况
        if not lab_graph:
            results = {
                'device_info': {},
                'device_conn': {},
                'device_port_vlans': {},
            }
            module.exit_json(ansible_facts=results)
        
        # 5. 返回整个图（未指定hostnames）
        if not hostnames:
            results = {
                'device_info': lab_graph.graph_facts["devices"],
                'device_conn': lab_graph.graph_facts["links"],
                'device_port_vlans': lab_graph.graph_facts["port_vlans"]
            }
            module.exit_json(ansible_facts=results)
        
        # 6. 构建指定主机的结果
        succeed, results = lab_graph.build_results(hostnames, m_args['ignore_errors'])
        if succeed:
            module.exit_json(ansible_facts=results)
        else:
            module.fail_json(msg=results)
            
    except (IOError, OSError):
        module.fail_json(msg="Can not find required file")
    except Exception:
        module.fail_json(msg=traceback.format_exc())
```

### 3.4 返回数据格式

模块通过`module.exit_json(ansible_facts=results)`返回数据，数据会被添加到Ansible的facts中。

**重要说明：**

返回的结果**不是整个lab的完整图**，而是**只包含查询设备的子图**。例如，调用`build_results(["str-msn2700-01"])`只会返回该设备的相关信息，不包含lab中其他设备的数据。

返回的字典按**数据类型**分为四类：

#### 1. 节点属性（设备信息）

存储设备本身的属性，不涉及连接关系：

```python
{
    "device_info": {主机名: 设备属性},              # 查询设备的详细信息
    "device_console_info": {主机名: Console服务器属性},  # Console服务器的设备信息
    "device_pdu_info": {主机名: {PDU名: PDU属性}},      # PDU设备的信息
    "device_bmc_info": {主机名: BMC属性},              # BMC设备的信息
}
```

#### 2. 边（连接关系）

描述设备之间的各种连接，这是图的核心：

```python
{
    "device_conn": {主机名: {端口: 对端信息}},           # 网络连接（双向存储）
    "device_console_link": {主机名: Console连接信息},    # Console连接（单向）
    "device_pdu_links": {主机名: PDU连接信息},          # PDU连接（单向）
    "device_bmc_link": {主机名: BMC连接信息},           # BMC连接（单向）
    "device_from_l1_links": {主机名: L1连接},           # L1到设备（单向）
    "device_to_l1_links": {主机名: L1连接},             # 设备到L1（单向）
}
```

**注意：**
- **网络连接（device_conn）** 是双向存储的：物理上是无向边，但在数据结构中存储为两条有向边
- **其他连接** 都是单向存储的：只存储从被管理设备指向管理设备的方向

#### 3. 边的属性

为边附加的配置信息：

```python
{
    "device_port_vlans": {主机名: {端口: VLAN配置}},    # 端口的VLAN配置
    "device_port_vrfs": {主机名: {端口: VRF配置}},      # 端口的VRF配置（如有）
    "device_vrfs": {主机名: VRF集合},                   # 设备上的所有VRF（如有）
}
```

#### 4. 派生/计算数据

从原始数据计算得出的辅助信息，便于使用：

```python
{
    "device_vlan_list": {主机名: [VLAN列表]},           # 从port_vlans计算的完整VLAN列表
    "device_vlan_range": {主机名: ["VLAN范围"]},        # VLAN列表转换为范围字符串
    "device_vlan_map_list": {主机名: {端口索引: VLAN}}, # VLAN到端口索引的映射
    "device_l1_cross_connects": {L1设备名: 交叉连接},   # L1交叉连接计算结果
    "device_linked_ports": {主机名: {端口: [连接列表]}}, # 支持多连接的端口
}
```

#### 完整的返回数据结构

```python
{
    # ========== 节点属性 ==========
    "device_info": {...},              # 设备信息
    "device_console_info": {...},      # Console服务器信息
    "device_pdu_info": {...},          # PDU设备信息
    "device_bmc_info": {...},          # BMC设备信息
    
    # ========== 边（连接关系）==========
    "device_conn": {...},              # 网络连接（双向存储）
    "device_console_link": {...},      # Console连接（单向）
    "device_pdu_links": {...},         # PDU连接（单向）
    "device_bmc_link": {...},          # BMC连接（单向）
    "device_from_l1_links": {...},     # L1到设备的连接（单向）
    "device_to_l1_links": {...},       # 设备到L1的连接（单向）
    
    # ========== 边的属性 ==========
    "device_port_vlans": {...},        # 端口VLAN配置
    "device_port_vrfs": {...},         # 端口VRF配置
    "device_vrfs": {...},              # VRF集合
    
    # ========== 派生/计算数据 ==========
    "device_vlan_list": {...},         # VLAN列表（计算）
    "device_vlan_range": {...},        # VLAN范围（计算）
    "device_vlan_map_list": {...},     # VLAN映射（计算）
    "device_l1_cross_connects": {...}, # L1交叉连接（计算）
    "device_linked_ports": {...}       # 多连接端口（计算）
}
```

---

## 第四阶段：测试Fixtures（数据使用）

### 4.1 Fixture概述

位置：`/tests/common/fixtures/conn_graph_facts.py`

这个文件定义了pytest fixtures，使测试用例可以方便地获取连接图数据。

### 4.2 核心Fixtures

#### 4.2.1 conn_graph_facts (主Fixture)

```python
@pytest.fixture(scope="module")
def conn_graph_facts(duthosts, localhost):
    """获取所有DUT的连接图信息"""
    return get_graph_facts(
        duthosts[0], 
        localhost,
        [dh.hostname for dh in duthosts]
    )
```

**特点：**
- scope="module": 模块级别，整个测试模块共享一个实例
- 参数：依赖`duthosts`和`localhost` fixtures
- 返回：包含所有DUT设备的连接图信息

#### 4.2.2 fanout_graph_facts (Fanout设备Fixture)

```python
@pytest.fixture(scope="module")
def fanout_graph_facts(localhost, duthosts, rand_one_tgen_dut_hostname, conn_graph_facts):
    """获取连接到DUT的fanout设备的连接图信息"""
    duthost = duthosts[rand_one_tgen_dut_hostname]
    facts = dict()
    dev_conn = conn_graph_facts.get('device_conn', {})
    if not dev_conn:
        return facts
    
    # 遍历DUT的所有连接
    for _, val in list(dev_conn[duthost.hostname].items()):
        fanout = val["peerdevice"]
        if fanout not in facts:
            # 获取fanout设备的图信息
            facts[fanout] = {
                k: v[fanout] 
                for k, v in list(get_graph_facts(duthost, localhost, fanout).items())
            }
    return facts
```

**用途：** 获取与DUT连接的所有fanout设备（交换机）的详细信息。

#### 4.2.3 fanout_graph_facts_multidut (多DUT Fanout Fixture)

```python
@pytest.fixture(scope="module")
def fanout_graph_facts_multidut(localhost, duthosts, conn_graph_facts):
    """获取连接到多个DUT的fanout设备信息（仅IXIA/SNAPPI测试设备）"""
    facts = dict()
    dev_conn = conn_graph_facts.get('device_conn', {})
    if not dev_conn:
        return facts

    # 收集所有fanout设备
    fanout_set = set()
    for duthost in duthosts:
        for _, val in list(dev_conn[duthost.hostname].items()):
            fanout_set.add(val["peerdevice"])

    # 仅包含IXIA/SNAPPI测试设备
    for fanout in fanout_set:
        fanout_data = {
            k: v[fanout] 
            for k, v in list(get_graph_facts(duthost, localhost, fanout).items())
        }
        if fanout_data['device_info']['HwSku'] in ('SNAPPI-tester', 'IXIA-tester'):
            facts[fanout] = fanout_data

    return facts
```

**特点：** 仅返回流量测试设备（IXIA/SNAPPI），过滤掉普通交换机。

### 4.3 核心函数：get_graph_facts()

```python
def get_graph_facts(duthost, localhost, hostnames):
    """调用Ansible模块获取图信息
    
    Args:
        duthost: DUT主机的pytest fixture
        localhost: localhost的pytest fixture
        hostnames: 主机名（字符串或列表）
        
    Returns:
        dict: 连接图facts
    """
    # 1. 确定CSV文件路径
    base_path = os.path.dirname(os.path.realpath(__file__))
    lab_conn_graph_path = os.path.join(base_path, "../../../ansible/files/")

    # 2. 从inventory文件推断图组
    inv_files = duthost.host.options["inventory_manager"]._sources
    graph_groups_file = os.path.join(lab_conn_graph_path, "graph_groups.yml")
    group = None
    if os.path.isfile(graph_groups_file):
        graph_groups = yaml.safe_load(open(graph_groups_file))
        for inv_file in inv_files:
            inv_name = os.path.basename(inv_file)
            if inv_name in graph_groups:
                group = inv_name

    # 3. 构建参数
    kargs = {"filepath": lab_conn_graph_path}
    if group:
        kargs["group"] = group
    if isinstance(hostnames, six.string_types):
        kargs["host"] = hostnames
    elif isinstance(hostnames, (list, tuple)):
        kargs["hosts"] = hostnames
    
    # 4. 调用Ansible模块
    conn_graph_facts = localhost.conn_graph_facts(**kargs)["ansible_facts"]
    
    # 5. 数据类型转换（Python 3兼容）
    return key_convert2str(conn_graph_facts)
```

**关键步骤：**

1. **路径计算：** 从当前文件位置计算出CSV文件的路径
2. **图组推断：** 根据inventory文件名推断应该使用哪个图组
3. **参数构建：** 根据hostnames类型（字符串/列表）构建不同的参数
4. **调用模块：** 通过`localhost.conn_graph_facts()`调用Ansible模块
5. **类型转换：** 确保Python 2/3兼容性

### 4.4 数据类型转换：key_convert2str()

```python
def key_convert2str(conn_graph_facts):
    """转换键类型为字符串（Python 3兼容）
    
    在Python 2中，键可能是unicode
    在Python 3中，键可能是AnsibleUnsafeText
    统一转换为str类型
    """
    if six.PY2:
        return conn_graph_facts
    
    # Python 3: 转换device_conn的键
    result = copy.deepcopy(conn_graph_facts)
    result['device_conn'] = {}
    for key, value in list(conn_graph_facts['device_conn'].items()):
        result['device_conn'][str(key)] = value

    return result
```

### 4.5 测试用例使用示例

```python
def test_example(duthosts, conn_graph_facts, fanout_graph_facts):
    """示例测试用例"""
    
    # 获取第一个DUT
    duthost = duthosts[0]
    
    # 获取DUT的设备信息
    dut_info = conn_graph_facts['device_info'][duthost.hostname]
    print("DUT HwSku:", dut_info['HwSku'])
    print("DUT Management IP:", dut_info['ManagementIp'])
    
    # 获取DUT的所有连接
    dut_conns = conn_graph_facts['device_conn'][duthost.hostname]
    for port, conn in dut_conns.items():
        print(f"Port {port} connects to {conn['peerdevice']}:{conn['peerport']}")
    
    # 获取DUT的VLAN配置
    dut_vlans = conn_graph_facts['device_port_vlans'][duthost.hostname]
    for port, vlan_info in dut_vlans.items():
        print(f"Port {port}: mode={vlan_info['mode']}, vlans={vlan_info['vlanids']}")
    
    # 获取fanout设备信息
    for fanout_name, fanout_data in fanout_graph_facts.items():
        fanout_info = fanout_data['device_info']
        print(f"Fanout {fanout_name}: {fanout_info['HwSku']}")
```

---

## 完整数据流示例

让我们通过一个具体例子跟踪完整的数据流。

### 示例场景

测试用例需要获取主机`str-msn2700-01`的连接图信息。

### Step 1: CSV文件读取

**sonic_lab_devices.csv:**
```csv
Hostname,ManagementIp,HwSku,Type,Protocol,Os
str-msn2700-01,10.251.0.188/23,Mellanox-2700,DevSonic,,sonic
str-7260-10,10.251.0.13/23,Arista-7260QX-64,FanoutLeaf,,sonic
```

**sonic_lab_links.csv:**
```csv
StartDevice,StartPort,EndDevice,EndPort,BandWidth,VlanID,VlanMode,AutoNeg
str-msn2700-01,Ethernet0,str-7260-10,Ethernet1,40000,1681,Access,on
str-msn2700-01,Ethernet4,str-7260-10,Ethernet2,40000,1682,Access,on
```

### Step 2: LabGraph处理

**创建LabGraph实例：**
```python
lab_graph = LabGraph("/home/cliff/sonic-mgmt/ansible/files/", "lab")
```

**读取CSV (csv_facts):**
```python
{
    "devices": [
        {"Hostname": "str-msn2700-01", "ManagementIp": "10.251.0.188/23", ...},
        {"Hostname": "str-7260-10", "ManagementIp": "10.251.0.13/23", ...}
    ],
    "links": [
        {"StartDevice": "str-msn2700-01", "StartPort": "Ethernet0", 
         "EndDevice": "str-7260-10", "EndPort": "Ethernet1", ...},
        {"StartDevice": "str-msn2700-01", "StartPort": "Ethernet4", ...}
    ]
}
```

**转换为graph_facts:**
```python
{
    "devices": {
        "str-msn2700-01": {
            "Hostname": "str-msn2700-01",
            "ManagementIp": "10.251.0.188/23",
            "mgmtip": "10.251.0.188",
            "ManagementGw": "10.251.0.1",
            "HwSku": "Mellanox-2700",
            "Type": "DevSonic",
            "Os": "sonic",
            "CardType": "Linecard",
            "HwSkuType": "predefined"
        },
        "str-7260-10": {...}
    },
    "links": {
        "str-msn2700-01": {
            "Ethernet0": {
                "peerdevice": "str-7260-10",
                "peerport": "Ethernet1",
                "speed": "40000",
                "autoneg": "on",
                "fec_disable": False
            },
            "Ethernet4": {
                "peerdevice": "str-7260-10",
                "peerport": "Ethernet2",
                "speed": "40000",
                "autoneg": "on",
                "fec_disable": False
            }
        },
        "str-7260-10": {
            "Ethernet1": {
                "peerdevice": "str-msn2700-01",
                "peerport": "Ethernet0",
                ...
            },
            "Ethernet2": {...}
        }
    },
    "port_vlans": {
        "str-msn2700-01": {
            "Ethernet0": {
                "mode": "Access",
                "vlanids": "1681",
                "vlanlist": [1681]
            },
            "Ethernet4": {
                "mode": "Access",
                "vlanids": "1682",
                "vlanlist": [1682]
            }
        },
        "str-7260-10": {...}
    }
}
```

**构建结果 (build_results):**
```python
succeed, results = lab_graph.build_results(["str-msn2700-01"])

results = {
    "device_info": {
        "str-msn2700-01": {
            "Hostname": "str-msn2700-01",
            "mgmtip": "10.251.0.188",
            "HwSku": "Mellanox-2700",
            ...
        }
    },
    "device_conn": {
        "str-msn2700-01": {
            "Ethernet0": {"peerdevice": "str-7260-10", "peerport": "Ethernet1", ...},
            "Ethernet4": {"peerdevice": "str-7260-10", "peerport": "Ethernet2", ...}
        }
    },
    "device_port_vlans": {
        "str-msn2700-01": {
            "Ethernet0": {"mode": "Access", "vlanids": "1681", "vlanlist": [1681]},
            "Ethernet4": {"mode": "Access", "vlanids": "1682", "vlanlist": [1682]}
        }
    },
    "device_vlan_list": {
        "str-msn2700-01": [1681, 1682]
    },
    "device_vlan_range": {
        "str-msn2700-01": ["1681-1682"]
    },
    "device_console_link": {"str-msn2700-01": {}},
    "device_pdu_links": {"str-msn2700-01": {}},
    ...
}
```

### Step 3: Ansible模块封装

**Ansible playbook调用:**
```yaml
- name: Get connection graph facts
  conn_graph_facts:
    hosts: ["str-msn2700-01"]
    filepath: "/path/to/ansible/files/"
    group: "lab"
  register: graph_facts
```

**或者pytest调用:**
```python
conn_graph_facts = localhost.conn_graph_facts(
    hosts=["str-msn2700-01"],
    filepath="/home/cliff/sonic-mgmt/ansible/files/",
    group="lab"
)["ansible_facts"]
```

**模块返回数据:**
```python
{
    "ansible_facts": {
        "device_info": {...},
        "device_conn": {...},
        "device_port_vlans": {...},
        "device_vlan_list": {...},
        "device_vlan_range": {...},
        ...
    }
}
```

### Step 4: Pytest Fixture使用

**Fixture定义:**
```python
@pytest.fixture(scope="module")
def conn_graph_facts(duthosts, localhost):
    return get_graph_facts(duthosts[0], localhost, [dh.hostname for dh in duthosts])
```

**测试用例使用:**
```python
def test_port_connections(duthosts, conn_graph_facts):
    duthost = duthosts[0]
    
    # 获取设备信息
    device_info = conn_graph_facts['device_info'][duthost.hostname]
    assert device_info['HwSku'] == 'Mellanox-2700'
    
    # 获取连接信息
    connections = conn_graph_facts['device_conn'][duthost.hostname]
    eth0_conn = connections['Ethernet0']
    assert eth0_conn['peerdevice'] == 'str-7260-10'
    assert eth0_conn['peerport'] == 'Ethernet1'
    assert eth0_conn['speed'] == '40000'
    
    # 获取VLAN信息
    port_vlans = conn_graph_facts['device_port_vlans'][duthost.hostname]
    eth0_vlan = port_vlans['Ethernet0']
    assert eth0_vlan['mode'] == 'Access'
    assert eth0_vlan['vlanids'] == '1681'
    assert 1681 in eth0_vlan['vlanlist']
```

---

## 总结

### 数据流总结

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. CSV文件 (数据源)                                               │
│    - 设备信息: sonic_lab_devices.csv                              │
│    - 连接信息: sonic_lab_links.csv                                │
│    - 辅助连接: pdu/console/bmc/l1_links.csv                       │
│    格式: 结构化CSV表格                                             │
└──────────────────────────────────────────────────────────────────┘
                            ↓ read_csv_files()
┌──────────────────────────────────────────────────────────────────┐
│ 2. csv_facts (原始数据)                                           │
│    {                                                             │
│      "devices": [{"Hostname": "...", ...}],                      │
│      "links": [{"StartDevice": "...", ...}]                      │
│    }                                                             │
│    格式: 字典列表 (List of Dicts)                                  │
└──────────────────────────────────────────────────────────────────┘
                            ↓ csv_to_graph_facts()
┌──────────────────────────────────────────────────────────────────┐
│ 3. graph_facts (图结构数据)                                       │
│    {                                                             │
│      "devices": {"hostname": {...}},                             │
│      "links": {"hostname": {"port": {...}}},                     │
│      "port_vlans": {"hostname": {"port": {...}}}                 │
│    }                                                             │
│    格式: 嵌套字典 (Nested Dicts)，便于查询                          │
└──────────────────────────────────────────────────────────────────┘
                            ↓ build_results(hostnames)
┌──────────────────────────────────────────────────────────────────┐
│ 4. results (过滤后的结果)                                          │
│    {                                                             │
│      "device_info": {"hostname": {...}},                         │
│      "device_conn": {"hostname": {...}},                         │
│      "device_vlan_list": {"hostname": [...]},                    │
│      ...                                                         │
│    }                                                             │
│    格式: 按设备组织的多个字典                                       │
└──────────────────────────────────────────────────────────────────┘
                            ↓ Ansible module
┌──────────────────────────────────────────────────────────────────┐
│ 5. ansible_facts (Ansible格式)                                   │
│    {                                                             │
│      "ansible_facts": {                                          │
│        "device_info": {...},                                     │
│        "device_conn": {...},                                     │
│        ...                                                       │
│      }                                                           │
│    }                                                             │
└──────────────────────────────────────────────────────────────────┘
                            ↓ pytest fixture
┌──────────────────────────────────────────────────────────────────┐
│ 6. conn_graph_facts (测试用例可用数据)                             │
│    直接使用的facts字典                                             │
│    {                                                             │
│      "device_info": {...},                                       │
│      "device_conn": {...},                                       │
│      ...                                                         │
│    }                                                             │
└──────────────────────────────────────────────────────────────────┘
```

### 关键设计模式

1. **分层架构：** 数据源 → 处理层 → 封装层 → 使用层
2. **关注点分离：** 每层有明确职责
3. **数据转换：** CSV → List[Dict] → Dict[Dict] → 结构化Facts
4. **缓存优化：** 端口映射缓存，避免重复计算
5. **灵活查询：** 支持单主机、多主机、整图查询
6. **子图提取：** build_results提取指定设备的子图，按需返回数据
7. **数据分类：** 返回结果分为节点属性、边、边的属性、派生数据四类
8. **图的存储：** 
   - 网络连接：双向存储（无向边的实现）
   - 管理连接：单向存储（有向边）
9. **错误处理：** 多级错误处理和验证

### 数据处理要点

1. **IP地址处理：** 自动解析CIDR，生成mgmtip和网关
2. **端口名称转换：** Sonic设备的端口别名自动转换为端口名
3. **VLAN范围处理：** 字符串范围转换为列表，支持复杂范围
4. **双向连接：** 网络连接自动创建双向映射（物理上无向，存储为两条有向边）
5. **单向连接：** PDU/Console/BMC连接仅存储单向（从被管理设备到管理设备）
6. **类型兼容：** Python 2/3兼容性处理
7. **图组管理：** 支持多套测试环境的独立配置
8. **子图提取：** build_results只返回查询设备的子图，不是整个lab的完整图

### 使用场景

1. **测试用例：** 获取DUT和Fanout的拓扑信息
2. **配置部署：** 根据拓扑自动配置设备
3. **连接验证：** 验证物理连接是否正确
4. **资源管理：** 了解可用的测试设备和端口
5. **故障诊断：** 快速定位连接问题

### 优势

1. **数据集中管理：** 所有拓扑信息在CSV文件中
2. **版本控制友好：** CSV文件易于diff和merge
3. **可扩展：** 易于添加新的连接类型
4. **复用性强：** 同一套数据供Ansible和pytest使用
5. **类型安全：** 多层数据验证和类型转换

---

---

## 附录：连接图的图论结构

### 图的定义

在sonic-mgmt的连接图（Connection Graph）中，使用的是**有向属性图（Directed Attributed Graph）**模型：

```
G = (V, E)
其中：
- V = 节点集合（Vertices/Nodes）
- E = 边集合（Edges/Links）
```

### 节点（Nodes/Vertices）

**节点代表测试环境中的所有物理设备和虚拟设备。**

#### 节点类型及示例

| 节点类型 | Type字段 | 说明 | 示例 |
|---------|---------|------|------|
| **DUT设备** | `DevSonic` | 被测试的SONiC交换机 | `str-msn2700-01` |
| **Fanout Root** | `FanoutRoot` | 根Fanout交换机（连接到上游网络） | `str-7260-11` |
| **Fanout Leaf** | `FanoutLeaf` | 叶Fanout交换机（连接到DUT） | `str-7260-10` |
| **测试服务器** | `Server` | PTF测试服务器 | `str-acs-serv-01` |
| **PDU** | `Pdu` | 电源分配单元 | `pdu-1`, `pdu-2` |
| **Console服务器** | `ConsoleServer` | 串口控制台服务器 | `console-1`, `console-2` |
| **BMC** | `Bmc` | 带外管理控制器 | `bmc-server-01` |
| **L1交换机** | `L1Switch` | Layer 1物理层交换机 | `l1-switch-01` |
| **流量生成器** | `Tester` | IXIA/SNAPPI测试设备 | `ixia-chassis-01` |

#### 节点属性

每个节点包含以下属性（存储在`graph_facts["devices"]`中）：

```python
{
    "Hostname": "str-msn2700-01",           # 唯一标识符
    "ManagementIp": "10.251.0.188/23",     # 管理IP
    "mgmtip": "10.251.0.188",              # 解析后的IP
    "ManagementGw": "10.251.0.1",          # 管理网关
    "HwSku": "Mellanox-2700",              # 硬件型号
    "Type": "DevSonic",                     # 设备类型
    "Os": "sonic",                          # 操作系统
    "Protocol": "ssh",                      # 管理协议
    "CardType": "Linecard",                 # 卡类型
    "HwSkuType": "predefined"               # 硬件配置类型
}
```

### 边（Edges/Links）

**边代表设备之间的物理连接或逻辑关联。**

#### 边的类型

sonic-mgmt支持多种类型的边，分别存储在不同的数据结构中：

##### 1. 网络连接边（Network Links）

**最重要的边类型**，代表设备之间通过网络端口的物理连接。

**数据来源：** `sonic_lab_links.csv`

**存储位置：** `graph_facts["links"]`

**边的属性：**
```python
{
    "peerdevice": "str-7260-10",      # 对端设备
    "peerport": "Ethernet1",          # 对端端口
    "speed": "40000",                 # 带宽（Mbps）
    "autoneg": "on",                  # 自动协商
    "fec_disable": False,             # FEC是否禁用
    "mac": "00:11:22:33:44:55"       # MAC地址（可选）
}
```

**边的方向性：**
- 网络连接是**双向的**（无向边）
- 但在数据结构中存储为**两条有向边**：
```python
links["str-msn2700-01"]["Ethernet0"] → links["str-7260-10"]["Ethernet1"]
links["str-7260-10"]["Ethernet1"] → links["str-msn2700-01"]["Ethernet0"]
```

**示例：**
```
str-msn2700-01:Ethernet0 ←→ str-7260-10:Ethernet1
    属性: 40G, Access VLAN 1681, AutoNeg on
```

##### 2. PDU连接边（PDU Links）

代表设备的电源连接关系。

**数据来源：** `sonic_lab_pdu_links.csv`

**存储位置：** `graph_facts["pdu_links"]`

**边的属性：**
```python
{
    "peerdevice": "pdu-2",           # PDU设备名
    "peerport": "5",                 # PDU端口号
    "feed": "A"                      # 电源馈线（A/B/N/A）
}
```

**特殊性：** 支持双电源（PSU A/B）
```
str-msn2700-01:PSU1:A → pdu-2:5
str-msn2700-01:PSU1:B → pdu-2:6
```

##### 3. Console连接边（Console Links）

代表串口控制台连接。

**数据来源：** `sonic_lab_console_links.csv`

**存储位置：** `graph_facts["console_links"]`

**边的属性：**
```python
{
    "peerdevice": "console-1",       # Console服务器
    "peerport": "ttyS3",             # 串口端口
    "baud_rate": "9600",             # 波特率
    "proxy": "none",                 # 代理设置
    "type": "ssh",                   # 连接类型
    "menu_type": "cisco"             # 菜单类型
}
```

##### 4. BMC连接边（BMC Links）

代表带外管理连接。

**数据来源：** `sonic_lab_bmc_links.csv`

**存储位置：** `graph_facts["bmc_links"]`

**边的属性：**
```python
{
    "peerdevice": "bmc-server-01",   # BMC服务器
    "peerport": "eth1",              # BMC端口
    "bmc_ip": "192.168.1.100"        # BMC IP地址
}
```

##### 5. L1连接边（L1 Links）

代表通过L1物理层交换机的连接。

**数据来源：** `sonic_lab_l1_links.csv`

**存储位置：** 
- `graph_facts["from_l1_links"]` - L1到设备
- `graph_facts["to_l1_links"]` - 设备到L1

**边的属性：**
```python
# 设备 → L1交换机
{
    "peerdevice": "l1-switch-01",
    "peerport": ["1", "2", "3", "4"]  # 可以是多通道
}

# L1交换机 → 设备
{
    "peerdevice": "str-msn2700-01",
    "peerport": "Ethernet0"
}
```

### 边的附加属性

除了连接信息，边还包含VLAN和VRF等网络配置：

#### VLAN属性

存储在 `graph_facts["port_vlans"]` 中：

```python
{
    "mode": "Access",                    # Access或Trunk
    "vlanids": "1681",                   # VLAN ID字符串
    "vlanlist": [1681]                   # VLAN ID列表
}
```

对于Trunk模式：
```python
{
    "mode": "Trunk",
    "vlanids": "1681-1712",
    "vlanlist": [1681, 1682, ..., 1712]
}
```

#### VRF属性

存储在 `graph_facts["port_vrfs"]` 中：

```python
{
    "name": "Vrf_01"                     # VRF名称
}
```

### 图的拓扑结构

典型的测试环境拓扑（以T0拓扑为例）：

```
                    [Internet]
                        |
                        |
                  ┌─────────────┐
                  │  FanoutRoot │ (str-7260-11)
                  │  (上游交换机) │
                  └─────────────┘
                        |
                        | Trunk (VLAN 1681-1712)
                        |
                  ┌─────────────┐
                  │  FanoutLeaf │ (str-7260-10)
                  │  (下游交换机) │
                  └─────────────┘
                        |
         ┌──────────────┼──────────────┐
         |              |              |
    Access VLAN    Access VLAN    Access VLAN
     1681-1690      1691-1700      1701-1712
         |              |              |
    ┌─────────┐   ┌─────────┐   ┌─────────┐
    │   DUT   │   │   DUT   │   │  Server │
    │ (SONiC) │   │ (SONiC) │   │  (PTF)  │
    └─────────┘   └─────────┘   └─────────┘
         |              |              |
      (Console)      (PDU-A)       (PDU-B)
         |              |              |
    ┌─────────┐   ┌─────────┐   ┌─────────┐
    │Console  │   │  PDU-1  │   │  PDU-2  │
    │ Server  │   │         │   │         │
    └─────────┘   └─────────┘   └─────────┘
```

### 图的表示方法

#### 1. 邻接表表示（实际使用）

graph_utils.py使用邻接表存储图：

```python
graph_facts = {
    "devices": {
        "device1": {...},
        "device2": {...}
    },
    "links": {
        "device1": {
            "port1": {"peerdevice": "device2", "peerport": "port2", ...},
            "port2": {...}
        },
        "device2": {
            "port2": {"peerdevice": "device1", "peerport": "port1", ...}
        }
    }
}
```

**优点：**
- 快速查询：O(1)时间查找某个端口的对端
- 节省空间：只存储实际存在的连接
- 易于遍历：可以快速遍历某个设备的所有连接

#### 2. 边列表表示（CSV文件）

CSV文件使用边列表存储：

```csv
StartDevice,StartPort,EndDevice,EndPort,BandWidth,VlanID,VlanMode
device1,port1,device2,port2,40000,1681,Access
device1,port3,device3,port1,100000,1682,Access
```

**优点：**
- 人类可读
- 易于编辑和维护
- 适合版本控制

### 图的操作

#### 1. 图的查询

```python
# 查找设备的所有邻居
neighbors = graph_facts["links"]["str-msn2700-01"]

# 查找特定端口的对端
peer = graph_facts["links"]["str-msn2700-01"]["Ethernet0"]
peer_device = peer["peerdevice"]
peer_port = peer["peerport"]
```

#### 2. 图的过滤

```python
# 过滤出多个设备之间的连接
def _filter_linked_ports(self, hostnames):
    hostnames_set = set(hostnames)
    filtered = {}
    for hostname in hostnames:
        for port, link in self.graph_facts["linked_ports"][hostname].items():
            if link["peerdevice"] in hostnames_set:
                filtered[hostname][port] = link
    return filtered
```

#### 3. 子图提取

`build_results(hostnames)` 方法提取指定设备的子图：

```python
# 输入：设备名列表
hostnames = ["str-msn2700-01", "str-7260-10"]

# 输出：包含这些设备及其连接的子图
subgraph = {
    "device_info": {设备信息},
    "device_conn": {设备之间的连接},
    "device_port_vlans": {端口VLAN配置},
    ...
}
```

### 图的应用场景

1. **拓扑验证**：验证物理连接是否符合预期
2. **路径查找**：找出数据包从源到目的地的路径
3. **连通性检查**：检查两个设备是否连通
4. **配置生成**：基于拓扑自动生成设备配置
5. **测试用例生成**：根据拓扑结构生成测试场景
6. **故障诊断**：定位连接问题

### 图的扩展性

添加新的边类型（如光纤连接、无线连接等）：

1. 在 `SUPPORTED_CSV_FILES` 中添加新文件类型
2. 在 `csv_to_graph_facts()` 中添加解析逻辑
3. 在 `build_results()` 中添加结果构建逻辑

```python
SUPPORTED_CSV_FILES = {
    "devices": "sonic_{}_devices.csv",
    "links": "sonic_{}_links.csv",
    # ... 现有类型 ...
    "fiber_links": "sonic_{}_fiber_links.csv",  # 新增
}
```

---

**文档版本：** 1.0  
**创建时间：** 2025-12-14  
**适用版本：** sonic-mgmt master分支
