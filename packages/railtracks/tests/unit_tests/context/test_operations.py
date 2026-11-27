from unittest import mock

import railtracks as rt
import railtracks.context.operations as operations
from railtracks.context.external import _MISSING


def test_get_and_put(monkeypatch, make_runner_context_vars, make_external_context_mock):
    ec = make_external_context_mock()
    rt_vars = make_runner_context_vars(external_context=ec)
    monkeypatch.setattr(
        operations, "safe_get_runner_context", mock.Mock(return_value=rt_vars)
    )
    assert operations.get("foo") == "bar"
    assert operations.get("notfound", default=123) == 123
    operations.put("baz", 42)
    ec.put.assert_called_with("baz", 42)


def test_mutate_delegates_and_records(
    monkeypatch, make_runner_context_vars, make_external_context_mock
):
    ec = make_external_context_mock()
    ec.mutate = mock.Mock(return_value=6)
    rt_vars = make_runner_context_vars(external_context=ec)
    monkeypatch.setattr(
        operations, "safe_get_runner_context", mock.Mock(return_value=rt_vars)
    )
    recorded = mock.Mock()
    monkeypatch.setattr(operations, "record_put", recorded)

    def inc(n):
        return n + 1

    assert rt.context.mutate("count", inc) == 6
    ec.mutate.assert_called_once_with("count", inc, default=_MISSING)
    recorded.assert_called_once_with("count", 6)

    ec.mutate.reset_mock()
    recorded.reset_mock()
    assert operations.mutate("count", inc, default=0) == 6
    ec.mutate.assert_called_once_with("count", inc, default=0)
    recorded.assert_called_once_with("count", 6)
