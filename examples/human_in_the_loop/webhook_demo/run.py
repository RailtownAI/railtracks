"""HIL backend: webhook-style external resolution.

Register a pending approval, then suspend the coroutine on an `asyncio.Future`
until something *outside* it resolves it. In real life that's a Slack button
click or a UI callback hitting a webhook route; this demo makes that literal
instead of simulating it: a two-button Streamlit app (`webhook_setup.py`,
launched automatically below) is the human's approval UI, and clicking
Approve or Reject sends a real HTTP POST (with an optional comment on
reject) to the `/resolve/{order_id}` route this file exposes with FastAPI.
That request handler is what resolves the pending future -- the same thing
a real webhook handler receiving a Slack interaction payload would do.
`localhost` is standing in for the public URL a real webhook would be
registered at; nothing else here is faked.

`webhook_setup.py` is deliberately uninteresting -- it's just enough
Streamlit to give a human a button to click, not part of what this demo is
teaching. Everything relevant to `pre_verifier`/webhooks lives in this file.

Needs `streamlit` for the button UI (not a railtracks dependency, just this
demo's stand-in for a real approval UI): `uv pip install streamlit`.
(`uv run --with streamlit` also works standalone, but in this repo's uv
workspace it writes streamlit into the root pyproject.toml/uv.lock as a real
dependency as a side effect -- `uv pip install` avoids that.)

Run: uv run python examples/human_in_the_loop/webhook_demo/run.py
"""

import asyncio
import subprocess
import sys
from pathlib import Path

import railtracks as rt
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from railtracks.middleware import Verdict, VerifierRejectedError
from railtracks.prebuilt.middleware import pre_verifier

##### The webhook route an external event (here: the Streamlit buttons) hits #####

_pending: dict[str, asyncio.Future] = {}

webhook_app = FastAPI()


class WebhookDecision(BaseModel):
    accepted: bool
    comment: str | None = None


@webhook_app.post("/resolve/{order_id}")
async def resolve_webhook(order_id: str, decision: WebhookDecision) -> dict:
    """A real webhook route -- whatever receives the external event (a Slack
    interaction handler, a UI callback, ... here: the Streamlit buttons)
    calls this to deliver the human's decision, accept or reject, with an
    optional comment. `async def` so this runs directly on the same event
    loop the pending future belongs to, rather than FastAPI's sync-route
    thread pool -- otherwise resolving the future would need cross-thread
    signaling instead of a plain `set_result`."""
    future = _pending.pop(order_id, None)
    if future is not None and not future.done():
        default_comment = (
            "approved via webhook" if decision.accepted else "rejected via webhook"
        )
        future.set_result(
            Verdict(
                accepted=decision.accepted, comment=decision.comment or default_comment
            )
        )
    return {"resolved": future is not None}


async def ask_via_webhook(order_id: str, amount: float) -> Verdict:
    """Register a pending approval and wait for it to be resolved externally."""
    future: asyncio.Future = asyncio.get_running_loop().create_future()
    _pending[order_id] = future

    print(
        f"Waiting for approval of refund {amount} for order {order_id} -- "
        f"click Approve or Reject in the browser tab that just opened..."
    )
    return await future


hil_gate = pre_verifier(ask_via_webhook, timeout=180, name="webhook_hil")

##### Agent / tool gated by the HIL backend #####


@rt.function_node(middleware=[hil_gate])
def refund(order_id: str, amount: float) -> str:
    """Refund an order.

    Args:
        order_id (str): The order to refund.
        amount (float): The amount to refund.
    """
    return f"refunded {amount} for {order_id}"


refund_flow = rt.Flow(name="webhook_refund_flow", entry_point=refund)


async def main():
    server = uvicorn.Server(
        uvicorn.Config(webhook_app, host="127.0.0.1", port=8765, log_level="warning")
    )
    server_task = asyncio.create_task(server.serve())

    ui_script = Path(__file__).with_name("webhook_setup.py")
    ui_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ui_script)]
    )

    try:
        result = await refund_flow.ainvoke(order_id="A1", amount=42.50)
        print(result)
    except VerifierRejectedError as e:
        print(f"Refund declined: {e}")
    finally:
        ui_process.terminate()
        server.should_exit = True
        await server_task


if __name__ == "__main__":
    asyncio.run(main())
