from railtracks.utils.logging.create import get_rt_logger


def test_create_default():
    logger = get_rt_logger()

    assert logger.name == "RT"

def test_name_insertion():
    logger = get_rt_logger("TestLogger")

    assert logger.name == "RT.TestLogger"