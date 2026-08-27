"""Streamlit setup for webhook_approval_demo.py -- one button, nothing else.

Not meant to teach anything about `pre_verifier` or webhooks -- see
webhook_approval_demo.py for that. This file exists only to give a human
something to actually click, standing in for a real approval UI (Slack, an
internal admin panel, ...). Launched automatically by
webhook_approval_demo.py via `streamlit run`; not meant to be run directly.

Requires `streamlit` (not a railtracks dependency, just this demo's UI).
"""

import urllib.request

import streamlit as st

WEBHOOK_URL = "http://127.0.0.1:8765/approve/A1"

st.title("Refund approval")
st.write("Refund of $42.50 for order A1 is waiting on your approval.")

if st.button("Approve"):
    urllib.request.urlopen(urllib.request.Request(WEBHOOK_URL, method="POST"))
    st.success("Approved -- check the terminal running the demo.")
