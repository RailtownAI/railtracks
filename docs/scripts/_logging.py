import railtracks as rt

# --8<-- [start: logging_setup]
rt.set_config(logging_setting="DEBUG")
rt.set_config(logging_setting="INFO")
rt.set_config(logging_setting="CRITICAL")
rt.set_config(logging_setting="NONE")
# --8<-- [end: logging_setup]

# --8<-- [start: logging_to_file]
rt.set_config(log_file="my_logs.log")
# --8<-- [end: logging_to_file]

# --8<-- [start: logging_custom_handler]
import logging


class CustomHandler(logging.Handler):
    def emit(self, record):
        # Custom logging logic
        pass


logger = logging.getLogger()
logger.addHandler(CustomHandler())
# --8<-- [end: logging_custom_handler]

# --8<-- [start: logging_global]
rt.set_config(logging_setting="DEBUG", log_file="my_logs.log")
# --8<-- [end: logging_global]

# --8<-- [start: logging_env_var]
RT_LOG_LEVEL = "DEBUG"
RT_LOG_FILE = "my_logs.log"
# --8<-- [end: logging_env_var]


# --8<-- [start: logging_scoped]
with rt.Session(logging_setting="DEBUG", log_file="my_logs.log") as runner:
    pass
# --8<-- [end: logging_scoped]

# --8<-- [start: logging_railtown]
import railtownai

RAILTOWN_API_KEY = "YOUR_RAILTOWN_API_KEY"
railtownai.init(RAILTOWN_API_KEY)
# --8<-- [end: logging_railtown]

# --8<-- [start: logging_loggly]
import logging
from loggly.handlers import HTTPSHandler

LOGGLY_TOKEN = "YOUR_LOGGLY_TOKEN"
https_handler = HTTPSHandler(
    url=f"https://logs-01.loggly.com/inputs/{LOGGLY_TOKEN}/tag/python"
)
logger = logging.getLogger()
logger.addHandler(https_handler)

# --8<-- [end: logging_loggly]

# --8<-- [start: logging_sentry]
import sentry_sdk

sentry_sdk.init(
    dsn="https://examplePublicKey@o0.ingest.sentry.io/0",
    send_default_pii=True,  # Collects additional metadata
)
# --8<-- [end: logging_sentry]
