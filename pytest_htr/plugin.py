import datetime
import json
import logging
import os
import pathlib
import time
import warnings
from collections import OrderedDict
from contextlib import contextmanager

import _pytest.hookspec
import pytest
from pytest_metadata.plugin import metadata_key

from . import serialize


class JSONReportBase:

    def __init__(self, config=None):
        self._config = config
        self._logger = logging.getLogger()

    def pytest_configure(self, config: pytest.Config) -> None:
        """
        Perform initial configuration. Called for every conftest after
        cmdline options are parsed.
        """
        # When the plugin is used directly from code, it may have been
        # initialized without a config.
        if self._config is None:
            self._config = config
        if not hasattr(config, "hw_report"):
            self._config.hw_report = self
        # If the user sets --tb=no, always omit the traceback from the report
        if self._config.option.tbstyle == "no" and not self._must_omit("traceback"):
            self._config.option.hw_test_report_omit.append("traceback")

    def pytest_addhooks(self, pluginmanager):
        """Add new hooks"""
        pluginmanager.add_hookspecs(Hooks)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):  # pylint: disable=unused-argument
        """Add the hw_report_extra attribute to pytest.Item and then clean up after"""
        item.hw_report_extra = {}
        yield
        del item.hw_report_extra

    @contextmanager
    def _capture_log(self, item, when):
        """Add log to the report"""
        handler = LoggingHandler()
        self._logger.addHandler(handler)
        try:
            yield
        finally:
            self._logger.removeHandler(handler)
        item.hw_report_extra[when]["log"] = handler.records

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_setup(self, item):
        """Add setup to the report. set up log if not omitted"""
        item.hw_report_extra["setup"] = {}
        if self._must_omit("log"):
            yield
        else:
            with self._capture_log(item, "setup"):
                yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        """Add call to the report. set up log if not omitted"""
        item.hw_report_extra["call"] = {}
        if self._must_omit("log"):
            yield
        else:
            with self._capture_log(item, "call"):
                yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_teardown(self, item):
        """Add teardown to the report. set up log if not omitted"""
        item.hw_report_extra["teardown"] = {}
        if self._must_omit("log"):
            yield
        else:
            with self._capture_log(item, "teardown"):
                yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        """Hook runtest_makereport to access the item *and* the report"""
        report = (yield).get_result()

        if not self._must_omit("streams"):
            streams = {
                key: val
                for when_, key, val in item._report_sections
                if when_ == report.when and key in ["stdout", "stderr"]
            }
            item.hw_report_extra[call.when].update(streams)

        for dict_ in self._config.hook.pytest_json_runtest_metadata(item=item, call=call):
            if not dict_:
                continue
            item.hw_report_extra.setdefault("metadata", {}).update(dict_)
        self._validate_metadata(item)

        for dict_ in self._config.hook.pytest_json_runtest_dut(item=item, call=call):
            if not dict_:
                continue
            item.hw_report_extra.setdefault("DUT", {}).update(dict_)
        self._validate_dut(item)

        for dict_ in self._config.hook.pytest_json_runtest_equipment(item=item, call=call):
            if not dict_:
                continue
            item.hw_report_extra.setdefault("equipment", {}).update(dict_)
        self._validate_equipment(item)

        # Attach the JSON details to the report. If this is an xdist worker,
        # the details will be serialized and relayed with the other attributes
        # of the report.
        report.hw_report_extra = item.hw_report_extra  # type: ignore[attr-defined]

    @staticmethod
    def _validate_metadata(item):
        """Ensure that `item` has JSON-serializable metadata, otherwise delete
        it."""
        if "metadata" not in item.hw_report_extra:
            return
        if not serialize.serializable(item.hw_report_extra["metadata"]):
            warnings.warn(f"Metadata of {item.nodeid} is not JSON-serializable.")
            del item.hw_report_extra["metadata"]

    @staticmethod
    def _validate_dut(item):
        """Ensure that `item` has JSON-serializable DUT, otherwise delete
        it."""
        if "DUT" not in item.hw_report_extra:
            return
        if not serialize.serializable(item.hw_report_extra["DUT"]):
            warnings.warn(f"DUT of {item.nodeid} is not JSON-serializable.")
            del item.hw_report_extra["DUT"]

    @staticmethod
    def _validate_equipment(item):
        """Ensure that `item` has JSON-serializable equipment, otherwise delete
        it."""
        if "equipment" not in item.hw_report_extra:
            return
        if not serialize.serializable(item.hw_report_extra["equipment"]):
            warnings.warn(f"equipment of {item.nodeid} is not JSON-serializable.")
            del item.hw_report_extra["equipment"]

    def _must_omit(self, key):
        return key in self._config.option.hw_test_report_omit


