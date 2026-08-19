# Shared CLI constants (no FastAPI / heavy imports).

cli_name = "railtracks"
cli_directory = ".railtracks"
DEFAULT_PORT = 3030
BETA_PORT = 3031

# TODO: Once we are releasing to PyPi change this to the release asset instead
latest_ui_url = "https://railtownazureb2c.blob.core.windows.net/cdn/rc-viz/latest.zip"

# Beta UI zip — download source for `railtracks viz --beta`. Empty until the
# beta build has a hosted asset; while empty, `viz --beta` errors out with a
# clear message rather than attempting the download.
beta_ui_url = ""
