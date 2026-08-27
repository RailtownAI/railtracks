"""Streamlit setup for run.py -- one form, nothing else.

Not meant to teach anything about `pre_verifier` or webhooks -- see run.py
for that. This file exists only to give a human something to actually
click, standing in for a real approval UI (Slack, an internal admin panel,
...). Launched automatically by run.py via `streamlit run`; not meant to be
run directly.

Requires `streamlit` (not a railtracks dependency, just this demo's UI):
`uv pip install streamlit`.
"""

import json
import urllib.request

import streamlit as st

WEBHOOK_URL = "http://127.0.0.1:8765/resolve/A1"


def send_decision(accepted: bool, comment: str) -> None:
    body = json.dumps({"accepted": accepted, "comment": comment or None}).encode()
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)


st.title("Refund approval")
st.write("Refund of $42.50 for order A1 is waiting on your decision.")

comment = st.text_area("Comment (used if you reject)")

decided = False
col1, col2 = st.columns(2)

if col1.button("Approve", type="primary"):
    st.success("Approved -- check the terminal running the demo.")
    send_decision(accepted=True, comment="")

if col2.button("Reject"):
    st.error("Rejected -- check the terminal running the demo.")
    send_decision(accepted=False, comment=comment)
