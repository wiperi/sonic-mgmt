# Helper Functions
import logging
import pytest

pytestmark = [pytest.mark.topology("any")]

logger = logging.getLogger(__name__)


def test_a(fanouthosts):
    print(fanouthosts)
    return

def test_b(duthosts, fanouthosts, vmhost, nbrhosts):
    print(duthosts, fanouthosts, vmhost, nbrhosts)
    import pdb; pdb.set_trace()
    return