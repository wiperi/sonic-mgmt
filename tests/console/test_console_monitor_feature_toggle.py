"""
Test cases for console monitor feature toggle functionality.

These tests verify:
1. DCE feature enable/disable on DUT
2. DTE feature enable/disable on neighbor VM
3. Service lifecycle and resource management

Testbed architecture:
    DUT (Console Switch, DCE) <--Serial--> Fanout <--socat/TCP--> VM Host <--virsh serial--> Neighbor VM (DTE)
"""
import logging
import time
from typing import List, Optional

import pytest

from tests.common.devices.sonic import SonicHost
from tests.common.devices.fanout import FanoutHost
from tests.common.helpers.assertions import pytest_assert

from tests.console.test_console_monitor import (
    BridgeManager,
    get_serial_fanout_for_line,
    get_neighbor_by_name,
)


logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.topology("any")]


# ==================== Helper Functions ====================

def parse_active_service_link_ids(systemctl_output: str, service_pattern: str) -> set[int]:
    """
    Parse systemctl list-units output to extract link IDs of active services.

    Args:
        systemctl_output: Output from `systemctl list-units 'service_pattern'`
        service_pattern: Service name pattern (e.g., 'console-monitor-proxy@')

    Returns:
        set[int]: Set of link IDs that have active services

    Example input:
        UNIT                             LOAD   ACTIVE SUB     DESCRIPTION
        console-monitor-proxy@1.service  loaded active running Console Monitor Proxy Service for port 1
        console-monitor-proxy@10.service loaded active running Console Monitor Proxy Service for port 10
    """
    import re
    active_link_ids = set()

    # Match lines like: console-monitor-proxy@1.service loaded active running ...
    pattern = rf'{re.escape(service_pattern)}(\d+)\.service\s+loaded\s+active\s+running'

    for match in re.finditer(pattern, systemctl_output):
        link_id = int(match.group(1))
        active_link_ids.add(link_id)

    return active_link_ids


def get_active_console_monitor_services(duthost: SonicHost, service_type: str) -> set[int]:
    """
    Get link IDs of active console-monitor services.

    Args:
        duthost: DUT host object
        service_type: 'proxy' or 'pty-bridge'

    Returns:
        set[int]: Set of link IDs with active services
    """
    service_pattern = f"console-monitor-{service_type}@"
    result = duthost.shell(
        f"systemctl list-units '{service_pattern}*.service'",
        module_ignore_errors=True
    )
    return parse_active_service_link_ids(result['stdout'], service_pattern)


# ==================== Fixtures ====================

@pytest.fixture(scope="module")
def configured_lines(console_facts: dict) -> list[int]:
    """
    Get list of configured console line IDs from console_facts.

    Returns:
        list[int]: List of configured line IDs (e.g., [1, 2, 3])
    """
    lines = console_facts.get('lines', {})
    pytest_assert(len(lines) > 0, "No console lines configured on DUT")
    return [int(line_id) for line_id in lines.keys()]


@pytest.fixture(scope="function")
def bridge_manager(duthost, fanouthosts, nbrhosts, vmhost):
    """
    Fixture that provides a BridgeManager and ensures cleanup after test.
    """
    manager = BridgeManager(duthost, fanouthosts, nbrhosts, vmhost)
    yield manager
    manager.cleanup_all_bridges()


@pytest.fixture(scope="function")
def cleanup_console_sessions(duthost, console_facts):
    """
    Cleanup fixture to clear all console sessions after each test.
    """
    yield

    # Cleanup on DUT side - clear any active lines
    try:
        for line_id, line_info in console_facts.get('lines', {}).items():
            if line_info.get('state') == 'BUSY':
                duthost.shell(f"sudo consutil clear {line_id}", module_ignore_errors=True)
                logger.info(f"Cleared busy line {line_id} on DUT")
    except Exception as e:
        logger.warning(f"Failed to cleanup console lines on DUT: {e}")


@pytest.fixture(scope="function")
def ensure_console_enabled(duthost):
    """
    Fixture that ensures console feature is enabled before and after test.

    This fixture:
    1. Enables console feature before test starts
    2. Yields control to the test
    3. Re-enables console feature after test completes (even if test fails)
    """
    # Setup: Enable console feature
    logger.info("Fixture setup: Enabling DCE feature...")
    duthost.shell("sudo config console enable", module_ignore_errors=True)
    time.sleep(2)

    yield

    # Teardown: Always re-enable console feature (even if test fails)
    logger.info("Fixture teardown: Re-enabling DCE feature...")
    duthost.shell("sudo config console enable", module_ignore_errors=True)
    time.sleep(2)


# ==================== Test Cases ====================