class JSONReport(JSONReportBase):
    """The JSON report pytest plugin."""

    def __init__(self, *args, **kwargs):
        JSONReportBase.__init__(self, *args, **kwargs)
        self._start_time = None
        self._json_tests = OrderedDict()
        self._json_warnings = []
        self._num_deselected = 0
        self._terminal_summary = ""
        # Min verbosity required to print to terminal
        self._terminal_min_verbosity = 0
        self.report = None

    def pytest_sessionstart(self, session):
        self._start_time = time.time()

    def pytest_runtest_logreport(self, report):
        # The `hw_report_extra` attr may have been lost, e.g. when the
        # original report object got replaced due to a crashed xdist worker (#75)
        if not hasattr(report, "hw_report_extra"):
            report.hw_report_extra = {}

        nodeid = report.nodeid
        try:
            json_testitem = self._json_tests[nodeid]
        except KeyError:
            json_testitem = serialize.make_testitem(nodeid)
            self._json_tests[nodeid] = json_testitem

        metadata = report.hw_report_extra.get("metadata")
        if metadata:
            json_testitem["metadata"] = metadata

        dut = report.hw_report_extra.get("DUT")
        if dut:
            json_testitem["DUT"] = dut

        equipment = report.hw_report_extra.get("equipment")
        if equipment:
            json_testitem["equipment"] = equipment

        # Add user properties in teardown stage if attribute exists and is non-empty
        if report.when == "teardown" and getattr(report, "user_properties", None):
            user_properties = [{str(key): val} for key, val in report.user_properties]
            if serialize.serializable(user_properties):
                json_testitem["user_properties"] = user_properties
            else:
                warnings.warn(f"User properties of {nodeid} are not JSON-serializable.")

        # Update total test outcome, if necessary. The total outcome can be
        # different from the outcome of the setup/call/teardown stage.
        outcome = self._config.hook.pytest_report_teststatus(report=report, config=self._config)[0]
        if outcome not in ["passed", ""]:
            json_testitem["outcome"] = outcome
        json_testitem[report.when] = self._config.hook.pytest_json_runtest_stage(report=report)

    @pytest.hookimpl(trylast=True)
    def pytest_json_runtest_stage(self, report):
        stage_details = report.hw_report_extra.get(report.when, {})
        return serialize.make_teststage(
            report,
            # TODO Can we use pytest's BaseReport.capstdout/err/log here?
            stage_details.get("stdout"),
            stage_details.get("stderr"),
            stage_details.get("log"),
            self._must_omit("traceback"),
        )

    @pytest.hookimpl(tryfirst=True)
    def pytest_sessionfinish(self, session):
        summary_data = {
            # Need to add deselected count to get correct number of collected
            # tests (see pytest-dev/pytest#9614)
            "collected": session.testscollected
            + self._num_deselected
        }
        if self._num_deselected:
            summary_data["deselected"] = self._num_deselected

        json_report = serialize.make_report(
            created=datetime.datetime.fromtimestamp(time.time()).isoformat(),
            duration=time.time() - self._start_time,
            exitcode=session.exitstatus,
            root=str(session.fspath),
            environment=self._config.stash.get(metadata_key, {}),
            summary=serialize.make_summary(self._json_tests, **summary_data),
        )
        if not self._config.option.json_report_summary:
            # if self._json_collectors:
            #     json_report["collectors"] = self._json_collectors
            json_report["tests"] = list(self._json_tests.values())
            if self._json_warnings:
                json_report["warnings"] = self._json_warnings

        self._config.hook.pytest_json_modifyreport(json_report=json_report)
        # After the session has finished, other scripts may want to use report
        # object directly
        self.report = json_report
        path = self._config.option.hw_test_report_file
        if path:
            path = pathlib.Path(os.path.expandvars(path)).expanduser()
            try:
                self.save_report(path)
            except OSError as e:
                self._terminal_summary = f"could not save report: {e}"
            else:
                self._terminal_summary = f"report saved to: {path}"
        else:
            self._terminal_summary = "report auto-save skipped"
            self._terminal_min_verbosity = 1

    def save_report(self, path: pathlib.Path) -> None:
        """Save the JSON report to `path`.

        Raises an exception if saving failed.
        """
        if self.report is None:
            raise ValueError("could not save report: no report available")
        # Create path if it doesn't exist
        dirname = path.parent
        if dirname:
            dirname.mkdir(exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                self.report,
                f,
                default=str,
                indent=self._config.option.hw_test_report_indent,
            )

    def pytest_warning_recorded(self, warning_message, when):
        if self._config is None:
            # If pytest is invoked directly from code, it may try to capture
            # warnings before the config is set.
            return
        if not self._must_omit("warnings"):
            self._json_warnings.append(serialize.make_warning(warning_message, when))

    # Warning hook fallback (warning_recorded is available from pytest>=6)
    if not hasattr(_pytest.hookspec, "pytest_warning_recorded"):
        pytest_warning_captured = pytest_warning_recorded
        del pytest_warning_recorded

    def pytest_terminal_summary(self, terminalreporter):
        if self._terminal_min_verbosity > (
            self._config.option.hw_test_report_verbosity
            if self._config.option.hw_test_report_verbosity is not None
            else terminalreporter.verbosity
        ):
            return
        terminalreporter.write_sep("-", "JSON report")
        terminalreporter.write_line(self._terminal_summary)


