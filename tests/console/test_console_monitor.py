"""
Test cases for console monitor DCE/DTE functionality.

These tests verify:
1. Console monitor heartbeat detection (DCE side on DUT, DTE side on fanout)
2. Console line status reporting via 'show line -b'
3. Data passthrough when connected to console line
"""
import logging
import time
import pexpect
import pytest

from tests.common.devices.fanout import FanoutHost
from tests.common.devices.sonic import SonicHost
from tests.common.helpers.assertions import pytest_assert
from tests.common.utilities import wait_until

# Use 'any' topology to run tests on any testbed (including virtual and physical)
pytestmark = [pytest.mark.topology("any")]

logger = logging.getLogger(__name__)

# Constants
HEARTBEAT_TIMEOUT_SEC = 15  # Time for heartbeat to timeout and line status to become 'Unknown'
HEARTBEAT_DETECT_SEC = 2    # Time for heartbeat to be detected and line status to become 'Up'


# ==================== Fixtures ====================

@pytest.fixture(scope="module")
def console_fanout(duthosts, fanouthosts):
    breakpoint()
    """
    Find the console fanout host in the testbed.

    Returns:
        FanoutHost: The first console fanout found that is a SonicHost
    """
    console_fanouts = [
        fanout for fanout in fanouthosts.values()
        if isinstance(fanout.host, SonicHost) and fanout.host.is_console_switch()
    ]

    if not console_fanouts:
        pytest.skip("No console fanout found in testbed - test requires physical hardware")

    fanout = console_fanouts[0]
    logger.info(f"Found console fanout: {fanout.hostname}")
    return fanout


@pytest.fixture(scope="module")
def dut_console_lines(duthosts, console_fanout):
    """
    Get the console line mappings between DUT and fanout.

    Returns:
        list: List of tuples (fanout_port, dut_port, baud_rate) for lines connected to the DUT
    """
    dut_host = duthosts[0]
    lines = [
        (fanout_port, mapping.dut_port, mapping.baud_rate)
        for fanout_port, mapping in console_fanout.serial_port_map.items()
        if mapping is not None and mapping.dut_name == dut_host.hostname
    ]

    if not lines:
        pytest.skip(f"No console lines found between DUT {dut_host.hostname} and fanout {console_fanout.hostname}")

    logger.info(f"Found {len(lines)} console lines: {lines}")
    return lines


@pytest.fixture(scope="function")
def dce_service_is_running(duthosts):
    """
    Verify console-monitor-dce service is running on DUT.

    This fixture:
    1. Verifies console feature is enabled in CONFIG_DB
    2. Verifies console lines are configured
    3. Verifies console-monitor-dce.service is running
    """
    duthost = duthosts[0]

    # Check if console feature is enabled in CONFIG_DB
    console_switch_config = duthost.shell(
        "sonic-db-cli CONFIG_DB HGET 'CONSOLE_SWITCH|console_mgmt' 'enabled'",
        module_ignore_errors=True
    )
    pytest_assert(
        console_switch_config['rc'] == 0 and console_switch_config['stdout'].strip().lower() == 'yes',
        "Console feature is not enabled in CONFIG_DB (CONSOLE_SWITCH|console_mgmt enabled != yes)"
    )
    logger.info("Console feature is enabled in CONFIG_DB")

    # Check console lines are configured (at least 1 line)
    console_facts = duthost.console_facts()['ansible_facts']['console_facts']
    configured_lines = console_facts.get('lines', {})
    pytest_assert(
        len(configured_lines) > 0,
        "No console lines configured on DUT"
    )
    logger.info(f"Found {len(configured_lines)} configured console lines: {list(configured_lines.keys())}")

    # Check console-monitor-dce service is running
    pytest_assert(
        duthost.is_host_service_running("console-monitor-dce"),
        "console-monitor-dce.service is not running on DUT"
    )
    logger.info("console-monitor-dce.service is running")

    yield

    # Cleanup: ensure no active console sessions after test
    logger.info("Cleaning up console sessions after test")


@pytest.fixture(scope="function")
def cleanup_console_sessions(duthosts, console_fanout):
    """
    Cleanup fixture to ensure console sessions are cleaned up after each test.
    """
    yield

    # Cleanup on fanout side
    try:
        if isinstance(console_fanout.host, SonicHost):
            console_fanout.host.cleanup_all_console_sessions()
            logger.info("Cleaned up all console sessions on fanout")
    except Exception as e:
        logger.warning(f"Failed to cleanup console sessions on fanout: {e}")

    # Cleanup on DUT side - clear any active lines
    duthost = duthosts[0]
    try:
        console_facts = duthost.console_facts()['ansible_facts']['console_facts']
        for line_id, line_info in console_facts.get('lines', {}).items():
            if line_info.get('state') == 'BUSY':
                duthost.shell(f"sudo consutil clear {line_id}", module_ignore_errors=True)
                logger.info(f"Cleared busy line {line_id} on DUT")
    except Exception as e:
        logger.warning(f"Failed to cleanup console lines on DUT: {e}")


