"""
Example: How to use serial_link connection info in pytest

This file demonstrates how to get and use serial link connection info through conn_graph_facts fixture
"""
import pytest
import logging

logger = logging.getLogger(__name__)


@pytest.mark.topology('any')
def test_get_serial_link_info(duthosts, conn_graph_facts):
    """
    Example test: Get serial link connection info for the device
    
    Args:
        duthosts: DUT host list
        conn_graph_facts: Connection graph info fixture, contains all connection info defined in CSV files
    """
    # Get the hostname of the first DUT
    get_duthosts = duthosts
    duthost = duthosts[0]
    dut_hostname = duthost.hostname
    device_serial_link = conn_graph_facts["device_serial_link"]
    
    # Check all devices in device_serial_link
    all_serial_devices = list(device_serial_link.keys())
    leaf_27_serial = device_serial_link.get('bjw3-can-720dt-leaf-27', {})
    
    logger.warning(f"Testing serial link for DUT: {dut_hostname}")
    logger.warning(f"All devices with serial links: {all_serial_devices}")
    logger.warning(f"bjw3-can-720dt-leaf-27 serial links: {leaf_27_serial}")

    assert 1 == 0, "Intentional fail to see all variables"

