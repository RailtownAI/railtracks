import pytest

import time

from requestcompletion.run.tools.profiling import StampManager


def test_single_stamper():
    sm = StampManager()
    message = "Hello world"
    t = time.time()
    stamp = sm.create_stamp(message)

    assert stamp.step == 0
    assert stamp.identifier == message
    assert t <= stamp.time <= time.time()


def test_multi_stamp():
    sm = StampManager()
    message = "Hello world"
    t = time.time()
    stamp = sm.create_stamp(message)

    assert stamp.step == 0
    assert stamp.identifier == message
    assert t <= stamp.time <= time.time()

    t = time.time()
    stamp2 = sm.create_stamp(message)

    assert stamp2.step == 1
    assert stamp2.identifier == message
    assert t <= stamp2.time <= time.time()


def test_parallel_stamps():
    sm = StampManager()

    stamp_gen = sm.stamp_creator()
    t = time.time()
    uno = stamp_gen("1")
    dos = stamp_gen("2")
    tres = stamp_gen("3")

    # ensure that the steps are all 0
    assert uno.step == 0
    assert dos.step == 0
    assert tres.step == 0

    # check that their messages are different
    assert uno.identifier == "1"
    assert dos.identifier == "2"
    assert tres.identifier == "3"

    # check that the time fit with what is expected
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