# ==================== Helper Functions ====================

def get_line_status(duthost, line_id):
    """
    Get the status of a specific console line.

    Args:
        duthost: DUT host object
        line_id: Console line ID (e.g., "1", "2")

    Returns:
        str: Line status ('Up', 'Unknown', 'Down', etc.) or None if not found
    """
    console_facts = duthost.console_facts()['ansible_facts']['console_facts']
    line_info = console_facts.get('lines', {}).get(str(line_id), {})
    return line_info.get('remote_device_state')


def get_all_line_statuses(duthost):
    """
    Get status of all console lines.

    Returns:
        dict: {line_id: status} for all lines
    """
    console_facts = duthost.console_facts()['ansible_facts']['console_facts']
    return {
        line_id: line_info.get('remote_device_state')
        for line_id, line_info in console_facts.get('lines', {}).items()
    }


def wait_for_line_status(duthost, line_id, expected_status, timeout=20):
    """
    Wait for a console line to reach expected status.

    Args:
        duthost: DUT host object
        line_id: Console line ID
        expected_status: Expected status string
        timeout: Maximum wait time in seconds

    Returns:
        bool: True if status reached, False if timeout
    """
    def check_status():
        status = get_line_status(duthost, line_id)
        logger.debug(f"Line {line_id} status: {status}")
        return status == expected_status

    return wait_until(timeout, 1, 0, check_status)


# ==================== Test Cases ====================

def test_console_monitor_heartbeat_detection(
    duthosts, console_fanout, dut_console_lines,
    dce_service_is_running, cleanup_console_sessions
):
    breakpoint()
    """
    Test console monitor heartbeat detection functionality.

    Test steps:
    1. Wait for heartbeat timeout, verify all lines show 'Unknown' status
    2. Enable heartbeat on fanout side for line 1
    3. Verify line 1 status changes to 'Up', other lines remain 'Unknown'
    4. Disable heartbeat on fanout side
    5. Verify line 1 remains 'Up' briefly (grace period)
    6. Wait for heartbeat timeout, verify line 1 returns to 'Unknown'
    """
    duthost = duthosts[0]
    fanout_host = console_fanout.host

    # Get first available line for testing
    fanout_port, dut_port, baud_rate = dut_console_lines[0]
    target_line = str(dut_port)
    logger.info(f"Testing with line {target_line} (fanout port {fanout_port}, baud rate {baud_rate})")

    # Step 1: Wait for heartbeat timeout and verify all lines show 'Unknown'
    logger.info(f"Step 1: Waiting {HEARTBEAT_TIMEOUT_SEC}s for heartbeat timeout...")
    time.sleep(HEARTBEAT_TIMEOUT_SEC)

    all_statuses = get_all_line_statuses(duthost)
    logger.info(f"All line statuses after timeout: {all_statuses}")

    for line_id, status in all_statuses.items():
        pytest_assert(
            status == 'Unknown',
            f"Line {line_id} should be 'Unknown' after heartbeat timeout, but got '{status}'"
        )

    # Step 2: Enable heartbeat on fanout side for target line
    logger.info(f"Step 2: Enabling heartbeat on fanout for line {target_line}...")
    fanout_host.shell("sudo config console heartbeat enable", module_ignore_errors=True)

    # Start console-monitor in DTE mode on fanout
    device_path = fanout_host._get_serial_device_path(fanout_port)
    fanout_host.shell(
        f"sudo console-monitor dte {device_path} &",
        module_ignore_errors=True
    )
    logger.info(f"Started console-monitor DTE on {device_path}")

    # Step 3: Wait and verify line status changes to 'Up'
    logger.info(f"Step 3: Waiting for line {target_line} to become 'Up'...")
    pytest_assert(
        wait_for_line_status(duthost, target_line, 'Up', timeout=HEARTBEAT_DETECT_SEC + 3),
        f"Line {target_line} did not change to 'Up' status after enabling heartbeat"
    )

    # Verify other lines remain 'Unknown'
    all_statuses = get_all_line_statuses(duthost)
    logger.info(f"Line statuses after heartbeat enabled: {all_statuses}")
    for line_id, status in all_statuses.items():
        if line_id == target_line:
            pytest_assert(status == 'Up', f"Target line {line_id} should be 'Up', got '{status}'")
        else:
            pytest_assert(status == 'Unknown', f"Line {line_id} should remain 'Unknown', got '{status}'")

    # Step 4: Disable heartbeat on fanout side
    logger.info("Step 4: Disabling heartbeat on fanout...")
    fanout_host.shell("sudo config console heartbeat disable", module_ignore_errors=True)
    fanout_host.shell(f"sudo pkill -f 'console-monitor.*{device_path}'", module_ignore_errors=True)

    # Step 5: Verify line remains 'Up' briefly (grace period)
    logger.info("Step 5: Verifying line remains 'Up' during grace period...")
    time.sleep(1)
    status = get_line_status(duthost, target_line)
    pytest_assert(
        status == 'Up',
        f"Line {target_line} should still be 'Up' during grace period, got '{status}'"
    )

    # Step 6: Wait for heartbeat timeout and verify status returns to 'Unknown'
    logger.info(f"Step 6: Waiting {HEARTBEAT_TIMEOUT_SEC}s for heartbeat timeout...")
    pytest_assert(
        wait_for_line_status(duthost, target_line, 'Unknown', timeout=HEARTBEAT_TIMEOUT_SEC + 5),
        f"Line {target_line} did not return to 'Unknown' status after heartbeat disabled"
    )

    logger.info("Test passed: Heartbeat detection working correctly")


