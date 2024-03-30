import pytest

pytest_plugins = "pytester"

miss_map = {
    "V": "Different values",
    "K": "Different keys",
    "T": "Different types",
}
# Some test cases borrowed from github.com/mattcl/pytest-json
FILE = """
from __future__ import print_function
import sys
import pytest


@pytest.fixture
def setup_teardown_fixture(request):
    print('setup')
    print('setuperr', file=sys.stderr)
    def fn():
        print('teardown')
        print('teardownerr', file=sys.stderr)
    request.addfinalizer(fn)

@pytest.fixture
def fail_setup_fixture(request):
    assert False

@pytest.fixture
def fail_teardown_fixture(request):
    def fn():
        assert False
    request.addfinalizer(fn)


def test_pass():
    assert True

def test_fail_with_fixture(setup_teardown_fixture):
    print('call')
    print('callerr', file=sys.stderr)
    assert False

@pytest.mark.xfail(reason='testing xfail')
def test_xfail():
    assert False

@pytest.mark.xfail(reason='testing xfail')
def test_xfail_but_passing():
    assert True

def test_fail_during_setup(fail_setup_fixture):
    assert True

def test_fail_during_teardown(fail_teardown_fixture):
    assert True

@pytest.mark.skipif(True, reason='testing skip')
def test_skip():
    assert False

def test_fail_nested():
    def baz(o=1):
        c = 3
        return 2 - c - None
    def bar(m, n=5):
        b = 2
        print(m)
        print('bar')
        return baz()
    def foo():
        a = 1
        print('foo')
        v = [bar(x) for x in range(3)]
        return v
    foo()

@pytest.mark.parametrize('x', [1, 2])
def test_parametrized(x):
    assert x == 1
"""


@pytest.fixture
def match_reports():
    def f(a, b):
        diffs = list(diff(normalize_report(a), normalize_report(b)))
        if not diffs:
            return True
        for kind, path, a_, b_ in diffs:
            path_str = ".".join(path)
            kind_str = miss_map[kind]
            if kind == "V":
                print(kind_str, path_str)
                print("\t", a_)
                print("\t", b_)
            else:
                print(kind_str + ":", path_str, a_, b_)
        return False

    return f


def normalize_report(report):
    report["created"] = 0
    report["duration"] = 0
    # xdist doesn't report successful node collections
    report["collectors"] = []

    for test in report["tests"]:
        for stage_name in ("setup", "call", "teardown"):
            try:
                stage = test[stage_name]
            except KeyError:
                continue
            stage["duration"] = 0
            if "longrepr" not in stage:
                stage["longrepr"] = ""
    return report


def diff(a, b, path=None):
    """Return differences between reports a and b."""
    if path is None:
        path = []
    # We can't compare "longrepr" because they may be different between runs
    # with and without workers
    if path and path[-1] != "longrepr":
        return
    if type(a) is not type(b):
        yield ("T", path, a, b)
        return
    if isinstance(a, dict):
        a_keys = sorted(a.keys())
        b_keys = sorted(b.keys())
        if a_keys != b_keys:
            yield ("K", path, a_keys, b_keys)
            return
        for ak, bk in zip(a_keys, b_keys):
            for item in diff(a[ak], b[bk], path + [str(ak)]):
                yield item
        return
    if isinstance(a, list):
        for i, (ai, bi) in enumerate(zip(a, b)):
            for item in diff(ai, bi, path + [str(i)]):
                yield item
        return
    if a != b:
        yield ("V", path, repr(a), repr(b))
    return


@pytest.fixture
def dut(json_dut):
    device = {"serial no": "MATT", "version": "1.2.2"}
    json_dut["serial no"] = device.get("serial no")
    json_dut["version"] = device.get("version")
    return device


@pytest.fixture
def sig_gen(json_equipment):
    json_equipment["sig_gen"] = {
        "serial": 123,
        "manufacturer": "tester inc.",
        "model": "wavemaster 3000",
    }
    return


@pytest.fixture
def spec_an(json_equipment):
    json_equipment["spec_an"] = {
        "serial": 456,
        "manufacturer": "tester inc.",
        "model": "wavefinder 3000",
    }
    return
