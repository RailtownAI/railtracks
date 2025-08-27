#!/usr/bin/env python3

"""
railtracks - A Python development server with file watching and JSON API
Usage: railtracks [command]

Commands:
  init    Initialize railtracks environment (setup directories, download UI)
  viz     Start the railtracks development server

- Checks to see if there is a .railtracks directory
- If not, it creates one (and adds it to the .gitignore)
- If there is a build directory, it runs the build command
- If there is a .railtracks directory, it starts the server

For testing purposes, you can add `alias railtracks="python railtracks.py"` to your .bashrc or .zshrc
"""

import json
import mimetypes
import os
import signal
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

__version__ = "0.1.0"

# TODO: Once we are releasing to PyPi change this to the release asset instead
latest_ui_url = "https://railtownazureb2c.blob.core.windows.net/cdn/rc-viz/latest.zip"

cli_name = "railtracks"
cli_directory = ".railtracks"
DEFAULT_PORT = 3030
DEBOUNCE_INTERVAL = 0.5  # seconds

# Global SSE clients management
sse_clients = set()
sse_clients_lock = threading.Lock()
global_shutdown_request = False


def get_script_directory():
    """Get the directory where this script is located"""
    return Path(__file__).parent.absolute()


def print_status(message):
    print(f"[{cli_name}] {message}")


def print_success(message):
    print(f"[{cli_name}] {message}")


def print_warning(message):
    print(f"[{cli_name}] {message}")


def print_error(message):
    print(f"[{cli_name}] {message}")


def create_railtracks_dir():
    """Create .railtracks directory if it doesn't exist and add to .gitignore"""
    railtracks_dir = Path(cli_directory)
    if not railtracks_dir.exists():
        print_status(f"Creating {cli_directory} directory...")
        railtracks_dir.mkdir(exist_ok=True)
        print_success(f"Created {cli_directory} directory")

    # Check if cli_directory is in .gitignore
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        with open(gitignore_path) as f:
            gitignore_content = f.read()

        if cli_directory not in gitignore_content:
            print_status(f"Adding {cli_directory} to .gitignore...")
            with open(gitignore_path, "a") as f:
                f.write(f"\n{cli_directory}\n")
            print_success(f"Added {cli_directory} to .gitignore")
    else:
        print_status("Creating .gitignore file...")
        with open(gitignore_path, "w") as f:
            f.write(f"{cli_directory}\n")
        print_success(f"Created .gitignore with {cli_directory}")


def download_and_extract_ui():
    """Download the latest frontend UI and extract it to .railtracks/ui"""
    ui_url = latest_ui_url
    ui_dir = Path(f"{cli_directory}/ui")

    print_status("Downloading latest frontend UI...")

    try:
        # Create temporary file for download
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
            temp_zip_path = temp_file.name

        # Download the zip file
        print_status(f"Downloading from: {ui_url}")
        urllib.request.urlretrieve(ui_url, temp_zip_path)

        # Create ui directory if it doesn't exist
        ui_dir.mkdir(parents=True, exist_ok=True)

        # Extract the zip file
        print_status("Extracting UI files...")
        with zipfile.ZipFile(temp_zip_path, "r") as zip_ref:
            zip_ref.extractall(ui_dir)

        # Clean up temporary file
        os.unlink(temp_zip_path)

        print_success("Frontend UI downloaded and extracted successfully")
        print_status(f"UI files available in: {ui_dir}")

    except urllib.error.URLError as e:
        print_error(f"Failed to download UI: {e}")
        print_error("Please check your internet connection and try again")
        sys.exit(1)
    except zipfile.BadZipFile as e:
        print_error(f"Failed to extract UI zip file: {e}")
        print_error("The downloaded file may be corrupted")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error during UI download/extraction: {e}")
        sys.exit(1)