class JSONReportWorker(JSONReportBase):

    pass


class LoggingHandler(logging.Handler):

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        d = dict(record.__dict__)
        d["msg"] = record.getMessage()
        d["args"] = None
        d["exc_info"] = None
        d.pop("message", None)
        self.records.append(d)


class Hooks:

    def pytest_json_modifyreport(self, json_report):
        """Called after building JSON report and before saving it.

        Plugins can use this hook to modify the report before it's saved.
        """

    @pytest.hookspec(firstresult=True)
    def pytest_json_runtest_stage(self, report):
        """Return a dict used as the JSON representation of `report` (the
        `_pytest.runner.TestReport` of the current test stage).

        Called from `pytest_runtest_logreport`. Plugins can use this hook to
        overwrite how the result of a test stage run gets turned into JSON.
        """

    def pytest_json_runtest_dut(self, item, call):
        """Return a dict used as the JSON representation of `dut` (the
        `_pytest.runner.TestReport` of the current test stage).

        Called from `pytest_runtest_logreport`. Plugins can use this hook to
        overwrite how the dut run gets turned into JSON.
        """

    def pytest_json_runtest_equipment(self, item, call):
        """Return a dict used as the JSON representation of `equipment` (the
        `_pytest.runner.TestReport` of the current test stage).

        Called from `pytest_runtest_logreport`. Plugins can use this hook to
        overwrite how the equipment run gets turned into JSON.
        """

    def pytest_json_runtest_metadata(self, item, call):
        """Return a dict which will be added to the current test item's JSON
        metadata.

        Called from `pytest_runtest_makereport`. Plugins can use this hook to
        add metadata based on the current test run.
        """


@pytest.fixture
def json_metadata(request):
    """Fixture to add metadata to the current test item."""
    try:
        return request.node.hw_report_extra.setdefault("metadata", {})
    except AttributeError:
        if not request.config.option.hw_test_report:
            # The user didn't request a JSON report, so the plugin didn't
            # prepare a metadata context. We return a dummy dict, so the
            # fixture can be used as expected without causing internal errors.
            return {}
        raise


@pytest.fixture
def json_dut(request):
    """Fixture to add metadata to the current test item."""
    try:
        return request.node.hw_report_extra.setdefault("DUT", {})
    except AttributeError:
        if not request.config.option.hw_test_report:
            # The user didn't request a JSON report, so the plugin didn't
            # prepare a metadata context. We return a dummy dict, so the
            # fixture can be used as expected without causing internal errors.
            return {}
        raise


@pytest.fixture
def json_equipment(request):
    """Fixture to add metadata to the current test item."""
    try:
        return request.node.hw_report_extra.setdefault("equipment", {})
    except AttributeError:
        if not request.config.option.hw_test_report:
            # The user didn't request a JSON report, so the plugin didn't
            # prepare a metadata context. We return a dummy dict, so the
            # fixture can be used as expected without causing internal errors.
            return {}
        raise


def pytest_addoption(parser):
    group = parser.getgroup("hwtestreport", "reporting test results as JSON")
    group.addoption(
        "--hw-test-report", default=False, action="store_true", help="create JSON report"
    )
    group.addoption(
        "--hw-test-report-file",
        default=".report.json",
        # The case-insensitive string "none" will make the value None
        type=lambda x: None if x.lower() == "none" else x,
        help='target path to save JSON report (use "none" to not save the ' "report)",
    )
    group.addoption(
        "--hw-test-report-omit",
        default=[],
        nargs="+",
        help="list of fields to omit in the report "
        "(choose from: log, traceback, streams, warnings)",
    )
    group.addoption(
        "--json-report-summary",
        default=False,
        action="store_true",
        help="only create a summary without per-test details",
    )
    group.addoption(
        "--hw-test-report-indent",
        type=int,
        help="pretty-print JSON with specified indentation level",
    )
    group.addoption(
        "--hw-test-report-verbosity",
        type=int,
        help="set verbosity (default is value of --verbosity)",
    )


def pytest_configure(config):
    if not config.option.hw_test_report:
        return
    if hasattr(config, "workerinput"):
        Plugin = JSONReportWorker
    else:
        Plugin = JSONReport
    plugin = Plugin(config)
    config.hw_report = plugin
    config.pluginmanager.register(plugin)


def pytest_unconfigure(config):
    plugin = getattr(config, "hw_report", None)
    if plugin is not None:
        del config.hw_report
        config.pluginmanager.unregister(plugin)
