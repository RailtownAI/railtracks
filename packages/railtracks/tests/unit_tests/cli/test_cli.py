#!/usr/bin/env python3

"""
Basic unit tests for railtracks CLI functionality
"""

import json
import os
import shutil
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from railtracks.cli import (
    _visual_dependencies_available,
    check_for_ui_update,
    create_railtracks_dir,
    get_remote_ui_version,
    get_script_directory,
    get_stored_ui_version,
    is_port_in_use,
    main,
    save_ui_version,
)
from railtracks.cli.io import (
    _print_update_available,
    print_error,
    print_status,
    print_success,
    print_warning,
)
from railtracks.cli.viz_server import app


class TestUtilityFunctions(unittest.TestCase):
    """Test basic utility functions"""

    def test_get_script_directory(self):
        """Test get_script_directory returns a valid Path"""
        result = get_script_directory()
        self.assertIsInstance(result, Path)
        self.assertTrue(result.exists())
        self.assertTrue(result.is_dir())

    @patch('builtins.print')
    def test_print_functions(self, mock_print):
        """Test all print functions format messages correctly"""
        test_message = "test message"

        print_status(test_message)
        mock_print.assert_called_with("[railtracks] test message")

        print_success(test_message)
        mock_print.assert_called_with("[railtracks] test message")

        print_warning(test_message)
        mock_print.assert_called_with("[railtracks] test message")

        print_error(test_message)
        mock_print.assert_called_with("[railtracks] test message")


class TestCreateRailtracksDir(unittest.TestCase):
    """Test create_railtracks_dir function"""

    def setUp(self):
        """Set up temporary directory for testing"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        """Clean up temporary directory"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    @patch('railtracks.cli.print_status')
    @patch('railtracks.cli.print_success')
    def test_create_railtracks_dir_new(self, mock_success, mock_status):
        """Test creating .railtracks directory when it doesn't exist"""
        # Ensure .railtracks doesn't exist
        railtracks_path = Path(".railtracks")
        self.assertFalse(railtracks_path.exists())

        create_railtracks_dir()

        # Should exist now
        self.assertTrue(railtracks_path.exists())
        self.assertTrue(railtracks_path.is_dir())

        # Should have called print functions
        mock_status.assert_called()
        mock_success.assert_called()

    @patch('railtracks.cli.print_status')
    @patch('railtracks.cli.print_success')
    def test_create_railtracks_dir_existing(self, mock_success, mock_status):
        """Test when .railtracks directory already exists"""
        # Create .railtracks directory first
        railtracks_path = Path(".railtracks")
        railtracks_path.mkdir()

        create_railtracks_dir()

        # Should still exist
        self.assertTrue(railtracks_path.exists())
        self.assertTrue(railtracks_path.is_dir())

    @patch('railtracks.cli.print_status')
    @patch('railtracks.cli.print_success')
    def test_create_railtracks_dir_gitignore_new(self, mock_success, mock_status):
        """Test creating .gitignore with .railtracks entry"""
        create_railtracks_dir()

        # Should create .gitignore
        gitignore_path = Path(".gitignore")
        self.assertTrue(gitignore_path.exists())

        # Should contain .railtracks
        with open(gitignore_path) as f:
            content = f.read()
        self.assertIn(".railtracks", content)

    @patch('railtracks.cli.print_status')
    @patch('railtracks.cli.print_success')
    def test_create_railtracks_dir_gitignore_existing(self, mock_success, mock_status):
        """Test adding .railtracks to existing .gitignore"""
        # Create existing .gitignore
        gitignore_path = Path(".gitignore")
        with open(gitignore_path, "w") as f:
            f.write("*.pyc\n__pycache__/\n")

        create_railtracks_dir()

        # Should contain both old and new entries
        with open(gitignore_path) as f:
            content = f.read()
        self.assertIn("*.pyc", content)
        self.assertIn(".railtracks", content)

    @patch('railtracks.cli.print_status')
    def test_create_railtracks_dir_gitignore_already_present(self, mock_status):
        """Test when .railtracks is already in .gitignore"""
        # Create .gitignore with .railtracks already present
        gitignore_path = Path(".gitignore")
        with open(gitignore_path, "w") as f:
            f.write("*.pyc\n.railtracks\n__pycache__/\n")

        original_content = gitignore_path.read_text()

        create_railtracks_dir()

        # Content should be unchanged
        new_content = gitignore_path.read_text()
        self.assertEqual(original_content, new_content)