def test_console_data_passthrough(
    duthosts, console_fanout, dut_console_lines, creds,
    dce_service_is_running, cleanup_console_sessions
):
    """
    Test data can be passed through console connection.

    Test steps:
    1. Connect to console line from DUT using 'connect line X'
    2. Send test data from fanout side to the serial port
    3. Verify test data is received on DUT console session
    """
    duthost = duthosts[0]
    fanout_host = console_fanout.host

    # Get DUT connection info
    dutip = duthost.host.options['inventory_manager'].get_host(duthost.hostname).vars['ansible_host']
    dutuser = creds['sonicadmin_user']
    dutpass = creds['sonicadmin_password']

    # Get first available line for testing
    fanout_port, dut_port, baud_rate = dut_console_lines[0]
    target_line = str(dut_port)
    logger.info(f"Testing data passthrough on line {target_line}")

    # Generate unique test data
    test_data = f"CONSOLE_TEST_DATA_{int(time.time())}"
    client = None

    try:
        # Step 1: Connect to console line from DUT
        logger.info(f"Step 1: Connecting to console line {target_line} from DUT...")
        client = pexpect.spawn(
            f"ssh {dutuser}@{dutip} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            f"'sudo connect line {target_line}'",
            timeout=30
        )
        client.expect('[Pp]assword:')
        client.sendline(dutpass)

        # Wait for connection to establish
        i = client.expect(['Successful connection', 'Cannot connect', pexpect.TIMEOUT], timeout=10)
        pytest_assert(i == 0, f"Failed to connect to console line {target_line}")
        logger.info(f"Successfully connected to line {target_line}")

        # Step 2: Send test data from fanout side
        logger.info(f"Step 2: Sending test data from fanout: {test_data}")
        device_path = fanout_host._get_serial_device_path(fanout_port)

        # Configure serial port and send data
        fanout_host.shell(
            f"stty -F {device_path} {baud_rate} raw -echo cs8 -parenb -cstopb",
            module_ignore_errors=True
        )
        fanout_host.shell(
            f"echo '{test_data}' > {device_path}",
            module_ignore_errors=True
        )

        # Step 3: Verify data received on DUT console session
        logger.info("Step 3: Verifying data received on DUT console...")
        try:
            client.expect(test_data, timeout=5)
            logger.info(f"Successfully received test data: {test_data}")
        except pexpect.TIMEOUT:
            pytest.fail(f"Did not receive test data '{test_data}' on console")

    except pexpect.exceptions.EOF:
        pytest.fail("Console connection closed unexpectedly")
    except pexpect.exceptions.TIMEOUT:
        pytest.fail("Timeout while connecting to console")
    except Exception as e:
        pytest.fail(f"Unexpected error during console test: {e}")
    finally:
        # Exit console session
        if client is not None:
            try:
                client.sendcontrol('a')
                client.sendcontrol('x')
                client.close()
            except Exception:
                pass

    logger.info("Test passed: Data passthrough working correctly")