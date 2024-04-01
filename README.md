# Pytest Hardware Test Report

[![CI](https://github.com/trottmpq/pytest-hardware-test-report/actions/workflows/main.yml/badge.svg)](https://github.com/trottmpq/pytest-hardware-test-report/actions/workflows/main.yml)
[![PyPI Version](https://img.shields.io/pypi/v/pytest-hardware-test-report.svg)](https://pypi.org/project/pytest-hardware-test-report)
[![Python Versions](https://img.shields.io/pypi/pyversions/pytest-hardware-test-report.svg)](https://pypi.org/project/pytest-hardware-test-report)

This pytest plugin creates test reports for hardware tests in JSON. This makes it easy to process test results in other applications.

It can report a summary, test details, captured output, logs, exception tracebacks and more. Additionally, you can use the available fixtures and hooks to [add metadata](#metadata) and [customize](#modifying-the-report) the report as you like.

## Table of contents

* [Installation](#installation)
* [Options](#options)
* [Usage](#usage)
  * [Fixtures](#fixtures)
    * [json_dut](#json_dut)
    * [json_equipment](#json_equipment)
    * [json_metadata](#json_metadata)
  * [Advanced Usage](#advanced-usage)
    * [DUT](#dut)
    * [Equipment](#equipment)
    * [Metadata](#metadata)
    * [Modifying the report](#modifying-the-report)
  * [Direct invocation](#direct-invocation)
  * [Format](#format)
  * [Summary](#summary)
  * [Environment](#environment)
  * [Tests](#tests)
  * [Test stage](#test-stage)
  * [Log](#log)
  * [Warnings](#warnings)
* [Related tools](#related-tools)

## Installation

```bash
pip install pytest-hardware-test-report --upgrade 
```

## Options

| Option | Description |
| --- | --- |
| `--hw-test-report` | Create JSON report |
| `--hw-test-report-file=PATH` | Target path to save JSON report (use "none" to not save the report) |
| `--hw-test-report-summary` | Just create a summary without per-test details |
| `--hw-test-report-omit=FIELD_LIST` | List of fields to omit in the report (choose from: `log`, `traceback`, `streams`, `warnings`) |
| `--hw-test-report-indent=LEVEL` | Pretty-print JSON with specified indentation level |
| `--hw-test-report-verbosity=LEVEL` | Set verbosity (default is value of `--verbosity`) |

## Usage

Just run pytest with `--hw-test-report`. The report is saved in `.report.json` by default.

```bash
$ pytest --hw-test-report -v tests/
$ cat .report.json
{"created": 1518371686.7981803, ... "tests":[{"nodeid": "test_foo.py", "outcome": "passed", ...}, ...]}
```

If you just need to know how many tests passed or failed and don't care about details, you can produce a summary only:

```bash
pytest --hw-test-report --hw-test-report-summary
```

Many fields can be omitted to keep the report size small. E.g., this will leave out keywords and stdout/stderr output:

```bash
pytest --hw-test-report --hw-test-report-omit keywords streams
```

If you don't like to have the report saved, you can specify `none` as the target file name:

```bash
pytest --hw-test-report --hw-test-report-file none
```

### Fixtures

#### json_dut

To record information about the device under test in the report you can use the `json_dut` [test fixture](https://docs.pytest.org/en/stable/fixture.html). This also works if your DUT is, itself, a fixture:

```python
@pytest.fixture(name="dut")
def dut_fixture(json_dut):
    json_dut['serial no'] = 1234567
    json_dut['version'] = 1.0.0
    dut = setup_dut()
    yield dut
    dut.teardown()
```

#### json_equipment

To record information about any test equipment you may use in the report you can use the `json_equipment` [test fixture](https://docs.pytest.org/en/stable/fixture.html):

```python
def equipment1(json_equipment):
    json_equipment['equipment1'] = {'manufacturer': 'Test Inc.', 'Model': 'Testomatic 300'}
```

#### json_metadata

The easiest way to add your own metadata to a test item is by using the `json_metadata` [test fixture](https://docs.pytest.org/en/stable/fixture.html):

```python
def test_something(json_metadata):
    json_metadata['foo'] = {"some": "thing"}
    json_metadata['bar'] = 123
```

## Advanced usage

### Hooks

If you're using a `pytest_json_*` hook although the plugin is not installed or not active (not using `--json-report`), pytest doesn't recognize it and may fail with an internal error like this:

```bash
INTERNALERROR> pluggy.manager.PluginValidationError: unknown hook 'pytest_json_runtest_metadata' in plugin <module 'conftest' from 'conftest.py'>
```

You can avoid this by declaring the hook implementation optional:

```python
import pytest
@pytest.hookimpl(optionalhook=True)
def pytest_json_runtest_metadata(item, call):
    ...
```

#### DUT

Or use the `pytest_json_runtest_dut` [hook](https://docs.pytest.org/en/stable/reference.html#hooks) (in your `conftest.py`) to add metadata based on the current test run. The dict returned will automatically be merged with any existing metadata. E.g., this adds the start and stop time of each test's `setup` stage:

```python
def pytest_json_runtest_dut(item, call):
    if call.when != 'setup':
        return {}
    return {'start': call.start, 'stop': call.stop}
```

#### Equipment

Or use the `pytest_json_runtest_equipment` [hook](https://docs.pytest.org/en/stable/reference.html#hooks) (in your `conftest.py`) to add metadata based on the current test run. The dict returned will automatically be merged with any existing metadata. E.g., this adds the start and stop time of each test's `setup` stage:

```python
def pytest_json_runtest_equipment(item, call):
    if call.when != 'setup':
        return {}
    return {'start': call.start, 'stop': call.stop}
```

#### Metadata

Or use the `pytest_json_runtest_metadata` [hook](https://docs.pytest.org/en/stable/reference.html#hooks) (in your `conftest.py`) to add metadata based on the current test run. The dict returned will automatically be merged with any existing metadata. E.g., this adds the start and stop time of each test's `call` stage:

```python
def pytest_json_runtest_metadata(item, call):
    if call.when != 'call':
        return {}
    return {'start': call.start, 'stop': call.stop}
```

Also, you could add metadata using [pytest-metadata's `--metadata` switch](https://github.com/pytest-dev/pytest-metadata#additional-metadata) which will add metadata to the report's `environment` section, but not to a specific test item. You need to make sure all your metadata is JSON-serializable.

#### Modifying the report

You can modify the entire report before it's saved by using the `pytest_json_modifyreport` hook.

Just implement the hook in your `conftest.py`, e.g.:

```python
def pytest_json_modifyreport(json_report):
    # Add a key to the report
    json_report['foo'] = 'bar'
    # Delete the summary from the report
    del json_report['summary']
```

After `pytest_sessionfinish`, the report object is also directly available to script via `config._json_report.report`. So you can access it using some built-in hook:

```python
def pytest_sessionfinish(session):
    report = session.config._json_report.report
    print('exited with', report['exitcode'])
```

If you *really* want to change how the result of a test stage run is turned into JSON, you can use the `pytest_json_runtest_stage` hook. It takes a [`TestReport`](https://docs.pytest.org/en/latest/reference.html#_pytest.runner.TestReport) and returns a JSON-serializable dict:

```python
def pytest_json_runtest_stage(report):
    return {'outcome': report.outcome}
```

### Direct invocation

You can use the plugin when invoking `pytest.main()` directly from code:

```python
import pytest
from pytest_htr.plugin import JSONReport

plugin = JSONReport()
pytest.main(['--hw-test-report-file=none', 'test_foo.py'], plugins=[plugin])
```

You can then access the `report` object:

```python
print(plugin.report)
```

And save the report manually:

```python
plugin.save_report('/tmp/my_report.json')
```

## Format

The JSON report contains metadata of the session, a summary, tests and warnings. You can find a sample report in [`sample_report.json`](sample_report.json).

| Key | Description |
| --- | --- |
| `created` | Report creation date. (Unix time) |
| `duration` | Session duration in seconds. |
| `exitcode` | Process exit code as listed [in the pytest docs](https://docs.pytest.org/en/latest/usage.html#possible-exit-codes). The exit code is a quick way to tell if any tests failed, an internal error occurred, etc. |
| `root` | Absolute root path from which the session was started. |
| `environment` | [Environment](#environment) entry. |
| `summary` | [Summary](#summary) entry. |
| `tests` | [Tests](#tests) entry. (absent if `--hw-test-report-summary`)  |
| `warnings` | [Warnings](#warnings) entry. (absent if `--hw-test-report-summary` or if no warnings)  |

### Format Example

```python
{
    "created": 1518371686.7981803,
    "duration": 0.1235666275024414,
    "exitcode": 1,
    "root": "/path/to/tests",
    "environment": ENVIRONMENT,
    "summary": SUMMARY,
    "tests": TESTS,
    "warnings": WARNINGS,
}
```

## Summary

Number of outcomes per category and the total number of test items.

| Key | Description |
| --- | --- |
|  `collected` | Total number of tests collected. |
|  `total` | Total number of tests run. |
|  `deselected` | Total number of tests deselected. (absent if number is 0) |
| `<outcome>` | Number of tests with that outcome. (absent if number is 0) |

### Summary Example

```python
{
    "collected": 10,
    "passed": 2,
    "failed": 3,
    "xfailed": 1,
    "xpassed": 1,
    "error": 2,
    "skipped": 1,
    "total": 10
}
```

## Environment

The environment section is provided by [pytest-metadata](https://github.com/pytest-dev/pytest-metadata). All metadata given by that plugin will be added here, so you need to make sure it is JSON-serializable.

### Environment Example

```python
{
    "Python": "3.6.4",
    "Platform": "Linux-4.56.78-9-ARCH-x86_64-with-arch",
    "Packages": {
        "pytest": "3.4.0",
        "py": "1.5.2",
        "pluggy": "0.6.0"
    },
    "Plugins": {
        "json-report": "0.4.1",
        "xdist": "1.22.0",
        "metadata": "1.5.1",
        "forked": "0.2",
        "cov": "2.5.1"
    },
    "foo": "bar", # Custom metadata entry passed via pytest-metadata
}
```

## Tests

A list of test nodes. Each completed test stage produces a stage object (`setup`, `call`, `teardown`) with its own `outcome`.

| Key | Description |
| --- | --- |
| `nodeid` | ID of the test node. |
| `outcome` | Outcome of the test run. |
| `DUT` | DUT item. (absent if not present) |
| `equipment` | equipment item. (absent if not present) |
| `{setup, call, teardown}` | [Test stage](#test-stage) entry. To find the error in a failed test you need to check all stages. (absent if stage didn't run) |
| `metadata` | [Metadata](#metadata) item. (absent if no metadata) |

### Tests Example

```python
[
    {
        "nodeid": "test_foo.py::test_fail",
        "outcome": "failed",
        "DUT": {
            "serial no": 123456
        },
        "equipment": {
            "equipment 1": {
                "serial no": 123456
            },
            "equipment 2: {
                "serial no": 123456
            }
        },
        "setup": TEST_STAGE,
        "call": TEST_STAGE,
        "teardown": TEST_STAGE,
        "metadata": {
            "foo": "bar",
        }
    },
    ...
]
```

## Test stage

A test stage item.

| Key | Description |
| --- | --- |
| `duration` | Duration of the test stage in seconds. |
| `outcome` | Outcome of the test stage. (can be different from the overall test outcome) |
| `crash` | Crash entry. (absent if no error occurred) |
| `traceback` | List of traceback entries. (absent if no error occurred; affected by `--tb` option) |
| `stdout` | Standard output. (absent if none available) |
| `stderr` | Standard error. (absent if none available) |
| `log` | [Log](#log) entry. (absent if none available) |
| `longrepr` | Representation of the error. (absent if no error occurred; format affected by `--tb` option) |

### Test stage Example

```python
{
    "duration": 0.00018835067749023438,
    "outcome": "failed",
    "crash": {
        "path": "/path/to/tests/test_foo.py",
        "lineno": 54,
        "message": "TypeError: unsupported operand type(s) for -: 'int' and 'NoneType'"
    },
    "traceback": [
        {
            "path": "test_foo.py",
            "lineno": 65,
            "message": ""
        },
        {
            "path": "test_foo.py",
            "lineno": 63,
            "message": "in foo"
        },
        {
            "path": "test_foo.py",
            "lineno": 63,
            "message": "in <listcomp>"
        },
        {
            "path": "test_foo.py",
            "lineno": 54,
            "message": "TypeError"
        }
    ],
    "stdout": "foo\nbar\n",
    "stderr": "baz\n",
    "log": LOG,
    "longrepr": "def test_fail_nested():\n ..."
}
```

## Log

A list of log records. The fields of a log record are the [`logging.LogRecord` attributes](https://docs.python.org/3/library/logging.html#logrecord-attributes), with the exception that the fields `exc_info` and `args` are always empty and `msg` contains the formatted log message.

You can apply [`logging.makeLogRecord()`](https://docs.python.org/3/library/logging.html#logging.makeLogRecord)  on a log record to convert it back to a `logging.LogRecord` object.

### Log Example

```python
[
    {
        "name": "root",
        "msg": "This is a warning.",
        "args": null,
        "levelname": "WARNING",
        "levelno": 30,
        "pathname": "/path/to/tests/test_foo.py",
        "filename": "test_foo.py",
        "module": "test_foo",
        "exc_info": null,
        "exc_text": null,
        "stack_info": null,
        "lineno": 8,
        "funcName": "foo",
        "created": 1519772464.291738,
        "msecs": 291.73803329467773,
        "relativeCreated": 332.90839195251465,
        "thread": 140671803118912,
        "threadName": "MainThread",
        "processName": "MainProcess",
        "process": 31481
    },
    ...
]
```

## Warnings

A list of warnings that occurred during the session. (See the [pytest docs on warnings](https://docs.pytest.org/en/latest/warnings.html).)

| Key | Description |
| --- | --- |
| `filename` | File name. |
| `lineno` | Line number. |
| `message` | Warning message. |
| `when` | When the warning was captured. (`"config"`, `"collect"` or `"runtest"` as listed [here](https://docs.pytest.org/en/latest/reference.html#_pytest.hookspec.pytest_warning_captured)) |

### Warnings Example

```python
[
    {
        "code": "C1",
        "path": "/path/to/tests/test_foo.py",
        "nodeid": "test_foo.py::TestFoo",
        "message": "cannot collect test class 'TestFoo' because it has a __init__ constructor"
    }
]
```

## Related tools

* [pytest-json-report](https://github.com/numirias/pytest-json-report) Heavily inspired by this plugin. It is more suited for pure software testing but i have borrow large ammounts of code from there.

* [pytest-json](https://github.com/mattcl/pytest-json) has some great features but appears to be unmaintained. I borrowed some ideas and test cases from there.

* [tox has a switch](http://tox.readthedocs.io/en/latest/example/result.html) to create a JSON report including a test result summary. However, it just provides the overall outcome without any per-test details.
