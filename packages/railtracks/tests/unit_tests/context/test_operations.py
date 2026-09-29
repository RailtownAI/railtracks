from unittest import mock

import railtracks.context.operations as operations


def test_get_and_put(monkeypatch, make_runner_context_vars, make_external_context_mock):
    ec = make_external_context_mock()
    rt = make_runner_context_vars(external_context=ec)
    monkeypatch.setattr(
        operations, "safe_get_runner_context", mock.Mock(return_value=rt)
    )
    assert operations.get("foo") == "bar"
    assert operations.get("notfound", default=123) == 123
    operations.put("baz", 42)
    ec.put.assert_called_with("baz", 42)
