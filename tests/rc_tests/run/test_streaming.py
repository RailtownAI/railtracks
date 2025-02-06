import concurrent.futures
import time

from requestcompletion.context.context import EmptyContext
from requestcompletion.run.config import ExecutorConfig
from requestcompletion.run.run import run
from requestcompletion.run.tools.stream import (
    Subscriber,
)

from tests.rc_tests.fixtures.nodes import (
    StreamingRNGNode,
    StreamingCallNode,
)


def test_simple_streamer():
    i_r = StreamingRNGNode()

    class Sub(Subscriber[str]):
        def __init__(self):
            self.finished_message = None

        def handle(self, item: str) -> None:
            print(f"entering handler {item}")
            self.finished_message = item

    sub = Sub()
    finished_result = run(
        i_r,
        EmptyContext(),
        subscriber=sub,
        executor_config=ExecutorConfig(global_num_retries=5, force_close_streams=False),
    )
    # force close streams flag must be set to false to allow the slow streaming to finish.

    assert isinstance(finished_result.answer, float)
    assert sub.finished_message == StreamingRNGNode.rng_template.format(
        finished_result.answer
    )

    assert 0 < finished_result.answer < 1


# rather annoyingly this test could fail but it should be good nearly all of the time
def test_slow_streamer():
    i_node = StreamingRNGNode()

    class Sub(Subscriber[str]):
        def __init__(self):
            self.finished_message = None

        def handle(self, item: str) -> None:
            # make this really slow so it is likely to not finish by the time execution is complete
            time.sleep(1)
            self.finished_message = item

    sub = Sub()
    finished_result = run(
        i_node,
        subscriber=sub,
        executor_config=ExecutorConfig(global_num_retries=5, force_close_streams=True),
    )
    assert isinstance(finished_result.answer, float)
    assert sub.finished_message is None


def rng_stream_tester(
    num_calls=3,
    parallel_call_nums=3,
    multiplier=1,
):
    i_node = StreamingCallNode(
        num_calls,
        parallel_call_nums,
        lambda: StreamingRNGNode(),
    )

    class Sub(Subscriber[str]):
        def __init__(self):
            self.num_rngs = 0
            self.num_call_calls = 0
            self.errors = []

        def handle(self, item: str) -> None:
            # just look at the first part of the template
            call_template = StreamingCallNode.call_template_call.split()[:4]
            finished_template = StreamingRNGNode.rng_template.split()[:2]

            if item.split()[:4] == call_template:
                self.num_call_calls += 1 * multiplier

            if item.split()[:2] == finished_template:
                self.num_rngs += 1 * multiplier

    sub = Sub()
    finished_result = run(
        i_node,
        subscriber=sub,
        executor_config=ExecutorConfig(
            global_num_retries=5,
            force_close_streams=False,
        ),
        # we need to set this flag to allow the slow streaming to finish.
    )

    assert isinstance(finished_result.answer, list)

    assert len(finished_result.answer) == num_calls * parallel_call_nums
    assert all([0 < x < 1 for x in finished_result.answer])

    # check if the subscriber has any errors
    assert not sub.errors, f"Subscriber should not have any errors {sub.errors}"

    assert sub.num_call_calls == num_calls * parallel_call_nums * multiplier
    assert sub.num_rngs == num_calls * parallel_call_nums * multiplier


def test_rng_streamer():
    rng_stream_tester(3, 3)


def test_rng_streamer_2():
    rng_stream_tester(1, 15)


def test_rng_streamer_chaos():
    rng_stream_tester(4, 25)


def test_rng_streamer_chaos_2():
    rng_stream_tester(2, 15)


# there is also a weird test that we need to run through to make sure that the streamer can be different if we were
#  running 2 types of streamers at the same time.
def test_rng_streamer_chaos_with_multiple_processes():
    with concurrent.futures.ThreadPoolExecutor() as executor:
        f1 = executor.submit(rng_stream_tester, 2, 15, 3)
        f2 = executor.submit(rng_stream_tester, 2, 15, 2)

        f1.result()
        f2.result()


def test_rng_streamer_chaos_with_multiple_processes_2():
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for m in range(1, 50, 5):
            futures.append(executor.submit(rng_stream_tester, 2, 15, m))

        for f in concurrent.futures.as_completed(futures):
            f.result()
