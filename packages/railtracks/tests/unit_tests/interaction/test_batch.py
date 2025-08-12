import pytest
from unittest.mock import patch

from railtracks.interaction.batch import call_batch


@pytest.mark.asyncio
async def test_batch_single_iterable_returns_results_in_order():
    async def mock_call(node, *args):
        return f"result_{args[0]}"

    with patch("railtracks.interaction.batch.call", new=mock_call):
        node = lambda x: x  # Dummy node
        inputs = [1, 2, 3]

        results = await call_batch(node, inputs)

        assert results == ["result_1", "result_2", "result_3"]


@pytest.mark.asyncio
async def test_batch_multiple_iterables_passes_all_args():
    async def mock_call(node, *args):
        return f"sum_{sum(args)}"

    with patch("railtracks.interaction.batch.call", new=mock_call):
        node = lambda x, y: x + y  # Dummy node
        inputs1 = [1, 2, 3]
        inputs2 = [10, 20, 30]

        results = await call_batch(node, inputs1, inputs2)

        assert results == ["sum_11", "sum_22", "sum_33"]


@pytest.mark.asyncio
async def test_batch_with_exceptions_returned():
    async def mock_call(node, *args):
        if args[0] == "bad":
            raise ValueError("Bad input")
        return f"good_{args[0]}"

    with patch("railtracks.interaction.batch.call", new=mock_call):
        node = lambda x: x
        inputs = ["good", "bad", "good"]

        results = await call_batch(node, inputs, return_exceptions=True)

        assert results[0] == "good_good"
        assert isinstance(results[1], Exception)
        assert results[2] == "good_good"


@pytest.mark.asyncio
async def test_batch_with_exceptions_raised():
    async def mock_call(node, *args):
        if args[0] == "fail":
            raise RuntimeError("Fail!")
        return f"ok_{args[0]}"

    with patch("railtracks.interaction.batch.call", new=mock_call):
        node = lambda x: x
        inputs = ["ok", "fail", "ok"]

        with pytest.raises(RuntimeError, match="Fail!"):
            await call_batch(node, inputs, return_exceptions=False)
