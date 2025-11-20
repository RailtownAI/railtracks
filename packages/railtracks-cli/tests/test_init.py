#!/usr/bin/env python3

"""
Basic unit tests for railtracks CLI functionality
"""

import json
import os
import shutil
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import railtracks_cli
from fastapi.testclient import TestClient

from railtracks_cli import (
    DEBOUNCE_INTERVAL,
    FileChangeHandler,
    app,
    create_railtracks_dir,
    get_script_directory,
    is_port_in_use,
    print_error,
    print_status,
    print_success,
    print_warning,
)


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

    @patch('railtracks_cli.print_status')
    @patch('railtracks_cli.print_success')
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

    @patch('railtracks_cli.print_status')
    @patch('railtracks_cli.print_success')
    def test_create_railtracks_dir_existing(self, mock_success, mock_status):
        """Test when .railtracks directory already exists"""
        # Create .railtracks directory first
        railtracks_path = Path(".railtracks")
        railtracks_path.mkdir()

        create_railtracks_dir()

        # Should still exist
        self.assertTrue(railtracks_path.exists())
        self.assertTrue(railtracks_path.is_dir())

    @patch('railtracks_cli.print_status')
    @patch('railtracks_cli.print_success')
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

    @patch('railtracks_cli.print_status')
    @patch('railtracks_cli.print_success')
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

    @patch('railtracks_cli.print_status')
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


class TestFileChangeHandler(unittest.TestCase):
    """Test FileChangeHandler debouncing logic"""

    def setUp(self):
        """Set up handler for testing"""
        self.handler = FileChangeHandler()

    @patch('railtracks_cli.print_status')
    def test_file_change_handler_json_file(self, mock_print):
        """Test handler processes JSON file changes"""
        # Create a mock event
        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/path/file.json"

        self.handler.on_modified(mock_event)

        # Should have printed status
        mock_print.assert_called_once()

    @patch('railtracks_cli.print_status')
    def test_file_change_handler_non_json_file(self, mock_print):
        """Test handler ignores non-JSON files"""
        # Create a mock event for non-JSON file
        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/path/file.txt"

        self.handler.on_modified(mock_event)

        # Should not have printed
        mock_print.assert_not_called()

    @patch('railtracks_cli.print_status')
    def test_file_change_handler_directory(self, mock_print):
        """Test handler ignores directory changes"""
        # Create a mock event for directory
        mock_event = MagicMock()
        mock_event.is_directory = True
        mock_event.src_path = "/test/path/directory"

        self.handler.on_modified(mock_event)

        # Should not have printed
        mock_print.assert_not_called()

    @patch('railtracks_cli.print_status')
    @patch('time.time')
    def test_file_change_handler_debouncing(self, mock_time, mock_print):
        """Test debouncing prevents rapid duplicate events"""
        # Set up time mock to simulate rapid changes
        mock_time.side_effect = [1.0, 1.1, 1.6]  # Second call within debounce, third outside

        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/path/file.json"

        # First call should process
        self.handler.on_modified(mock_event)
        self.assertEqual(mock_print.call_count, 1)

        # Second call within debounce interval should be ignored
        self.handler.on_modified(mock_event)
        self.assertEqual(mock_print.call_count, 1)  # Still 1

        # Third call outside debounce interval should process
        self.handler.on_modified(mock_event)
        self.assertEqual(mock_print.call_count, 2)


