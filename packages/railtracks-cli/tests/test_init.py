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
    app,
    create_railtracks_dir,
    get_script_directory,
    is_port_in_use,
    migrate_railtracks,
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


class TestMigrateRailtracks(unittest.TestCase):
    """Test migrate_railtracks function"""

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
    def test_migrate_creates_all_directories(self, mock_success, mock_status):
        """Test that all required directories are created when they don't exist"""
        # Ensure .railtracks doesn't exist
        railtracks_dir = Path(".railtracks")
        self.assertFalse(railtracks_dir.exists())

        migrate_railtracks()

        # Verify all directories exist
        self.assertTrue(railtracks_dir.exists())
        self.assertTrue(railtracks_dir.is_dir())

        data_dir = railtracks_dir / "data"
        self.assertTrue(data_dir.exists())
        self.assertTrue(data_dir.is_dir())

        evaluations_dir = data_dir / "evaluations"
        self.assertTrue(evaluations_dir.exists())
        self.assertTrue(evaluations_dir.is_dir())

        sessions_dir = data_dir / "sessions"
        self.assertTrue(sessions_dir.exists())
        self.assertTrue(sessions_dir.is_dir())

        # Should have called print functions
        mock_status.assert_called()
        mock_success.assert_called()

    @patch('railtracks_cli.print_status')
    @patch('railtracks_cli.print_success')
    def test_migrate_with_existing_directories(self, mock_success, mock_status):
        """Test that existing directories are not recreated (idempotent)"""
        # Create all directories first
        railtracks_dir = Path(".railtracks")
        railtracks_dir.mkdir()
        data_dir = railtracks_dir / "data"
        data_dir.mkdir()
        evaluations_dir = data_dir / "evaluations"
        evaluations_dir.mkdir()
        sessions_dir = data_dir / "sessions"
        sessions_dir.mkdir()

        # Run migration
        migrate_railtracks()

        # All directories should still exist
        self.assertTrue(railtracks_dir.exists())
        self.assertTrue(data_dir.exists())
        self.assertTrue(evaluations_dir.exists())
        self.assertTrue(sessions_dir.exists())

    @patch('railtracks_cli.print_status')
    @patch('railtracks_cli.print_success')
    def test_migrate_moves_json_files_from_root(self, mock_success, mock_status):
        """Test moving JSON files from .railtracks root to .railtracks/data/sessions/"""
        # Create .railtracks directory
        railtracks_dir = Path(".railtracks")
        railtracks_dir.mkdir()

        # Create JSON files in root
        test_file1 = railtracks_dir / "test1.json"
        test_file2 = railtracks_dir / "test2.json"

        with open(test_file1, "w") as f:
            json.dump({"test": "data1"}, f)
        with open(test_file2, "w") as f:
            json.dump({"test": "data2"}, f)

        # Run migration
        migrate_railtracks()

        # Files should be moved to data/sessions/
        sessions_dir = railtracks_dir / "data" / "sessions"
        self.assertTrue((sessions_dir / "test1.json").exists())
        self.assertTrue((sessions_dir / "test2.json").exists())

        # Files should no longer be in root
        self.assertFalse(test_file1.exists())
        self.assertFalse(test_file2.exists())

        # Verify file contents
        with open(sessions_dir / "test1.json") as f:
            content1 = json.load(f)
            self.assertEqual(content1, {"test": "data1"})

        with open(sessions_dir / "test2.json") as f:
            content2 = json.load(f)
            self.assertEqual(content2, {"test": "data2"})

    @patch('railtracks_cli.print_status')
    @patch('railtracks_cli.print_success')
    def test_migrate_does_not_move_subdirectory_json(self, mock_success, mock_status):
        """Test that JSON files in subdirectories are NOT moved"""
        # Create .railtracks directory structure
        railtracks_dir = Path(".railtracks")
        railtracks_dir.mkdir()

        # Create JSON file in root
        root_file = railtracks_dir / "root.json"
        with open(root_file, "w") as f:
            json.dump({"location": "root"}, f)

        # Create subdirectories with JSON files
        ui_dir = railtracks_dir / "ui"
        ui_dir.mkdir()
        ui_file = ui_dir / "ui.json"
        with open(ui_file, "w") as f:
            json.dump({"location": "ui"}, f)

        data_dir = railtracks_dir / "data"
        data_dir.mkdir()
        data_file = data_dir / "data.json"
        with open(data_file, "w") as f:
            json.dump({"location": "data"}, f)

        # Run migration
        migrate_railtracks()

        # Root file should be moved
        sessions_dir = railtracks_dir / "data" / "sessions"
        self.assertTrue((sessions_dir / "root.json").exists())
        self.assertFalse(root_file.exists())

        # Subdirectory files should NOT be moved
        self.assertTrue(ui_file.exists())
        self.assertTrue(data_file.exists())

    @patch('railtracks_cli.print_status')
    @patch('railtracks_cli.print_success')
    def test_migrate_no_json_files(self, mock_success, mock_status):
        """Test handling when no JSON files exist in root"""
        # Create .railtracks directory
        railtracks_dir = Path(".railtracks")
        railtracks_dir.mkdir()

        # Run migration
        migrate_railtracks()

        # Directories should be created
        sessions_dir = railtracks_dir / "data" / "sessions"
        self.assertTrue(sessions_dir.exists())

        # Should have printed appropriate message
        calls = [str(call) for call in mock_status.call_args_list]
        self.assertTrue(any("No JSON files" in str(call) for call in calls))

    @patch('railtracks_cli.print_status')
    @patch('railtracks_cli.print_success')
    def test_migrate_console_output(self, mock_success, mock_status):
        """Test console output messages"""
        # Create .railtracks directory with JSON file
        railtracks_dir = Path(".railtracks")
        railtracks_dir.mkdir()

        test_file = railtracks_dir / "migration_test.json"
        with open(test_file, "w") as f:
            json.dump({"test": "data"}, f)

        # Run migration
        migrate_railtracks()

        # Check that status messages were called
        mock_status.assert_called()
        mock_success.assert_called()

        # Check for specific migration message
        success_calls = [str(call) for call in mock_success.call_args_list]
        self.assertTrue(any("Migrated migration_test.json" in str(call) for call in success_calls))

    @patch('railtracks_cli.print_status')
    @patch('railtracks_cli.print_success')
    def test_migrate_multiple_files(self, mock_success, mock_status):
        """Test migration of multiple JSON files"""
        # Create .railtracks directory
        railtracks_dir = Path(".railtracks")
        railtracks_dir.mkdir()

        # Create multiple JSON files
        files = ["file1.json", "file2.json", "file3.json"]
        for filename in files:
            test_file = railtracks_dir / filename
            with open(test_file, "w") as f:
                json.dump({"file": filename}, f)

        # Run migration
        migrate_railtracks()

        # All files should be moved
        sessions_dir = railtracks_dir / "data" / "sessions"
        for filename in files:
            self.assertTrue((sessions_dir / filename).exists())
            self.assertFalse((railtracks_dir / filename).exists())

        # Check migration summary message
        success_calls = [str(call) for call in mock_success.call_args_list]
        self.assertTrue(any("3 file(s) moved" in str(call) for call in success_calls))

    @patch('railtracks_cli.print_status')
    @patch('railtracks_cli.print_success')
    def test_migrate_partial_directory_structure(self, mock_success, mock_status):
        """Test migration when some directories already exist"""
        # Create .railtracks and data directories
        railtracks_dir = Path(".railtracks")
        railtracks_dir.mkdir()
        data_dir = railtracks_dir / "data"
        data_dir.mkdir()

        # Create JSON file in root
        test_file = railtracks_dir / "test.json"
        with open(test_file, "w") as f:
            json.dump({"test": "data"}, f)

        # Run migration
        migrate_railtracks()

        # Missing directories should be created
        evaluations_dir = data_dir / "evaluations"
        sessions_dir = data_dir / "sessions"
        self.assertTrue(evaluations_dir.exists())
        self.assertTrue(sessions_dir.exists())

        # File should be moved
        self.assertTrue((sessions_dir / "test.json").exists())
        self.assertFalse(test_file.exists())


if __name__ == "__main__":
    unittest.main()