def init_railtracks():
    """Initialize the railtracks environment"""
    print_status("Initializing railtracks environment...")

    # Setup directories
    create_railtracks_dir()

    # Download and extract UI
    download_and_extract_ui()

    print_success("railtracks initialization completed!")
    print_status("You can now run 'railtracks viz' to start the server")


def broadcast_sse_event(event_data):
    """Broadcast an event to all connected SSE clients"""
    if not sse_clients:
        return

    message = f"data: {json.dumps(event_data)}\n\n"
    message_bytes = message.encode()

    with sse_clients_lock:
        disconnected_clients = set()
        for client in sse_clients:
            try:
                client.wfile.write(message_bytes)
                client.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                disconnected_clients.add(client)

        # Clean up disconnected clients
        for client in disconnected_clients:
            sse_clients.discard(client)


class FileChangeHandler(FileSystemEventHandler):
    """Handle file system events in the .railtracks directory"""

    def __init__(self):
        self.last_modified = {}

    def on_modified(self, event):
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if file_path.suffix.lower() == ".json":
            current_time = time.time()
            last_time = self.last_modified.get(str(file_path), 0)

            # Debounce rapid file changes
            if current_time - last_time > DEBOUNCE_INTERVAL:
                self.last_modified[str(file_path)] = current_time
                print_status(f"JSON file modified: {file_path.name}")

                # Broadcast SSE event to all connected clients
                broadcast_sse_event(
                    {
                        "type": "file_changed",
                        "file": file_path.name,
                        "timestamp": current_time,
                        "size": file_path.stat().st_size,
                    }
                )


class RailtracksHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the railtracks server"""

    def __init__(self, *args, **kwargs):
        self.ui_dir = Path(f"{cli_directory}/ui")
        self.railtracks_dir = Path(cli_directory)
        super().__init__(*args, **kwargs)

    def do_GET(self):  # noqa: N802
        """Handle GET requests"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # API endpoints
        if path == "/api/files":
            self.handle_api_files()
        elif path.startswith("/api/json/"):
            self.handle_api_json(path)
        elif path == "/api/sse":  # SSE endpoint
            self.handle_sse()
        else:
            # Serve static files from build directory
            self.serve_static_file(path)

    def do_OPTIONS(self):  # noqa: N802
        """Handle OPTIONS requests for CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):  # noqa: N802
        """Handle POST requests"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/api/refresh":
            self.handle_refresh()
        else:
            self.send_error(404, "Not Found")

    def handle_api_files(self):
        """Handle /api/files endpoint - list JSON files in .railtracks directory"""
        try:
            json_files = []
            if self.railtracks_dir.exists():
                for file_path in self.railtracks_dir.glob("*.json"):
                    json_files.append(
                        {
                            "name": file_path.name,
                            "size": file_path.stat().st_size,
                            "modified": file_path.stat().st_mtime,
                        }
                    )

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(json_files).encode())

        except Exception as e:
            print_error(f"Error handling /api/files: {e}")
            self.send_error(500, "Internal Server Error")

    def handle_api_json(self, path):
        """Handle /api/json/{filename} endpoint - load specific JSON file"""
        try:
            # Extract filename from path
            filename = path.replace("/api/json/", "")
            if not filename.endswith(".json"):
                filename += ".json"

            file_path = self.railtracks_dir / filename

            if not file_path.exists():
                self.send_error(404, f"File {filename} not found")
                return

            # Read and parse JSON file
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                # Validate JSON
                json.loads(content)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content.encode())

        except json.JSONDecodeError as e:
            print_error(f"Invalid JSON in {filename}: {e}")
            self.send_error(400, f"Invalid JSON: {e}")
        except Exception as e:
            print_error(f"Error handling /api/json/{filename}: {e}")
            self.send_error(500, "Internal Server Error")

    def handle_sse(self):
        """Handle /api/sse endpoint - Server-Sent Events for real-time file notifications"""
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Cache-Control")
            self.end_headers()

            # Add this client to the SSE clients set
            with sse_clients_lock:
                sse_clients.add(self)

            try:
                # Keep connection alive and send heartbeats
                # For single-user local tool, use very short intervals
                while True:
                    # Send heartbeat every 1 second
                    heartbeat_data = json.dumps(
                        {"type": "heartbeat", "timestamp": time.time()}
                    )
                    self.wfile.write(f"data: {heartbeat_data}\n\n".encode())
                    self.wfile.flush()

                    # Sleep in very tiny chunks for immediate shutdown response
                    for _ in range(20):  # 1 second total, checking every 0.05 seconds
                        time.sleep(0.05)
                        # Check if server is shutting down - multiple ways
                        try:
                            # Check if the connection is still valid
                            if not self.wfile or self.wfile.closed:
                                return
                            # Check if server is shutting down
                            if (
                                hasattr(self.server, "_shutdown_request")
                                and self.server._shutdown_request
                            ):
                                return
                            # Check global shutdown flag
                            if global_shutdown_request:
                                return
                        except:  # noqa: E722
                            return

            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                # Remove client when connection closes
                with sse_clients_lock:
                    sse_clients.discard(self)

        except Exception as e:
            print_error(f"Error in SSE handler: {e}")
            with sse_clients_lock:
                sse_clients.discard(self)

    def handle_refresh(self):
        """Handle /api/refresh endpoint - trigger frontend refresh"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "refresh_triggered"}).encode())
        print_status("Frontend refresh triggered")

    def serve_static_file(self, path):
        """Serve static files from .railtracks/ui directory"""
        try:
            # Default to index.html for root path
            if path == "/":
                file_path = self.ui_dir / "index.html"
            else:
                file_path = self.ui_dir / path.lstrip("/")

            if not file_path.exists():
                # For SPA routing, fallback to index.html
                file_path = self.ui_dir / "index.html"

            if not file_path.exists():
                self.send_error(404, "File not found")
                return

            # Determine content type
            content_type, _ = mimetypes.guess_type(str(file_path))
            if content_type is None:
                content_type = "application/octet-stream"

            # Read and serve file
            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(content)

        except Exception as e:
            print_error(f"Error serving static file {path}: {e}")
            self.send_error(500, "Internal Server Error")

    def log_message(self, format, *args):
        """Override to use our colored logging"""
        print_status(f"{self.address_string()} - {format % args}")


class FastShutdownHTTPServer(HTTPServer):
    """HTTP server that can be shut down more quickly"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shutdown_request = False

    def shutdown(self):
        """Override shutdown to be more immediate"""
        self._shutdown_request = True
        super().shutdown()


