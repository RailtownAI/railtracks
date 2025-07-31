import time
import threading
import pickle
import pytest

from railtracks.utils.profiling import Stamp, StampManager

# ================= START Fixtures & Helpers ==================
@pytest.fixture
def stampmanager_fixture():
    return StampManager()

@pytest.fixture
def stamp_fixture():
    return Stamp(time=12345, step=2, identifier="uniq")

# ================= END Fixtures & Helpers ====================


# ================= START Stamp Basic/Operator tests ==================

def test_stamp_lt_orders_by_step():
    """__lt__ gives precedence to step before time"""
    s1 = Stamp(time=10, step=1, identifier="foo")
    s2 = Stamp(time=4, step=2, identifier="foo")
    assert s1 < s2

def test_stamp_lt_orders_by_time_on_same_step():
    s1 = Stamp(time=10, step=1, identifier="foo")
    s2 = Stamp(time=15, step=1, identifier="foo")
    assert s1 < s2

def test_stamp_hash_is_unique_for_unique_fields():
    s1 = Stamp(time=10, step=1, identifier="foo")
    s2 = Stamp(time=10, step=1, identifier="bar")
    assert hash(s1) != hash(s2)

def test_stamp_hash_matches_tuple(stamp_fixture):
    s = stamp_fixture
    assert hash(s) == hash((s.time, s.step, s.identifier))

# ================= END Stamp Basic/Operator tests ====================



# ============ START StampManager single/parallel/main path tests ================

def test_single_stamper():
    sm = StampManager()
    message = "Hello world"
    t = time.time()
    stamp = sm.create_stamp(message)

    assert stamp.step == 0
    assert stamp.identifier == message
    assert t <= stamp.time <= time.time()

    logs = sm.step_logs
    assert len(logs) == 1
    assert logs[0] == [message] or logs[0][0] == message  # handle dict/list
    assert sm.all_stamps[0].identifier == message

def test_multi_stamp():
    sm = StampManager()
    message = "Hello world"
    t1 = time.time()
    stamp1 = sm.create_stamp(message)

    assert stamp1.step == 0
    assert stamp1.identifier == message
    assert t1 <= stamp1.time <= time.time()

    t2 = time.time()
    stamp2 = sm.create_stamp(message)

    assert stamp2.step == 1
    assert stamp2.identifier == message
    assert t2 <= stamp2.time <= time.time()

def test_parallel_stamps():
    sm = StampManager()

    stamp_gen = sm.stamp_creator()
    t = time.time()
    uno = stamp_gen("1")
    dos = stamp_gen("2")
    tres = stamp_gen("3")

    assert uno.step == 0
    assert dos.step == 0
    assert tres.step == 0

    assert uno.identifier == "1"
    assert dos.identifier == "2"
    assert tres.identifier == "3"

    assert t <= uno.time <= dos.time
    assert uno.time <= dos.time <= tres.time
    assert dos.time <= tres.time <= time.time()

def test_two_parallel_stamps():
    sm = StampManager()
    stamp_gen_1 = sm.stamp_creator()
    stamp_gen_2 = sm.stamp_creator()

    uno_1 = stamp_gen_1("1")
    uno_2 = stamp_gen_2("1")
    dos_1 = stamp_gen_1("2")
    dos_2 = stamp_gen_2("2")
    tres_1 = stamp_gen_1("3")
    tres_2 = stamp_gen_2("3")

    assert uno_1.step == 0
    assert uno_2.step == 1
    assert dos_1.step == 0
    assert dos_2.step == 1
    assert tres_1.step == 0
    assert tres_2.step == 1

    assert uno_1.identifier == "1"
    assert uno_2.identifier == "1"
    assert dos_1.identifier == "2"
    assert dos_2.identifier == "2"
    assert tres_1.identifier == "3"
    assert tres_2.identifier == "3"

    assert uno_1.time <= uno_2.time
    assert uno_2.time <= dos_1.time
    assert dos_1.time <= dos_2.time
    assert dos_2.time <= tres_1.time
    assert tres_1.time <= tres_2.time

    assert uno_1 < uno_2
    assert dos_1 < dos_2