class TestFastAPIEndpoints(unittest.TestCase):
    """Test FastAPI endpoints"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Create .railtracks directory
        railtracks_dir = Path(os.environ.get("RAILTRACKS_HOME", ".railtracks"))
        railtracks_dir.mkdir()

        # Create test JSON files in root
        self.test_files = {
            "simple.json": {"test": "data"},
            "my agent session.json": {"agent": "session", "data": "test"},
            "file with spaces.json": {"spaces": "test"},
            "special-chars!@#.json": {"special": "chars"}
        }

        for filename, content in self.test_files.items():
            file_path = railtracks_dir / filename
            with open(file_path, "w") as f:
                json.dump(content, f)

        # Create test client
        self.client = TestClient(app)

    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_get_evaluations_empty(self):
        """Test /api/evaluations endpoint with no data directory"""
        response = self.client.get("/api/evaluations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_evaluations_with_data(self):
        """Test /api/evaluations endpoint with data"""
        # Create evaluations directory and files
        evaluations_dir = Path(".railtracks/data/evaluations")
        evaluations_dir.mkdir(parents=True)

        eval1 = {"id": "eval1", "score": 0.95}
        eval2 = {"id": "eval2", "score": 0.87}

        with open(evaluations_dir / "eval1.json", "w") as f:
            json.dump(eval1, f)
        with open(evaluations_dir / "eval2.json", "w") as f:
            json.dump(eval2, f)

        response = self.client.get("/api/evaluations")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertIn(eval1, data)
        self.assertIn(eval2, data)

    def test_get_sessions_empty(self):
        """Test /api/sessions endpoint with no data directory"""
        response = self.client.get("/api/sessions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_sessions_with_data(self):
        """Test /api/sessions endpoint with data"""
        # Create sessions directory and files
        sessions_dir = Path(".railtracks/data/sessions")
        sessions_dir.mkdir(parents=True)

        session1 = {"id": "session1", "status": "completed"}
        session2 = {"id": "session2", "status": "failed"}

        with open(sessions_dir / "session1.json", "w") as f:
            json.dump(session1, f)
        with open(sessions_dir / "session2.json", "w") as f:
            json.dump(session2, f)

        response = self.client.get("/api/sessions")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertIn(session1, data)
        self.assertIn(session2, data)

    def test_get_session_by_guid(self):
        """Test /api/sessions/{guid} endpoint with existing session"""
        # Create sessions directory and file
        sessions_dir = Path(".railtracks/data/sessions")
        sessions_dir.mkdir(parents=True)

        session_data = {"id": "test-guid-123", "status": "completed", "data": "test"}
        guid = "test-guid-123"

        with open(sessions_dir / f"{guid}.json", "w") as f:
            json.dump(session_data, f)

        response = self.client.get(f"/api/sessions/{guid}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), session_data)

    def test_get_session_by_guid_with_flow_name_prefix(self):
        """Test /api/sessions/{guid} finds session saved as {flow_name}_{guid}.json"""
        sessions_dir = Path(".railtracks/data/sessions")
        sessions_dir.mkdir(parents=True)

        session_data = {"session_id": "abc-123-guid", "flow_name": "Stock Analysis"}
        guid = "abc-123-guid"
        with open(sessions_dir / f"Stock Analysis_{guid}.json", "w") as f:
            json.dump(session_data, f)

        response = self.client.get(f"/api/sessions/{guid}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), session_data)

    def test_get_session_by_guid_not_found(self):
        """Test /api/sessions/{guid} endpoint with non-existent session"""
        # Create sessions directory but no file
        sessions_dir = Path(".railtracks/data/sessions")
        sessions_dir.mkdir(parents=True)

        response = self.client.get("/api/sessions/nonexistent-guid")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": "Session not found"})

    def test_get_session_by_guid_invalid_json(self):
        """Test /api/sessions/{guid} endpoint with invalid JSON file"""
        # Create sessions directory and invalid JSON file
        sessions_dir = Path(".railtracks/data/sessions")
        sessions_dir.mkdir(parents=True)

        guid = "invalid-json-guid"
        invalid_file = sessions_dir / f"{guid}.json"
        with open(invalid_file, "w") as f:
            f.write("{ invalid json }")

        response = self.client.get(f"/api/sessions/{guid}")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        self.assertIn("Invalid JSON", response.json()["error"])


class TestPortChecking(unittest.TestCase):
    """Test port checking functionality"""

    def test_is_port_in_use_available_port(self):
        """Test is_port_in_use returns False for available port"""
        # Use a high port number that's unlikely to be in use
        test_port = 65535
        result = is_port_in_use(test_port)
        self.assertFalse(result)

    def test_is_port_in_use_occupied_port(self):
        """Test is_port_in_use returns True for occupied port"""
        # Create a socket to occupy a port
        test_port = 65534
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
            test_socket.bind(('localhost', test_port))
            test_socket.listen(1)

            # Now check if the port is in use
            result = is_port_in_use(test_port)
            self.assertTrue(result)

    @patch('railtracks.cli.print_error')
    @patch('railtracks.cli.is_port_in_use', return_value=True)
    @patch('railtracks.cli._visual_dependencies_available', return_value=True)
    @patch('railtracks.cli.sys.argv', ['railtracks', 'viz'])
    def test_viz_command_port_in_use(self, _mock_deps, _mock_port, mock_print_error):
        """Test viz command exits with error when port is in use"""
        with self.assertRaises(SystemExit) as ctx:
            main()

        self.assertEqual(ctx.exception.code, 1)
        mock_print_error.assert_any_call("Port 3030 is already in use!")

    def test_viz_command_port_available(self):
        """Test viz command behavior when port is available"""
        # Test that the port checking function works correctly
        # This is more of an integration test of the port checking logic

        # Test with a port that should be available
        test_port = 65533
        result = is_port_in_use(test_port)

        # The result should be a boolean
        self.assertIsInstance(result, bool)

        # If the port is available, we should be able to bind to it
        if not result:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
                try:
                    test_socket.bind(('localhost', test_port))
                    # If we get here, the port was indeed available
                    self.assertFalse(result)
                except OSError:
                    # Port became unavailable between checks
                    pass

    def test_port_checking_with_different_ports(self):
        """Test port checking with various port numbers"""
        # Test with a range of ports
        test_ports = [8080, 3000, 5000, 9000]

        for port in test_ports:
            result = is_port_in_use(port)
            # Result should be boolean
            self.assertIsInstance(result, bool)

            # If port is available, we should be able to bind to it
            if not result:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
                    try:
                        test_socket.bind(('localhost', port))
                        # If we get here, the port was indeed available
                        self.assertFalse(result)
                    except OSError:
                        # Port became unavailable between checks
                        pass

    def test_port_checking_edge_cases(self):
        """Test port checking with edge cases"""
        # Test with invalid port numbers
        with self.assertRaises(OverflowError):
            is_port_in_use(-1)

        # Port 0 is actually valid (lets OS assign port)
        result = is_port_in_use(0)
        self.assertIsInstance(result, bool)

        with self.assertRaises(OverflowError):
            is_port_in_use(65536)  # Port number too high

    @patch('railtracks.cli.socket.socket')
    def test_port_checking_socket_error(self, mock_socket_class):
        """Test port checking when socket operations fail"""
        # Mock socket to raise OSError
        mock_socket = MagicMock()
        mock_socket.bind.side_effect = OSError("Socket error")
        mock_socket_class.return_value.__enter__.return_value = mock_socket

        result = is_port_in_use(3030)
        self.assertTrue(result)  # Should return True when socket fails to bind

class TestUIVersionTracking(unittest.TestCase):
    """Test UI version persistence and update-check logic"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        # Create .railtracks dir so the version file path is valid
        Path(".railtracks").mkdir()

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    # --- get_stored_ui_version ---

    def test_get_stored_ui_version_no_file(self):
        """Returns None when the version file does not exist"""
        result = get_stored_ui_version()
        self.assertIsNone(result)

    def test_get_stored_ui_version_with_file(self):
        """Returns the stored version string when the file exists"""
        Path(".railtracks/.ui_version").write_text('"abc-etag-123"')
        result = get_stored_ui_version()
        self.assertEqual(result, '"abc-etag-123"')

    def test_get_stored_ui_version_strips_whitespace(self):
        """Strips leading/trailing whitespace from the stored value"""
        Path(".railtracks/.ui_version").write_text('  etag-value  \n')
        result = get_stored_ui_version()
        self.assertEqual(result, 'etag-value')

    # --- save_ui_version ---

    def test_save_ui_version_writes_file(self):
        """Writes the version string to the version file"""
        save_ui_version('"new-etag"')
        content = Path(".railtracks/.ui_version").read_text()
        self.assertEqual(content, '"new-etag"')

    def test_save_ui_version_overwrites_existing(self):
        """Overwrites an existing version file"""
        Path(".railtracks/.ui_version").write_text('old-etag')
        save_ui_version('new-etag')
        self.assertEqual(Path(".railtracks/.ui_version").read_text(), 'new-etag')

    # --- get_remote_ui_version ---

    @patch('railtracks.cli.urllib.request.urlopen')
    def test_get_remote_ui_version_returns_etag(self, mock_urlopen):
        """Returns the ETag header from the remote HEAD response"""
        mock_response = MagicMock()
        mock_response.headers.get.side_effect = lambda k: '"remote-etag"' if k == 'ETag' else None
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = get_remote_ui_version()
        self.assertEqual(result, '"remote-etag"')

    @patch('railtracks.cli.urllib.request.urlopen')
    def test_get_remote_ui_version_falls_back_to_last_modified(self, mock_urlopen):
        """Falls back to Last-Modified when ETag is absent"""
        mock_response = MagicMock()
        mock_response.headers.get.side_effect = lambda k: 'Mon, 16 Mar 2026 00:00:00 GMT' if k == 'Last-Modified' else None
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = get_remote_ui_version()
        self.assertEqual(result, 'Mon, 16 Mar 2026 00:00:00 GMT')

    @patch('railtracks.cli.urllib.request.urlopen', side_effect=Exception('network error'))
    def test_get_remote_ui_version_returns_none_on_error(self, _mock_urlopen):
        """Returns None when the network request fails"""
        result = get_remote_ui_version()
        self.assertIsNone(result)

    # --- check_for_ui_update ---

    @patch('railtracks.cli._print_update_available')
    def test_check_no_stored_version_skips_check(self, mock_print):
        """Does nothing when no version is stored (first-time install)"""
        check_for_ui_update()
        mock_print.assert_not_called()

    @patch('railtracks.cli.get_remote_ui_version', return_value=None)
    @patch('railtracks.cli._print_update_available')
    def test_check_remote_unavailable_skips_warning(self, mock_print, _mock_remote):
        """Does not warn when the remote version cannot be fetched"""
        Path(".railtracks/.ui_version").write_text('stored-etag')
        check_for_ui_update()
        mock_print.assert_not_called()

    @patch('railtracks.cli.get_remote_ui_version', return_value='stored-etag')
    @patch('railtracks.cli._print_update_available')
    def test_check_versions_match_no_warning(self, mock_print, _mock_remote):
        """Does not warn when stored and remote versions are the same"""
        Path(".railtracks/.ui_version").write_text('stored-etag')
        check_for_ui_update()
        mock_print.assert_not_called()

    @patch('railtracks.cli.get_remote_ui_version', return_value='new-etag')
    @patch('railtracks.cli._print_update_available')
    def test_check_versions_differ_shows_warning(self, mock_print, _mock_remote):
        """Calls _print_update_available when remote version differs from stored"""
        Path(".railtracks/.ui_version").write_text('old-etag')
        check_for_ui_update()
        mock_print.assert_called_once()

    # --- _print_update_available ---

    @patch('builtins.print')
    def test_print_update_available_contains_update_command(self, mock_print):
        """Printed message includes the 'railtracks update' command"""
        _print_update_available()
        mock_print.assert_called_once()
        printed_text = mock_print.call_args[0][0]
        self.assertIn('railtracks update', printed_text)

    # --- UI_VERSION_FILE derivation ---

    def test_ui_version_file_derived_from_cli_directory(self):
        """UI_VERSION_FILE is derived from cli_directory, not hardcoded separately"""
        import railtracks.cli as cli_module
        self.assertTrue(
            cli_module.UI_VERSION_FILE.startswith(cli_module.cli_directory),
            "UI_VERSION_FILE should start with cli_directory so they stay in sync",
        )

    # --- temp file cleanup on failure ---

    @patch('railtracks.cli.sys.exit')
    @patch('railtracks.cli.urllib.request.urlopen')
    def test_temp_file_deleted_on_extraction_failure(self, mock_urlopen, mock_exit):
        """Temp zip file is cleaned up even when zip extraction fails"""
        # Provide a response that returns invalid zip bytes
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.headers.get.return_value = None
        mock_response.read.return_value = b"not a zip file"
        mock_urlopen.return_value = mock_response

        captured_paths = []
        real_named_temporary_file = tempfile.NamedTemporaryFile

        def capturing_ntf(**kwargs):
            f = real_named_temporary_file(**kwargs)
            captured_paths.append(f.name)
            return f

        with patch('railtracks.cli.tempfile.NamedTemporaryFile', side_effect=capturing_ntf):
            import railtracks.cli as cli_module
            cli_module.download_and_extract_ui()

        # sys.exit should have been called due to BadZipFile
        mock_exit.assert_called()
        # The temp file should have been deleted by the finally block
        for path in captured_paths:
            self.assertFalse(os.path.exists(path), f"Temp file {path} was not cleaned up")

    # --- background thread for update check ---

    @patch('railtracks.cli.check_for_ui_update')
    @patch('railtracks.cli.viz_server.RailtracksServer')
    @patch('railtracks.cli.create_railtracks_dir')
    @patch('railtracks.cli.is_port_in_use', return_value=False)
    @patch('railtracks.cli._visual_dependencies_available', return_value=True)
    @patch('railtracks.cli.sys.argv', ['railtracks', 'viz'])
    def test_viz_runs_update_check_in_background_thread(self, _mock_deps, _mock_port,
                                                         _mock_dir, mock_server,
                                                         mock_check):
        """viz command runs check_for_ui_update in a daemon thread, not blocking main"""
        thread_kwargs = {}

        real_thread = threading.Thread

        def capturing_thread(**kwargs):
            if kwargs.get('target') is mock_check:
                thread_kwargs.update(kwargs)
            return real_thread(**kwargs)

        mock_server_instance = MagicMock()
        mock_server.return_value = mock_server_instance

        import railtracks.cli as cli_module
        with patch('railtracks.cli.threading.Thread', side_effect=capturing_thread):
            cli_module.main()

        self.assertIs(thread_kwargs.get('target'), mock_check,
                      "check_for_ui_update should be the thread target")
        self.assertTrue(thread_kwargs.get('daemon'),
                        "Update-check thread should be a daemon thread")


