import pytest
from requestcompletion.rc_mcp.oauth import (
    InMemoryTokenStorage, CallbackHandler, CallbackServer
)
from unittest.mock import MagicMock, ANY
import time 
import threading

# ======= START InMemoryTokenStorage tests ============

@pytest.mark.asyncio
async def test_token_storage_get_set_tokens_and_clientinfo(
    mock_OAuthToken, mock_OAuthClientInformationFull
):
    storage = InMemoryTokenStorage()
    assert await storage.get_tokens() is None
    assert await storage.get_client_info() is None

    await storage.set_tokens(mock_OAuthToken)
    assert await storage.get_tokens() is mock_OAuthToken

    await storage.set_client_info(mock_OAuthClientInformationFull)
    assert await storage.get_client_info() is mock_OAuthClientInformationFull

# ======= END InMemoryTokenStorage tests ==============


# ======= START CallbackHandler tests =================
def test_callback_handler_handles_success():
    # Simulate OAuth callback with ?code=abc&state=def
    callback_data = {}
    cbh = CallbackHandler.__new__(CallbackHandler)
    cbh.callback_data = callback_data
    cbh.path = "/?code=abc&state=def"

    # Mock methods
    cbh.send_response = MagicMock()
    cbh.send_header = MagicMock()
    cbh.end_headers = MagicMock()
    cbh.wfile = MagicMock()
    cbh.wfile.write = MagicMock()

    cbh.do_GET()

    assert callback_data["authorization_code"] == "abc"
    assert callback_data["state"] == "def"
    cbh.send_response.assert_called_with(200)
    cbh.wfile.write.assert_called()
    # Should produce "Authorization Successful" in HTML
    assert b"Authorization Successful" in cbh.wfile.write.call_args[0][0]

def test_callback_handler_handles_error():
    callback_data = {}
    cbh = CallbackHandler.__new__(CallbackHandler)
    cbh.callback_data = callback_data
    cbh.path = "/?error=access_denied"

    cbh.send_response = MagicMock()
    cbh.send_header = MagicMock()
    cbh.end_headers = MagicMock()
    cbh.wfile = MagicMock()

    cbh.do_GET()

    assert callback_data["error"] == "access_denied"
    cbh.send_response.assert_called_with(400)
    cbh.wfile.write.assert_called()
    assert b"Authorization Failed" in cbh.wfile.write.call_args[0][0]

def test_callback_handler_handles_other():
    callback_data = {}
    cbh = CallbackHandler.__new__(CallbackHandler)
    cbh.callback_data = callback_data
    cbh.path = "/notarealcb"

    cbh.send_response = MagicMock()
    cbh.end_headers = MagicMock()
    cbh.do_GET()
    cbh.send_response.assert_called_with(404)
    cbh.end_headers.assert_called()

# ======= END CallbackHandler tests ==============


# ======= START CallbackServer tests ==============

def test_callback_server_start_stop(
    patch_HTTPServer, patch_threading_Thread
):
    cs = CallbackServer(port=9090)
    handler = cs._create_handler_with_data()
    assert issubclass(handler, CallbackHandler)
    cs.start()
    patch_HTTPServer.assert_called_with(("localhost", 9090), ANY)       # ANY because of handler, already checked handler is a subclass of CallbackHandler
    patch_threading_Thread.assert_called()
    assert cs.server is patch_HTTPServer.return_value
    assert cs.thread is patch_threading_Thread.return_value

    # Simulate server and thread are running
    cs.server = MagicMock()
    cs.thread = MagicMock()
    cs.stop()
    cs.server.shutdown.assert_called()
    cs.server.server_close.assert_called()
    cs.thread.join.assert_called()

def test_callback_server_wait_for_callback_success(patch_time_sleep):
    cs = CallbackServer()
    cs.callback_data["authorization_code"] = None
    # In another thread, set the code after a few calls
    results = []
    def set_code():
        for _ in range(3):
            time.sleep(0.1)
        cs.callback_data["authorization_code"] = "mycode"
    thr = threading.Thread(target=set_code)
    thr.start()
    code = cs.wait_for_callback(timeout=2)
    assert code == "mycode"
    thr.join()

def test_callback_server_wait_for_callback_timeout(patch_time_sleep, patch_time_time):
    cs = CallbackServer()
    cs.callback_data["authorization_code"] = None
    with pytest.raises(Exception, match="Timeout waiting for OAuth callback"):
        cs.wait_for_callback(timeout=1)

def test_callback_server_wait_for_callback_error(patch_time_sleep):
    cs = CallbackServer()
    cs.callback_data["authorization_code"] = None
    cs.callback_data["error"] = "SOME_ERR"
    with pytest.raises(Exception, match="SOME_ERR"):
        cs.wait_for_callback(timeout=1)

def test_callback_server_get_state():
    cs = CallbackServer()
    cs.callback_data["state"] = "xyz789"
    assert cs.get_state() == "xyz789"

# ======= END CallbackServer tests ==================