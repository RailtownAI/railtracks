# Shared CLI constants (no FastAPI / heavy imports).

cli_name = "railtracks"
cli_directory = ".railtracks"
DEFAULT_PORT = 3030
BETA_PORT = 3031
BETA_UI_URL_ENV = "RAILTRACKS_BETA_UI_URL"

# TODO: Once we are releasing to PyPi change this to the release asset instead
latest_ui_url = "https://railtownazureb2c.blob.core.windows.net/cdn/rc-viz/latest.zip"

# Beta UI zip — an optional packaged default for `railtracks viz --beta`.
# Development builds and private beta channels can supply the URL at runtime
# through BETA_UI_URL_ENV without patching the installed package.
beta_ui_url = "https://railtracksstorage.blob.core.windows.net/railtrackswebsite/v2-visualizer/v2.0.0-beta.zip"