class TestMainDispatch(unittest.TestCase):
    """Test the main() CLI entrypoint dispatching"""

    @patch('railtracks.cli._print_help')
    @patch('railtracks.cli.sys.argv', ['railtracks'])
    def test_no_args_shows_help_and_exits(self, mock_help):
        """main() with no command shows help and exits"""
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)
        mock_help.assert_called_once()

    @patch('builtins.print')
    @patch('railtracks.cli.sys.argv', ['railtracks', 'bogus'])
    def test_unknown_command_exits(self, mock_print):
        """main() with an unknown command prints error and exits"""
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)
        printed = [call[0][0] for call in mock_print.call_args_list]
        self.assertTrue(any('bogus' in s for s in printed))

    @patch('railtracks.cli.print_error')
    @patch('railtracks.cli.print_status')
    @patch('railtracks.cli._visual_dependencies_available', return_value=False)
    @patch('railtracks.cli.sys.argv', ['railtracks', 'viz'])
    def test_viz_exits_when_visual_deps_missing(self, _mock_deps,
                                                mock_status, mock_error):
        """main() viz exits gracefully when visual extras are not installed"""
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)
        error_messages = ' '.join(c[0][0] for c in mock_error.call_args_list)
        self.assertIn('optional dependencies', error_messages)

    @patch('railtracks.cli.init_railtracks')
    @patch('railtracks.cli.sys.argv', ['railtracks', 'init'])
    def test_init_command(self, mock_init):
        """main() dispatches 'init' to init_railtracks()"""
        main()
        mock_init.assert_called_once()

    @patch('railtracks.cli.update_railtracks')
    @patch('railtracks.cli.sys.argv', ['railtracks', 'update'])
    def test_update_command(self, mock_update):
        """main() dispatches 'update' to update_railtracks()"""
        main()
        mock_update.assert_called_once()

    @patch('railtracks.cli.print_error')
    @patch('railtracks.cli.sys.argv', ['railtracks', 'add'])
    def test_add_no_spec_exits(self, mock_error):
        """main() add with no spec shows usage and exits"""
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)