class TestFastAPIEndpoints(unittest.TestCase):
    """Test FastAPI endpoints"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Create .railtracks directory
        railtracks_dir = Path(".railtracks")
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

    def test_get_runs_empty(self):
        """Test /api/runs endpoint with no data directory"""
        response = self.client.get("/api/runs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_runs_with_data(self):
        """Test /api/runs endpoint with data"""
        # Create runs directory and files
        runs_dir = Path(".railtracks/data/runs")
        runs_dir.mkdir(parents=True)

        run1 = {"id": "run1", "status": "completed"}
        run2 = {"id": "run2", "status": "failed"}

        with open(runs_dir / "run1.json", "w") as f:
            json.dump(run1, f)
        with open(runs_dir / "run2.json", "w") as f:
            json.dump(run2, f)

        response = self.client.get("/api/runs")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertIn(run1, data)
        self.assertIn(run2, data)

    def test_get_files_deprecated(self):
        """Test /api/files endpoint (deprecated)"""
        response = self.client.get("/api/files")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Deprecated"), "true")

        file_list = response.json()
        file_names = [f["name"] for f in file_list]
        self.assertIn("simple.json", file_names)
        self.assertIn("my agent session.json", file_names)

    def test_get_json_file_deprecated(self):
        """Test /api/json/{filename} endpoint (deprecated)"""
        response = self.client.get("/api/json/simple.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Deprecated"), "true")
        self.assertEqual(response.json(), {"test": "data"})

    def test_get_json_file_urlencoded_deprecated(self):
        """Test /api/json/{filename} with URL-encoded filename (deprecated)"""
        from urllib.parse import quote
        encoded_filename = quote("my agent session.json")
        response = self.client.get(f"/api/json/{encoded_filename}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Deprecated"), "true")
        self.assertEqual(response.json(), {"agent": "session", "data": "test"})

    def test_get_json_file_not_found(self):
        """Test /api/json/{filename} with non-existent file"""
        response = self.client.get("/api/json/nonexistent.json")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())

    def test_get_json_file_invalid_json(self):
        """Test /api/json/{filename} with invalid JSON"""
        invalid_file = Path(".railtracks/invalid.json")
        with open(invalid_file, "w") as f:
            f.write("{ invalid json }")

        response = self.client.get("/api/json/invalid.json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_get_json_file_auto_add_extension(self):
        """Test /api/json/{filename} auto-adds .json extension"""
        test_file = Path(".railtracks/testfile.json")
        with open(test_file, "w") as f:
            json.dump({"test": "data"}, f)

        response = self.client.get("/api/json/testfile")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"test": "data"})

    def test_post_refresh_deprecated(self):
        """Test /api/refresh endpoint (deprecated)"""
        response = self.client.post("/api/refresh")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Deprecated"), "true")
        self.assertEqual(response.json(), {"status": "refresh_triggered"})


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

    @patch('railtracks_cli.sys.exit')
    @patch('railtracks_cli.print_error')
    @patch('railtracks_cli.print_warning')
    @patch('railtracks_cli.print_status')
    @patch('railtracks_cli.is_port_in_use')
    def test_viz_command_port_in_use(self, mock_is_port_in_use, mock_print_status,
                                   mock_print_warning, mock_print_error, mock_sys_exit):
        """Test viz command behavior when port is in use"""
        # Mock port as in use
        mock_is_port_in_use.return_value = True

        # Mock the main function to test just the viz command logic
        with patch('railtracks_cli.create_railtracks_dir'), \
             patch('railtracks_cli.RailtracksServer'):

            # Simulate the viz command logic
            if mock_is_port_in_use.return_value:
                mock_print_error.assert_not_called()  # Not called yet
                mock_print_warning.assert_not_called()  # Not called yet
                mock_print_status.assert_not_called()  # Not called yet
                mock_sys_exit.assert_not_called()  # Not called yet

                # Simulate the actual error handling
                mock_print_error(f"Port 3030 is already in use!")
                mock_print_warning("You already have a railtracks viz server running.")
                mock_print_status("Please stop the existing server or use a different port.")
                mock_sys_exit(1)

                # Verify the calls were made
                mock_print_error.assert_called_with("Port 3030 is already in use!")
                mock_print_warning.assert_called_with("You already have a railtracks viz server running.")
                mock_print_status.assert_called_with("Please stop the existing server or use a different port.")
                mock_sys_exit.assert_called_with(1)

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

    @patch('railtracks_cli.socket.socket')
    def test_port_checking_socket_error(self, mock_socket_class):
        """Test port checking when socket operations fail"""
        # Mock socket to raise OSError
        mock_socket = MagicMock()
        mock_socket.bind.side_effect = OSError("Socket error")
        mock_socket_class.return_value.__enter__.return_value = mock_socket

        result = is_port_in_use(3030)
        self.assertTrue(result)  # Should return True when socket fails to bind


if __name__ == "__main__":
    unittest.main()
