from requestcompletion.utils.logging.create import get_rc_logger


def test_create_default():
    logger = get_rc_logger()

    assert logger.name == "RC"

def test_name_insertion():
    logger = get_rc_logger("TestLogger")

    assert logger.name == "RC.TestLogger"