class RailtracksServer:
    """Main server class"""

    def __init__(self, port=DEFAULT_PORT, open_browser=True):
        self.port = port
        self.server = None
        self.observer = None
        self.running = False
        self.open_browser = open_browser
        self._shutdown_request = False

    def open_web_browser(self):
        """Open the default web browser to the railtracks server"""
        try:
            url = f"http://localhost:{self.port}"
            print_status(f"🌐 Opening browser to: {url}")

            # Open browser in a separate thread to avoid blocking
            def open_browser_thread():
                try:
                    # Small delay to ensure server is ready
                    time.sleep(0.5)
                    webbrowser.open(url)
                    print_success("Browser opened successfully")
                except Exception as e:
                    print_warning(f"Could not open browser automatically: {e}")
                    print_status(f"Please open your browser and navigate to: {url}")

            browser_thread = threading.Thread(target=open_browser_thread)
            browser_thread.daemon = True
            browser_thread.start()

        except Exception as e:
            print_warning(f"Could not open browser: {e}")
            print_status(
                f"Please open your browser and navigate to: http://localhost:{self.port}"
            )

    def start_file_watcher(self):
        """Start watching the .railtracks directory"""
        railtracks_dir = Path(cli_directory)
        if not railtracks_dir.exists():
            railtracks_dir.mkdir(exist_ok=True)

        event_handler = FileChangeHandler()
        self.observer = Observer()
        self.observer.schedule(event_handler, str(railtracks_dir), recursive=True)
        self.observer.start()

        # Make observer threads daemon so they don't block shutdown
        for thread in self.observer._threads:
            thread.daemon = True

        print_status(f"Watching for JSON file changes in: {railtracks_dir}")

    def start_http_server(self):
        """Start the HTTP server"""

        # Create a custom handler class with the ui and railtracks directories
        class Handler(RailtracksHTTPHandler):
            def __init__(self, *args, **kwargs):
                self.ui_dir = Path(f"{cli_directory}/ui")
                self.railtracks_dir = Path(cli_directory)
                super().__init__(*args, **kwargs)

        self.server = FastShutdownHTTPServer(("localhost", self.port), Handler)
        print_success(f"🚀 railtracks server running at http://localhost:{self.port}")
        print_status(f"📁 Serving files from: {cli_directory}/ui/")
        print_status(f"👀 Watching for changes in: {cli_directory}/")
        print_status("📋 API endpoints:")
        print_status("   GET  /api/files - List JSON files")
        print_status("   GET  /api/json/filename - Load JSON file")
        print_status("   GET  /api/sse - Server-Sent Events")
        print_status("   POST /api/refresh - Trigger frontend refresh")
        print_status("Press Ctrl+C to stop the server")

        # Open browser if requested
        if self.open_browser:
            self.open_web_browser()

        self.server.serve_forever()

    def start(self):
        """Start both the file watcher and HTTP server"""
        self.running = True

        # Set up signal handlers for immediate shutdown
        def signal_handler(signum, frame):
            print_status(f"Received signal {signum}, shutting down immediately...")
            # Force immediate shutdown for single-user local tool
            global global_shutdown_request
            global_shutdown_request = True
            self.running = False
            if self.server:
                self.server._shutdown_request = True
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start file watcher in a separate thread
        watcher_thread = threading.Thread(target=self.start_file_watcher)
        watcher_thread.daemon = True
        watcher_thread.start()

        # Start HTTP server in main thread
        try:
            self.start_http_server()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop the server and cleanup - aggressive shutdown for single user"""
        if not self.running:
            return

        print_status("Shutting down railtracks...")
        self.running = False
        self._shutdown_request = True
        global global_shutdown_request
        global_shutdown_request = True

        # Clear all SSE clients immediately
        with sse_clients_lock:
            sse_clients.clear()

        # Force shutdown HTTP server immediately
        if self.server:
            try:
                self.server._shutdown_request = True
                self.server.shutdown()
                print_status("HTTP server stopped")
            except Exception as e:
                print_error(f"Error shutting down HTTP server: {e}")

        # Stop file watcher immediately (no waiting)
        if self.observer:
            try:
                self.observer.stop()
                # Don't wait - just force stop
                print_status("File watcher stopped")
            except Exception as e:
                print_error(f"Error stopping file watcher: {e}")

        print_success("railtracks stopped.")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print(f"Usage: {cli_name} [command] [options]")
        print("")
        print("Commands:")
        print(
            f"  init    Initialize {cli_name} environment (setup directories, download portable UI)"
        )
        print(f"  viz     Start the {cli_name} development server")
        print("")
        print("Options for 'viz' command:")
        print("  --no-browser    Don't automatically open browser")
        print("")
        print("Examples:")
        print(f"  {cli_name} init              # Initialize development environment")
        print(
            f"  {cli_name} viz               # Start visualizer web app (opens browser)"
        )
        print(
            f"  {cli_name} viz --no-browser  # Start visualizer web app (don't open browser)"
        )
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        init_railtracks()
    elif command == "viz":
        # Check for --no-browser flag
        open_browser = "--no-browser" not in sys.argv

        # Setup directories
        create_railtracks_dir()

        # Start server
        server = RailtracksServer(open_browser=open_browser)
        server.start()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: init, viz")
        sys.exit(1)


if __name__ == "__main__":
    main()
