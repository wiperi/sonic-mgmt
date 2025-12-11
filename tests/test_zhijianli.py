import ipaddress
import json
import logging
import pytest
import time
from ptf import testutils
# from scapy import *
# from scapy.contrib import dhcp6

from tests.common.fixtures.ptfhost_utils import copy_arp_responder_py  # noqa F401

pytestmark = [
    pytest.mark.topology('any'),
]


def test_zhijianli(duthost, tbinfo, ptfhost, ptfadapter, request):
    import pdb; pdb.set_trace()
    bgp_facts = duthost.bgp_facts()['ansible_facts']

    running_config_facts = duthost.get_running_config_facts()
    lo_facts = running_config_facts.get('LOOPBACK_INTERFACE')
    lo_ipv4_addr = list()
    lo_ipv6_addr = list()
    for lo_name in lo_facts:
        for ip_addr in lo_facts[lo_name].keys():
            ip_addr = ip_addr.split('/')[0]
            if ipaddress.ip_address(ip_addr).version == 4:
                lo_ipv4_addr.append(ip_addr)
            else:
                lo_ipv6_addr.append(ip_addr)
    vlan_intf_facts = running_config_facts.get('VLAN_INTERFACE')
    vlan_ipv4_addr = list()
    vlan_ipv6_addr = list()
    for vlan_name in vlan_intf_facts:
        for ip_addr in vlan_intf_facts[vlan_name].keys():
            ip_addr = ip_addr.split('/')[0]
            if ipaddress.ip_address(ip_addr).version == 4:
                vlan_ipv4_addr.append(ip_addr)
            else:
                vlan_ipv6_addr.append(ip_addr)
    import pdb; pdb.set_trace()
    time.sleep(1)


def construct_dhcpv6_solicit_packet():
    # DHCPv6 Solicit
    dhcpv6_solicit = dhcp6.DHCP6_Solicit()
    dhcpv6_solicit_msg_type = dhcp6.DHCP6OptOptReq()
    dhcpv6_solicit_msg_type.optreqtype = 6

    dhcpv6_solicit /= dhcpv6_solicit_msg_type

    return dhcpv6_solicit


