"""
Demo: Two ways to get DUT's neighbor devices in tests

Neighbor devices are defined in topology files: ansible/vars/topo_*.yml
"""
import pytest
import logging

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.topology("any")]

class TestGetNeighborDemo:
    """Demo class showing two ways to get neighbor devices"""

    def test_get_neighbors_via_nbrhosts(self, nbrhosts, tbinfo, adhoc):

        breakpoint()

        """
        方式一：使用 nbrhosts fixture（推荐）

        nbrhosts 是一个字典:
        - key: neighbor 名称 (如 "ARISTA01T1")
        - value: NeighborDevice 对象，包含 'host' 和 'conf'
        """
        logger.info("=== 方式一: 使用 nbrhosts fixture ===")

        if not nbrhosts:
            logger.warning("No neighbors found in this topology")
            pytest.skip("No VMs in this topology")

        # 打印所有 neighbor 名称
        logger.info(f"All neighbor names: {list(nbrhosts.keys())}")

        # 遍历所有 neighbors
        for nbr_name, nbr_device in nbrhosts.items():
            logger.info(f"\n--- Neighbor: {nbr_name} ---")

            # 获取 neighbor 的 host 对象 (EosHost/SonicHost/CiscoHost)
            nbr_host = nbr_device['host']

            # 获取 neighbor 的配置信息
            nbr_conf = nbr_device['conf']

            logger.info(f"Neighbor config: {nbr_conf}")

            # 在 neighbor 上执行命令示例
            # result = nbr_host.command("show version")
            # logger.info(f"Version output: {result['stdout']}")

    def test_get_neighbors_via_tbinfo(self, tbinfo):
        """
        方式二：通过 tbinfo 获取拓扑信息

        tbinfo['topo']['properties']['topology']['VMs'] 包含 VM 定义
        tbinfo['topo']['properties']['configuration'] 包含详细配置
        """
        logger.info("=== 方式二: 使用 tbinfo fixture ===")

        # 检查是否有 VMs
        if 'VMs' not in tbinfo['topo']['properties']['topology']:
            logger.warning("No VMs in topology")
            pytest.skip("No VMs in this topology")

        # 获取所有 VMs 的定义
        vms = tbinfo['topo']['properties']['topology']['VMs']

        if not vms:
            pytest.skip("VMs is empty")

        logger.info(f"All VM names: {list(vms.keys())}")

        # 遍历 VMs 获取基本信息
        for vm_name, vm_info in vms.items():
            logger.info(f"\n--- VM: {vm_name} ---")
            logger.info(f"  vlans: {vm_info.get('vlans', [])}")
            logger.info(f"  vm_offset: {vm_info.get('vm_offset', 'N/A')}")

        # 获取 neighbor 的详细配置
        configurations = tbinfo['topo']['properties'].get('configuration', {})

        for vm_name in vms.keys():
            if vm_name in configurations:
                vm_config = configurations[vm_name]
                logger.info(f"\n--- {vm_name} Configuration ---")

                # BGP 配置
                if 'bgp' in vm_config:
                    logger.info(f"  BGP ASN: {vm_config['bgp'].get('asn', 'N/A')}")
                    logger.info(f"  BGP Peers: {vm_config['bgp'].get('peers', {})}")

                # 接口配置
                if 'interfaces' in vm_config:
                    logger.info(f"  Interfaces: {list(vm_config['interfaces'].keys())}")

    def test_combined_example(self, nbrhosts, tbinfo):
        """
        组合使用示例：使用 tbinfo 获取配置，用 nbrhosts 执行操作
        """
        logger.info("=== 组合使用示例 ===")

        if not nbrhosts:
            pytest.skip("No VMs in this topology")

        configurations = tbinfo['topo']['properties'].get('configuration', {})

        for nbr_name, nbr_device in nbrhosts.items():
            # 从 tbinfo 获取配置
            nbr_conf_from_tbinfo = configurations.get(nbr_name, {})

            # 从 nbrhosts 获取配置（两者应该相同）
            nbr_conf_from_fixture = nbr_device['conf']

            logger.info(f"\nNeighbor: {nbr_name}")
            logger.info(f"  Config from tbinfo: {nbr_conf_from_tbinfo.get('bgp', {}).get('asn', 'N/A')}")
            logger.info(f"  Config from nbrhosts: {nbr_conf_from_fixture.get('bgp', {}).get('asn', 'N/A')}")

            # 使用 nbrhosts 的 host 对象执行操作
            # nbr_host = nbr_device['host']
            # nbr_host.command("show ip bgp summary")