def test_dce_feature_disabled(
    duthost: SonicHost,
    configured_lines: list[int],
    ensure_console_enabled,
    cleanup_console_sessions
):
    """
    Test DCE feature disable functionality.

    Verify that when DCE feature is disabled:
    1. All console-monitor services are stopped
    2. PTY links are removed
    3. Serial devices are released

    Test steps:
    1. Verify DCE feature is enabled and services are running (setup by fixture)
    2. Verify PTY links exist and serial device is in use for all lines
    3. Disable DCE feature
    4. Verify all services are stopped and resources are released for all lines
    5. Re-enable DCE feature (handled by fixture teardown)
    """

    # Step 1: Verify console-monitor-dce.service is running (enabled by fixture)
    logger.info("Step 1: Verifying console-monitor-dce.service is running...")
    pytest_assert(
        duthost.is_host_service_running("console-monitor-dce"),
        "console-monitor-dce.service should be running when feature is enabled"
    )

    # Step 2: Verify all console-monitor-pty-bridge@{link_id}.service are running
    logger.info("Step 2: Verifying console-monitor-pty-bridge services are running for all lines...")
    active_pty_bridge_ids = get_active_console_monitor_services(duthost, 'pty-bridge')
    expected_link_ids = set(configured_lines)
    missing_pty_bridge = expected_link_ids - active_pty_bridge_ids
    pytest_assert(
        len(missing_pty_bridge) == 0,
        f"console-monitor-pty-bridge services should be running for all lines. "
        f"Missing: {missing_pty_bridge}"
    )

    # Step 3: Verify all console-monitor-proxy@{link_id}.service are running
    logger.info("Step 3: Verifying console-monitor-proxy services are running for all lines...")
    active_proxy_ids = get_active_console_monitor_services(duthost, 'proxy')
    missing_proxy = expected_link_ids - active_proxy_ids
    pytest_assert(
        len(missing_proxy) == 0,
        f"console-monitor-proxy services should be running for all lines. "
        f"Missing: {missing_proxy}"
    )

    # Step 4: Verify PTY links exist for all lines
    logger.info("Step 4: Verifying PTY links exist for all lines...")
    device_prefix = duthost._get_serial_device_prefix()
    # Build a single command to check all PTY links at once
    pty_links = []
    serial_devices = []
    for link_id in configured_lines:
        pty_links.append(f"{device_prefix}{link_id}-PTS")
        pty_links.append(f"{device_prefix}{link_id}-PTM")
        serial_devices.append(f"{device_prefix}{link_id}")
    # Build test command: test -e file1 && test -e file2 && ...
    test_exists_cmd = ' && '.join([f'test -e {link}' for link in pty_links])
    result = duthost.shell(test_exists_cmd, module_ignore_errors=True)
    pytest_assert(
        result['rc'] == 0,
        f"All PTY links should exist. Missing links detected."
    )

    # Step 5: Disable DCE feature
    logger.info("Step 5: Disabling DCE feature...")
    duthost.shell("sudo config console disable")
    time.sleep(2)  # Wait for services to stop

    # Step 6: Verify console-monitor-dce.service is still running
    logger.info("Step 6: Verifying console-monitor-dce.service is still running...")
    pytest_assert(
        duthost.is_host_service_running("console-monitor-dce"),
        "console-monitor-dce.service should be running when feature is disabled"
    )

    # Step 7: Verify all console-monitor-pty-bridge@{link_id}.service are stopped
    logger.info("Step 7: Verifying console-monitor-pty-bridge services are stopped for all lines...")
    active_pty_bridge_ids = get_active_console_monitor_services(duthost, 'pty-bridge')
    unexpected_pty_bridge = expected_link_ids & active_pty_bridge_ids
    pytest_assert(
        len(unexpected_pty_bridge) == 0,
        f"console-monitor-pty-bridge services should be stopped for all lines. "
        f"Still running: {unexpected_pty_bridge}"
    )

    # Step 8: Verify all console-monitor-proxy@{link_id}.service are stopped
    logger.info("Step 8: Verifying console-monitor-proxy services are stopped for all lines...")
    active_proxy_ids = get_active_console_monitor_services(duthost, 'proxy')
    unexpected_proxy = expected_link_ids & active_proxy_ids
    pytest_assert(
        len(unexpected_proxy) == 0,
        f"console-monitor-proxy services should be stopped for all lines. "
        f"Still running: {unexpected_proxy}"
    )

    # Step 9: Verify PTY links are removed for all lines
    logger.info("Step 9: Verifying PTY links are removed for all lines...")
    # Build test command: test -e file1 || test -e file2 || ...
    test_not_exists_cmd = ' || '.join([f'test -e {link}' for link in pty_links])
    result = duthost.shell(test_not_exists_cmd, module_ignore_errors=True)
    pytest_assert(
        result['rc'] != 0,
        f"All PTY links should be removed after feature disabled."
    )

    # Step 10: Verify serial devices are not in use by console-monitor for all lines
    logger.info("Step 10: Verifying serial devices are released for all lines...")
    result = duthost.shell(f"sudo lsof {' '.join(serial_devices)} 2>/dev/null", module_ignore_errors=True)
    pytest_assert(
        result['stdout'] == "",
        f"Serial devices should not be in use by console-monitor (python3)"
    )

    # Note: Cleanup (re-enabling DCE feature) is handled by ensure_console_enabled fixture
    logger.info("Test passed: DCE feature disable functionality working correctly")