class TestVisualDepsCheck(unittest.TestCase):
    """Test _visual_dependencies_available()"""

    @patch('railtracks.cli.importlib.util.find_spec')
    def test_returns_true_when_both_present(self, mock_find_spec):
        mock_find_spec.return_value = MagicMock()
        self.assertTrue(_visual_dependencies_available())

    @patch('railtracks.cli.importlib.util.find_spec')
    def test_returns_false_when_fastapi_missing(self, mock_find_spec):
        mock_find_spec.side_effect = lambda name: None if name == 'fastapi' else MagicMock()
        self.assertFalse(_visual_dependencies_available())

    @patch('railtracks.cli.importlib.util.find_spec')
    def test_returns_false_when_uvicorn_missing(self, mock_find_spec):
        mock_find_spec.side_effect = lambda name: None if name == 'uvicorn' else MagicMock()
        self.assertFalse(_visual_dependencies_available())


class TestLazyGetattr(unittest.TestCase):
    """Test __getattr__ lazy exports on railtracks.cli"""

    def test_app_resolves(self):
        """railtracks.cli.app lazily loads the FastAPI app from viz_server"""
        import railtracks.cli as cli_module
        self.assertIsNotNone(cli_module.app)
        from railtracks.cli.viz_server import app as direct_app
        self.assertIs(cli_module.app, direct_app)

    def test_railtracks_server_resolves(self):
        """railtracks.cli.RailtracksServer lazily loads the class from viz_server"""
        import railtracks.cli as cli_module
        from railtracks.cli.viz_server import RailtracksServer
        self.assertIs(cli_module.RailtracksServer, RailtracksServer)

    def test_unknown_attr_raises(self):
        """Accessing an undefined name raises AttributeError"""
        import railtracks.cli as cli_module
        with self.assertRaises(AttributeError):
            _ = cli_module.nonexistent_thing


if __name__ == "__main__":
    unittest.main()
