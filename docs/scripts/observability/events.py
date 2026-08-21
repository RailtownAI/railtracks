# --8<-- [start: v2-viz]
from railtracks.observability import JsonlWriter, configure_writers

configure_writers([JsonlWriter()])
# --8<-- [end: v2-viz]