def test_combo():
    sm = StampManager()
    stamp_gen_1 = sm.stamp_creator()

    uno = stamp_gen_1("1")
    dos = stamp_gen_1("2")
    singleton = sm.create_stamp("3")
    tres = stamp_gen_1("4")

    assert uno.step == 0
    assert dos.step == 0
    assert singleton.step == 1
    assert tres.step == 0

    assert uno.identifier == "1"
    assert dos.identifier == "2"
    assert singleton.identifier == "3"
    assert tres.identifier == "4"

    assert uno.time <= dos.time
    assert dos.time <= singleton.time
    assert singleton.time <= tres.time

# ============= END StampManager single/parallel/main path tests ================

# ================ START StampManager save/state/lock/pickle ================

def test_save_state():
    sm = StampManager()
    stamp_gen_1 = sm.stamp_creator()
    uno = stamp_gen_1("1")

    state = sm.__getstate__()
    assert "_stamp_lock" not in state
    sm2 = StampManager()
    sm2.__setstate__(state)

    duo = sm2.create_stamp("2")
    assert duo.step == 1
    assert uno.step == 0

def test_create_lock_returns_new_lock():
    lock_type = type(threading.Lock())
    l1 = StampManager._create_lock()
    l2 = StampManager._create_lock()
    assert isinstance(l1, lock_type)
    assert l1 is not l2

def test_stampmanager_pickle_roundtrip(stampmanager_fixture):
    lock_type = type(threading.Lock())
    sm = stampmanager_fixture
    sm.create_stamp("abc")
    pkl = pickle.dumps(sm)
    sm2 = pickle.loads(pkl)
    # _stamp_lock should be re-created, not shared
    assert isinstance(sm2._stamp_lock, lock_type)
    assert sm2.step_logs == sm.step_logs

# ================ END StampManager save/state/lock/pickle ================

# ================= START StampManager convenience/getters =============
def test_create_stamp_basic(stampmanager_fixture):
    sm = stampmanager_fixture
    s = sm.create_stamp("first")
    assert isinstance(s, Stamp)
    assert s.step == 0
    assert s.identifier == "first"
    s2 = sm.create_stamp("second")
    assert s2.step == 1

def test_create_stamp_step_logs(stampmanager_fixture):
    sm = stampmanager_fixture
    sm.create_stamp("msg1")
    sm.create_stamp("msg2")
    logs = sm.step_logs
    assert logs[0] == ["msg1"]
    assert logs[1] == ["msg2"]

def test_stamp_creator_shared_step(stampmanager_fixture):
    sm = stampmanager_fixture
    creator = sm.stamp_creator()
    st1 = creator("a")
    st2 = creator("b")
    assert st1.step == st2.step
    assert st1.identifier == "a"
    assert st2.identifier == "b"
    assert sm._step >= st2.step + 1

def test_stamp_creator_step_logs(stampmanager_fixture):
    sm = stampmanager_fixture
    creator = sm.stamp_creator()
    creator("foo")
    creator("bar")
    logs = sm.step_logs
    log_vals = list(logs.values()) if isinstance(logs, dict) else logs
    assert "foo" in log_vals[0]
    assert "bar" in log_vals[0]

def test_all_stamps_sorted_returns_sorted(stampmanager_fixture):
    sm = stampmanager_fixture
    s1 = sm.create_stamp("msg1")
    time.sleep(0.01)
    s2 = sm.create_stamp("msg2")
    all_stamps = sm.all_stamps
    assert all_stamps[0].identifier == "msg1"
    assert all_stamps[1].identifier == "msg2"

def test_step_logs_is_deepcopy(stampmanager_fixture):
    sm = stampmanager_fixture
    sm.create_stamp("x")
    sl1 = sm.step_logs
    sl1[0].append("evil")
    assert sl1 != sm.step_logs

def test_all_stamps_is_deepcopy(stampmanager_fixture):
    sm = stampmanager_fixture
    sm.create_stamp("foo")
    all1 = sm.all_stamps
    all1[0].identifier = "evil"
    # mutated copy should not affect original
    assert all1 != sm.all_stamps

# ================ END StampManager convenience/getters ==============
