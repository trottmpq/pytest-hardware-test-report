"""Tests for the hardware-test-report pytest plugin"""

import json
import logging
import pathlib

import pytest

from pytest_htr.plugin import JSONReport

from .conftest import FILE


def test_arguments_in_help(pytester: pytest.Pytester) -> None:
    """Test to ensure that options are present in the help print"""
    pytester.makepyfile(FILE)
    res = pytester.runpytest("--help")
    res.stdout.fnmatch_lines(
        [
            "*hw-test-report*",
            "*hw-test-report-file*",
        ]
    )


def test_no_report(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(FILE)
    pytester.runpytest()
    assert not (pytester.path / ".report.json").exists()


def test_create_report(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report")
    assert (pytester.path / ".report.json").exists()


@pytest.mark.parametrize("file_path", ["arg.json", "x/report.json"])
def test_create_report_file_from_arg(pytester: pytest.Pytester, file_path: str) -> None:
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report", f"--hw-test-report-file={file_path}")
    assert (pytester.path / file_path).exists()


def test_create_no_report(pytester):
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report", "--hw-test-report-file=NONE")
    assert not (pytester.path / ".report.json").exists()


def test_terminal_summary(pytester):
    pytester.makepyfile(FILE)
    res = pytester.runpytest("--hw-test-report")
    res.stdout.fnmatch_lines(["-*JSON report*-", "*report saved*.report.json*"])

    res = pytester.runpytest("--hw-test-report", "--hw-test-report-file=./")
    res.stdout.fnmatch_lines(["*could not save report*"])

    res = pytester.runpytest("--hw-test-report", "--hw-test-report-file=NONE")
    res.stdout.no_fnmatch_line("-*JSON report*-")

    res = pytester.runpytest("--hw-test-report", "--hw-test-report-file=NONE", "-v")
    res.stdout.fnmatch_lines(["*auto-save skipped*"])

    res = pytester.runpytest("--hw-test-report", "-q")
    res.stdout.no_fnmatch_line("-*JSON report*-")

    res = pytester.runpytest("--hw-test-report", "-q", "--hw-test-report-verbosity=0")
    res.stdout.fnmatch_lines(["-*JSON report*-"])

    res = pytester.runpytest(
        "--hw-test-report", "--hw-test-report-file=NONE", "-vv", "--hw-test-report-verbosity=0"
    )
    res.stdout.no_fnmatch_line("-*JSON report*-")


def test_report_keys(pytester):
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    keys = set(
        [
            "created",
            "duration",
            "environment",
            "tests",
            "summary",
            "root",
            "exitcode",
        ]
    )
    assert set(data) == keys
    assert isinstance(data["created"], str)
    assert isinstance(data["duration"], float)
    assert pathlib.Path.is_absolute(pathlib.Path(data["root"]))
    assert data["exitcode"] == 1


def test_report_summary(pytester):
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    assert data["summary"] == {
        "total": 10,
        "passed": 2,
        "failed": 3,
        "skipped": 1,
        "xpassed": 1,
        "xfailed": 1,
        "error": 2,
        "collected": 10,
    }


def test_report_item_keys(pytester):
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    tests = {test["nodeid"].split("::")[-1][5:]: test for test in data["tests"]}
    assert set(tests["pass"]) == set(["nodeid", "outcome", "setup", "call", "teardown"])


def test_report_outcomes(pytester):
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    tests = {test["nodeid"].split("::")[-1][5:]: test for test in data["tests"]}
    assert len(tests) == 10
    assert tests["pass"]["outcome"] == "passed"
    assert tests["fail_with_fixture"]["outcome"] == "failed"
    assert tests["xfail"]["outcome"] == "xfailed"
    assert tests["xfail_but_passing"]["outcome"] == "xpassed"
    assert tests["fail_during_setup"]["outcome"] == "error"
    assert tests["fail_during_teardown"]["outcome"] == "error"
    assert tests["skip"]["outcome"] == "skipped"


def test_report_longrepr(pytester):
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    tests = {test["nodeid"].split("::")[-1][5:]: test for test in data["tests"]}
    assert "assert False" in tests["fail_with_fixture"]["call"]["longrepr"]


def test_report_crash_and_traceback(pytester):
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    tests = {test["nodeid"].split("::")[-1][5:]: test for test in data["tests"]}

    assert "traceback" not in tests["pass"]["call"]

    call = tests["fail_nested"]["call"]
    assert call["crash"]["path"].endswith("test_report_crash_and_traceback.py")
    assert call["crash"]["lineno"] == 55
    assert call["crash"]["message"].startswith("TypeError: unsupported ")
    traceback = [
        {"path": "test_report_crash_and_traceback.py", "lineno": 66, "message": ""},
        {"path": "test_report_crash_and_traceback.py", "lineno": 64, "message": "in foo"},
        {"path": "test_report_crash_and_traceback.py", "lineno": 64, "message": "in <listcomp>"},
        {"path": "test_report_crash_and_traceback.py", "lineno": 60, "message": "in bar"},
        {"path": "test_report_crash_and_traceback.py", "lineno": 55, "message": "TypeError"},
    ]
    assert call["traceback"] == traceback


@pytest.mark.parametrize("tb_style", ["long", "short"])
def test_report_traceback_styles(pytester, tb_style):
    pytester.makepyfile(
        """
    def test_raise(): assert False
    def test_raise_nested(): f = lambda: g; f()"""
    )
    pytester.runpytest("--hw-test-report", f"--tb={tb_style}")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    for i in (0, 1):
        assert isinstance(data["tests"][i]["call"]["traceback"], list)


@pytest.mark.parametrize("tb_style", ["native", "line", "no"])
def test_report_traceback_styles2(pytester, tb_style):
    pytester.makepyfile(
        """
        def test_raise(): assert False
        def test_raise_nested(): f = lambda: g; f()
        """
    )
    pytester.runpytest("--hw-test-report", f"--tb={tb_style}")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)

    for i in (0, 1):
        assert "traceback" not in data["tests"][i]["call"]


def test_no_traceback(pytester):
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report", "--hw-test-report-omit=traceback")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    tests = {test["nodeid"].split("::")[-1][5:]: test for test in data["tests"]}
    assert "traceback" not in tests["fail_nested"]["call"]


def test_pytest_no_traceback(pytester):
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report", "--tb=no")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    tests = {test["nodeid"].split("::")[-1][5:]: test for test in data["tests"]}
    assert "traceback" not in tests["fail_nested"]["call"]


def test_no_streams(pytester):
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report", "--hw-test-report-omit=streams")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    tests = {test["nodeid"].split("::")[-1][5:]: test for test in data["tests"]}
    call = tests["fail_with_fixture"]["call"]
    assert "stdout" not in call
    assert "stderr" not in call


def test_summary_only(pytester):
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report", "--hw-test-report-summary")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    assert "summary" in data
    assert "tests" not in data
    assert "warnings" not in data


def test_report_streams(pytester):
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    tests = {test["nodeid"].split("::")[-1][5:]: test for test in data["tests"]}

    test = tests["fail_with_fixture"]
    assert test["setup"]["stdout"] == "setup\n"
    assert test["setup"]["stderr"] == "setuperr\n"
    assert test["call"]["stdout"] == "call\n"
    assert test["call"]["stderr"] == "callerr\n"
    assert test["teardown"]["stdout"] == "teardown\n"
    assert test["teardown"]["stderr"] == "teardownerr\n"
    assert "stdout" not in tests["pass"]["call"]
    assert "stderr" not in tests["pass"]["call"]


def test_record_property(pytester):
    pytester.makepyfile(
        """
        def test_record_property(record_property):
            record_property('foo', 42)
            record_property('bar', ['baz', {'x': 'y'}])
            record_property('foo', 43)
            record_property(123, 456)

        def test_record_property_empty(record_property):
            assert True

        def test_record_property_unserializable(record_property):
            record_property('foo', b'somebytes')
    """
    )
    pytester.runpytest("-vv", "--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)

    tests = {test["nodeid"].split("::")[-1][5:]: test for test in data["tests"]}
    assert tests["record_property"]["user_properties"] == [
        {"foo": 42},
        {"bar": ["baz", {"x": "y"}]},
        {"foo": 43},
        {"123": 456},
    ]
    assert "user_properties" not in tests["record_property_empty"].keys()
    assert len(data["warnings"]) == 1 and (
        "not JSON-serializable" in data["warnings"][0]["message"]
    )


def test_json_dut(pytester):
    pytester.makepyfile(
        """
        def test_dut1(json_dut):
            json_dut['x'] = 'foo'
            json_dut['y'] = [1, {'a': 2}]

        def test_dut2(json_dut):
            json_dut['z'] = 1
            assert False

        def test_unused_dut(json_dut):
            assert True

        def test_empty_dut(json_dut):
            json_dut.update({})

        def test_unserializable_dut(json_dut):
            json_dut['a'] = object()

        import pytest
        @pytest.fixture
        def stage(json_dut):
            json_dut['a'] = 1
            yield
            json_dut['c'] = 3

        def test_multi_stage_dut(json_dut, stage):
            json_dut['b'] = 2
    """
    )
    pytester.runpytest("-vv", "--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)

    tests = {test["nodeid"].split("::")[-1][5:]: test for test in data["tests"]}
    assert tests["dut1"]["DUT"] == {"x": "foo", "y": [1, {"a": 2}]}
    assert tests["dut2"]["DUT"] == {"z": 1}
    assert "DUT" not in tests["unused_dut"]
    assert "DUT" not in tests["empty_dut"]
    assert "DUT" not in tests["unserializable_dut"]
    assert len(data["warnings"]) == 1 and (
        "test_unserializable_dut is not JSON-serializable" in data["warnings"][0]["message"]
    )
    assert tests["multi_stage_dut"]["DUT"] == {"a": 1, "b": 2, "c": 3}


def test_dut_fixture_without_report_flag(pytester):
    """Using the json_metadata fixture without --json-report should not raise
    internal errors."""
    pytester.makepyfile(
        """
        def test_dut(json_dut):
            json_dut['x'] = 'foo'
    """
    )
    res = pytester.runpytest()
    assert res.ret == 0
    assert not (pytester.path / ".report.json").exists()


def test_json_equipment(pytester):
    pytester.makepyfile(
        """
        def test_equipment1(json_equipment):
            json_equipment['x'] = 'foo'
            json_equipment['y'] = [1, {'a': 2}]

        def test_equipment2(json_equipment):
            json_equipment['z'] = 1
            assert False

        def test_unused_equipment(json_equipment):
            assert True

        def test_empty_equipment(json_equipment):
            json_equipment.update({})

        def test_unserializable_equipment(json_equipment):
            json_equipment['a'] = object()

        import pytest
        @pytest.fixture
        def stage(json_equipment):
            json_equipment['a'] = 1
            yield
            json_equipment['c'] = 3

        def test_multi_stage_equipment(json_equipment, stage):
            json_equipment['b'] = 2
    """
    )
    pytester.runpytest("-vv", "--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)

    tests = {test["nodeid"].split("::")[-1][5:]: test for test in data["tests"]}
    assert tests["equipment1"]["equipment"] == {"x": "foo", "y": [1, {"a": 2}]}
    assert tests["equipment2"]["equipment"] == {"z": 1}
    assert "equipment" not in tests["unused_equipment"]
    assert "equipment" not in tests["empty_equipment"]
    assert "equipment" not in tests["unserializable_equipment"]
    assert len(data["warnings"]) == 1 and (
        "test_unserializable_equipment is not JSON-serializable" in data["warnings"][0]["message"]
    )
    assert tests["multi_stage_equipment"]["equipment"] == {"a": 1, "b": 2, "c": 3}


def test_equipment_fixture_without_report_flag(pytester):
    """Using the json_metadata fixture without --json-report should not raise
    internal errors."""
    pytester.makepyfile(
        """
        def test_equipment(json_equipment):
            json_equipment['x'] = 'foo'
    """
    )
    res = pytester.runpytest()
    assert res.ret == 0
    assert not (pytester.path / ".report.json").exists()


def test_json_metadata(pytester):
    pytester.makepyfile(
        """
        def test_metadata1(json_metadata):
            json_metadata['x'] = 'foo'
            json_metadata['y'] = [1, {'a': 2}]

        def test_metadata2(json_metadata):
            json_metadata['z'] = 1
            assert False

        def test_unused_metadata(json_metadata):
            assert True

        def test_empty_metadata(json_metadata):
            json_metadata.update({})

        def test_unserializable_metadata(json_metadata):
            json_metadata['a'] = object()

        import pytest
        @pytest.fixture
        def stage(json_metadata):
            json_metadata['a'] = 1
            yield
            json_metadata['c'] = 3

        def test_multi_stage_metadata(json_metadata, stage):
            json_metadata['b'] = 2
    """
    )
    pytester.runpytest("-vv", "--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)

    tests = {test["nodeid"].split("::")[-1][5:]: test for test in data["tests"]}
    assert tests["metadata1"]["metadata"] == {"x": "foo", "y": [1, {"a": 2}]}
    assert tests["metadata2"]["metadata"] == {"z": 1}
    assert "metadata" not in tests["unused_metadata"]
    assert "metadata" not in tests["empty_metadata"]
    assert "metadata" not in tests["unserializable_metadata"]
    assert len(data["warnings"]) == 1 and (
        "test_unserializable_metadata is not JSON-serializable" in data["warnings"][0]["message"]
    )
    assert tests["multi_stage_metadata"]["metadata"] == {"a": 1, "b": 2, "c": 3}


def test_metadata_fixture_without_report_flag(pytester):
    """Using the json_metadata fixture without --json-report should not raise
    internal errors."""
    pytester.makepyfile(
        """
        def test_metadata(json_metadata):
            json_metadata['x'] = 'foo'
    """
    )
    res = pytester.runpytest()
    assert res.ret == 0
    assert not (pytester.path / ".report.json").exists()


def test_environment_via_metadata_plugin(pytester):
    pytester.makepyfile("")
    pytester.runpytest("--hw-test-report", "--metadata", "x", "y")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    assert "Python" in data["environment"]
    assert data["environment"]["x"] == "y"


def test_modifyreport_hook(pytester):
    pytester.makeconftest(
        """
        def pytest_json_modifyreport(json_report):
            json_report['foo'] = 'bar'
            del json_report['summary']
    """
    )
    pytester.makepyfile(
        """
        def test_foo():
            assert False
    """
    )
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    assert data["foo"] == "bar"
    assert "summary" not in data


def test_runtest_stage_hook(pytester):
    pytester.makeconftest(
        """
        def pytest_json_runtest_stage(report):
            return {'outcome': report.outcome}
    """
    )
    pytester.makepyfile(
        """
        def test_foo():
            assert False
    """
    )
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    test = data["tests"][0]
    assert test["setup"] == {"outcome": "passed"}
    assert test["call"] == {"outcome": "failed"}
    assert test["teardown"] == {"outcome": "passed"}


def test_runtest_metadata_hook(pytester):
    pytester.makeconftest(
        """
        def pytest_json_runtest_metadata(item, call):
            if call.when != 'call':
                return {}
            return {'id': item.nodeid, 'start': call.start, 'stop': call.stop}
    """
    )
    pytester.makepyfile(
        """
        def test_foo():
            assert False
    """
    )
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    test = data["tests"][0]
    assert test["metadata"]["id"].endswith("::test_foo")
    assert isinstance(test["metadata"]["start"], float)
    assert isinstance(test["metadata"]["stop"], float)


def test_runtest_dut_hook(pytester):
    pytester.makeconftest(
        """
        def pytest_json_runtest_dut(item, call):
            if call.when != 'setup':
                return {}
            return {'id': item.nodeid, 'start': call.start, 'stop': call.stop}
    """
    )
    pytester.makepyfile(
        """
        def test_foo():
            assert False
    """
    )
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    test = data["tests"][0]
    assert test["DUT"]["id"].endswith("::test_foo")
    assert isinstance(test["DUT"]["start"], float)
    assert isinstance(test["DUT"]["stop"], float)


def test_runtest_equipment_hook(pytester):
    pytester.makeconftest(
        """
        def pytest_json_runtest_equipment(item, call):
            if call.when != 'setup':
                return {}
            return {'id': item.nodeid, 'start': call.start, 'stop': call.stop}
    """
    )
    pytester.makepyfile(
        """
        def test_foo():
            assert False
    """
    )
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    test = data["tests"][0]
    assert test["equipment"]["id"].endswith("::test_foo")
    assert isinstance(test["equipment"]["start"], float)
    assert isinstance(test["equipment"]["stop"], float)


def test_warnings(pytester):
    pytester.makepyfile(
        """
        class TestFoo:
            def __init__(self):
                pass
            def test_foo(self):
                assert True
    """
    )
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    warnings = data["warnings"]
    assert set(warnings[0]) == {"category", "filename", "lineno", "message", "when"}
    assert warnings[0]["category"] in ("PytestCollectionWarning", "PytestWarning")
    assert warnings[0]["filename"].endswith(".py")
    assert warnings[0]["lineno"] == 1
    assert warnings[0]["when"] == "collect"
    assert "__init__" in warnings[0]["message"]


def test_process_report(pytester):
    pytester.makeconftest(
        """
        def pytest_sessionfinish(session):
            assert session.config.hw_report.report['exitcode'] == 0
    """
    )
    pytester.makepyfile(
        """
        def test_foo():
            assert True
    """
    )
    res = pytester.runpytest("--hw-test-report")
    assert res.ret == 0


def test_indent(pytester):
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        assert len(f.readlines()) == 1
    pytester.runpytest("--hw-test-report", "--hw-test-report-indent=4")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        assert f.readlines()[1].startswith('    "')


def test_logging(pytester):
    pytester.makepyfile(
        """
        import logging
        import pytest

        @pytest.fixture
        def fixture(request):
            logging.info('log info')
            def f():
                logging.warn('log warn')
            request.addfinalizer(f)

        def test_foo(fixture):
            logging.error('log error')
            try:
                raise
            except (RuntimeError, TypeError): # TypeError is raised in Py 2.7
                logging.getLogger().debug('log %s', 'debug', exc_info=True)
    """
    )
    pytester.runpytest("--hw-test-report", "--log-level=DEBUG")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)

    test = data["tests"][0]
    assert test["setup"]["log"][0]["msg"] == "log info"
    assert test["call"]["log"][0]["msg"] == "log error"
    assert test["call"]["log"][1]["msg"] == "log debug"
    assert test["teardown"]["log"][0]["msg"] == "log warn"

    record = logging.makeLogRecord(test["call"]["log"][1])
    assert record.getMessage() == record.msg == "log debug"


def test_no_logs(pytester):
    pytester.makepyfile(
        """
        import logging
        def test_foo():
            logging.error('log error')
    """
    )
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)

    assert "log" in data["tests"][0]["call"]

    pytester.makepyfile(
        """
        import logging
        def test_foo():
            logging.error('log error')
    """
    )
    pytester.runpytest("--hw-test-report", "--hw-test-report-omit=log")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)

    assert "log" not in data["tests"][0]["call"]


def test_no_warnings(pytester):
    pytester.makepyfile(
        """
        class TestFoo:
            def __init__(self):
                pass
            def test_foo(self):
                assert True
    """
    )
    pytester.runpytest("--hw-test-report", "--hw-test-report-omit=warnings")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)
    assert "warnings" not in data


def test_direct_invocation(pytester):
    pytester.makeconftest(
        """
        def pytest_sessionfinish(session):
            assert session.config.hw_report.report['exitcode'] == 0
    """
    )
    test_file = pytester.makepyfile(
        """
        def test_foo():
            assert True
    """
    )
    plugin = JSONReport()
    res = pytest.main([test_file], plugins=[plugin])
    assert res == 0
    assert plugin.report["exitcode"] == 0
    assert plugin.report["summary"]["total"] == 1

    report_path = pytester.path / "foo_report.json"
    assert not report_path.exists()
    plugin.save_report(report_path)
    assert report_path.exists()


def test_xdist(pytester, match_reports):
    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        r1 = json.load(f)

    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report", "-n=1")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        r2 = json.load(f)

    pytester.makepyfile(FILE)
    pytester.runpytest("--hw-test-report", "-n=4")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        r3 = json.load(f)
    assert match_reports(r1, r2)
    assert match_reports(r2, r3)


def test_flaky(pytester):
    pytester.makepyfile(
        """
        from flaky import flaky

        FLAKY_RUNS = 0

        @flaky
        def test_flaky_pass():
            assert 1 + 1 == 2

        @flaky
        def test_flaky_fail():
            global FLAKY_RUNS
            FLAKY_RUNS += 1
            assert FLAKY_RUNS == 2
    """
    )
    pytester.runpytest("--hw-test-report")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)

    assert set(data["summary"].items()) == {
        ("total", 2),
        ("passed", 2),
        ("collected", 2),
    }


def test_handle_deselection(pytester):
    """Handle deselection of test items that have not been collected."""
    fn = pytester.makepyfile(
        """
        def test_pass():
            assert True
        def test_fail():
            assert False
    """
    )
    assert pytester.runpytest("--hw-test-report", fn).ret == 1
    # In this second run, `--last-failed` causes `test_pass` to not be
    # *collected* but still explicitly *deselected*, so we assert there is no
    # internal error caused by trying to access the collector obj.
    assert pytester.runpytest("--hw-test-report", "--last-failed", fn).ret == 1


@pytest.mark.parametrize("num_processes", [1, 4])
def test_xdist_crash(pytester, num_processes):
    """Check that a crashing xdist worker doesn't kill the whole test run."""
    pytester.makepyfile(
        """
        import pytest
        import os

        @pytest.mark.parametrize("n", range(10))
        def test_crash_one_worker(n):
            if n == 0:
                os._exit(1)
    """
    )
    pytester.runpytest("--hw-test-report", f"-n={num_processes}")
    with open(pytester.path / ".report.json", encoding="utf-8") as f:
        data = json.load(f)

    assert data["exitcode"] == 1
    assert data["summary"]["passed"] == 9
    assert data["summary"]["failed"] == 1
