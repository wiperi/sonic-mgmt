# Helper Functions
import logging
import pytest

pytestmark = [pytest.mark.topology("any")]

logger = logging.getLogger(__name__)

def test_example(duthosts, fanouthosts, vmhost, tbinfo):
    """
    Example test case to demonstrate usage of fixtures and helpers.

    This test does not perform any assertions; it's a placeholder.
    """
    
    print(duthosts, fanouthosts, vmhost, tbinfo)
    return


def test_c(fanouthosts, nbrhosts):
    print(fanouthosts, nbrhosts)
    return

def test_d(nbrhosts, vmhost):
    print(nbrhosts, vmhost)
    return

def test_e(nbrhosts, duthosts):
    print(nbrhosts, duthosts)
    return

def test_f(duthosts, fanouthosts, vmhost, nbrhosts):
    print(duthosts, fanouthosts, vmhost, nbrhosts)
    import pdb; pdb.set_trace()
    return


def test_g(duthosts, fanouthosts, vmhost):
    print(duthosts, fanouthosts, vmhost)
    return

def test_h(duthosts, fanouthosts, nbrhosts):
    print(duthosts, fanouthosts, nbrhosts)    
    return

def test_i(duthosts, vmhost, nbrhosts):
    print(duthosts, vmhost, nbrhosts)
    return

def test_j(fanouthosts, vmhost, nbrhosts):
    print(fanouthosts, vmhost, nbrhosts)
    return
