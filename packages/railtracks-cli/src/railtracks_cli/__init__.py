#!/usr/bin/env python3

"""
railtracks - A Python development server with JSON API
Usage: railtracks [command]

Commands:
  init    Initialize railtracks environment (setup directories, download UI)
  viz     Start the railtracks development server
  migrate Verify and migrate the structure of .railtracks/ directory

- Checks to see if there is a .railtracks directory
- If not, it creates one (and adds it to the .gitignore)
- If there is a build directory, it runs the build command
- If there is a .railtracks directory, it starts the server

For testing purposes, you can add `alias railtracks="python railtracks.py"` to your .bashrc or .zshrc
"""

import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
import zipfile
from pathlib import Path
from urllib.parse import unquote

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

__version__ = "0.1.0"

# TODO: Once we are releasing to PyPi change this to the release asset instead
latest_ui_url = "https://railtownazureb2c.blob.core.windows.net/cdn/rc-viz/latest.zip"

cli_name = "railtracks"
cli_directory = ".railtracks"
DEFAULT_PORT = 3030

# FastAPI app instance
app = FastAPI()


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


def is_port_in_use(port):
    """Check if a port is already in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("localhost", port))
            return False  # Port is available
        except OSError:
            return True  # Port is in use


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


def migrate_railtracks():
    """Migrate and verify the structure of .railtracks directory"""
    print_status("Verifying .railtracks directory structure...")

    # Get the .railtracks directory path
    railtracks_dir = Path(cli_directory)

    # Verify/create .railtracks directory
    if not railtracks_dir.exists():
        print_status(f"Creating {cli_directory} directory...")
        railtracks_dir.mkdir(exist_ok=True)
        print_success(f"Created {cli_directory} directory")

    # Verify/create .railtracks/data directory
    data_dir = railtracks_dir / "data"
    if not data_dir.exists():
        print_status("Creating .railtracks/data directory...")
        data_dir.mkdir(parents=True, exist_ok=True)
        print_success("Created .railtracks/data directory")

    # Verify/create .railtracks/data/evaluations directory
    evaluations_dir = data_dir / "evaluations"
    if not evaluations_dir.exists():
        print_status("Creating .railtracks/data/evaluations directory...")
        evaluations_dir.mkdir(parents=True, exist_ok=True)
        print_success("Created .railtracks/data/evaluations directory")

    # Verify/create .railtracks/data/sessions directory
    sessions_dir = data_dir / "sessions"
    if not sessions_dir.exists():
        print_status("Creating .railtracks/data/sessions directory...")
        sessions_dir.mkdir(parents=True, exist_ok=True)
        print_success("Created .railtracks/data/sessions directory")

    # Find all JSON files in .railtracks root only (not recursive, not in subdirectories)
    json_files = list(railtracks_dir.glob("*.json"))

    if json_files:
        print_status(
            f"Found {len(json_files)} JSON file(s) in .railtracks root to migrate..."
        )
        for json_file in json_files:
            destination = sessions_dir / json_file.name
            shutil.move(str(json_file), str(destination))
            print_success(f"Migrated {json_file.name} to .railtracks/data/sessions/")
        print_success(
            f"Migration completed: {len(json_files)} file(s) moved to .railtracks/data/sessions/"
        )
    else:
        print_status("No JSON files found in .railtracks root to migrate")

    print_success("Directory structure verification and migration completed!")


# FastAPI endpoints


def get_railtracks_dir():
    """Get the .railtracks directory path"""
    return Path(cli_directory)


def get_data_dir(subdir):
    """Get a data subdirectory path (e.g., evaluations, sessions)"""
    return get_railtracks_dir() / "data" / subdir


@app.get("/api/evaluations")
async def get_evaluations():
    """Get all evaluation JSON files from .railtracks/data/evaluations/"""
    evaluations_dir = get_data_dir("evaluations")
    evaluations = []

    if evaluations_dir.exists():
        for file_path in evaluations_dir.glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = json.load(f)
                    evaluations.append(content)
            except (json.JSONDecodeError, IOError) as e:
                print_error(f"Error reading evaluation file {file_path.name}: {e}")

    return JSONResponse(content=evaluations)


@app.get("/api/sessions")
async def get_sessions():
    """Get all session JSON files from .railtracks/data/sessions/"""
    sessions_dir = get_data_dir("sessions")
    sessions = []

    if sessions_dir.exists():
        for file_path in sessions_dir.glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = json.load(f)
                    sessions.append(content)
            except (json.JSONDecodeError, IOError) as e:
                print_error(f"Error reading session file {file_path.name}: {e}")

    return JSONResponse(content=sessions)


@app.get("/api/files")
async def get_files():
    """
    DEPRECATED: This endpoint is deprecated and kept for old visualizer compatibility.
    List JSON files in .railtracks directory
    """
    railtracks_dir = get_railtracks_dir()
    json_files = []

    try:
        if railtracks_dir.exists():
            for file_path in railtracks_dir.glob("*.json"):
                json_files.append(
                    {
                        "name": file_path.name,
                        "size": file_path.stat().st_size,
                        "modified": file_path.stat().st_mtime,
                    }
                )

        response = JSONResponse(content=json_files)
        response.headers["Deprecated"] = "true"
        return response
    except Exception as e:
        print_error(f"Error handling /api/files: {e}")
        return JSONResponse(content={"error": "Internal Server Error"}, status_code=500)


@app.get("/api/json/{filename:path}")
async def get_json_file(filename: str):
    """
    DEPRECATED: This endpoint is deprecated and kept for old visualizer compatibility.
    Load specific JSON file from .railtracks directory
    """
    railtracks_dir = get_railtracks_dir()

    try:
        # URL decode the filename to handle spaces and special characters
        filename = unquote(filename)
        if not filename.endswith(".json"):
            filename += ".json"

        file_path = railtracks_dir / filename

        if not file_path.exists():
            return JSONResponse(
                content={"error": f"File {filename} not found"}, status_code=404
            )

        # Read and parse JSON file
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            # Validate JSON
            json_data = json.loads(content)

        response = JSONResponse(content=json_data)
        response.headers["Deprecated"] = "true"
        return response

    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in {filename}: {e}")
        return JSONResponse(content={"error": f"Invalid JSON: {e}"}, status_code=400)
    except Exception as e:
        print_error(f"Error handling /api/json/{filename}: {e}")
        return JSONResponse(content={"error": "Internal Server Error"}, status_code=500)


@app.post("/api/refresh")
async def refresh():
    """
    DEPRECATED: This endpoint is deprecated and kept for old visualizer compatibility.
    Trigger frontend refresh
    """
    print_status("Frontend refresh triggered")
    response = JSONResponse(content={"status": "refresh_triggered"})
    response.headers["Deprecated"] = "true"
    return response


@app.get("/{full_path:path}")
async def serve_ui_or_404(full_path: str):
    """Serve UI files with SPA routing fallback (catch-all route)"""
    # Skip API routes
    if full_path.startswith("api/"):
        return JSONResponse(content={"error": "Not Found"}, status_code=404)

    ui_dir = Path(f"{cli_directory}/ui")
    ui_file = ui_dir / full_path
    if ui_file.exists() and ui_file.is_file():
        return FileResponse(str(ui_file))
    # Fallback to index.html for SPA routing
    index_file = ui_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(content={"error": "File not found"}, status_code=404)


class RailtracksServer:
    """Main server class"""

    def __init__(self, port=DEFAULT_PORT):
        self.port = port
        self.running = False
        self.config = None

    def start(self):
        """Start the FastAPI server"""
        self.running = True

        # Print server info
        print_success(f"🚀 railtracks server running at http://localhost:{self.port}")
        print_status(f"📁 Serving files from: {cli_directory}/ui/")
        print_status("📋 API endpoints:")
        print_status("   GET  /api/evaluations - Get all evaluation JSON files")
        print_status("   GET  /api/sessions - Get all session JSON files")
        print_status("   GET  /api/files - List JSON files (deprecated)")
        print_status("   GET  /api/json/{filename} - Load JSON file (deprecated)")
        print_status("   POST /api/refresh - Trigger frontend refresh (deprecated)")
        print_status("Press Ctrl+C to stop the server")

        # Open browser after a short delay to ensure server is ready
        def open_browser():
            time.sleep(1)  # Give server a moment to fully start
            url = f"http://localhost:{self.port}"
            print_status(f"Opening browser to {url}")
            try:
                webbrowser.open(url)
            except Exception as e:
                print_warning(f"Could not open browser automatically: {e}")
                print_status(f"Please manually open: {url}")

        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()

        # Start uvicorn server
        try:
            config = uvicorn.Config(
                app,
                host="localhost",
                port=self.port,
                log_level="info",
                access_log=False,  # We handle our own logging
            )
            server = uvicorn.Server(config)
            self.config = config
            server.run()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop the server and cleanup"""
        if self.running:
            print_status("Shutting down railtracks...")
            self.running = False

            print_success("railtracks stopped.")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print(f"Usage: {cli_name} [command]")
        print("")
        print("Commands:")
        print(
            f"  init    Initialize {cli_name} environment (setup directories, download portable UI)"
        )
        print(f"  viz     Start the {cli_name} development server")
        print(f"  migrate Verify and migrate the structure of .{cli_name}/ directory")
        print("")
        print("Examples:")
        print(f"  {cli_name} init    # Initialize development environment")
        print(f"  {cli_name} viz     # Start visualizer web app")
        print(
            f"  {cli_name} migrate # Verify and migrate .{cli_name}/ directory structure"
        )
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        init_railtracks()
    elif command == "viz":
        # Check if port is already in use
        if is_port_in_use(DEFAULT_PORT):
            print_error(f"Port {DEFAULT_PORT} is already in use!")
            print_status("Please stop the existing server.")
            sys.exit(1)

        # Setup directories
        create_railtracks_dir()

        # Start server
        server = RailtracksServer()
        server.start()
    elif command == "migrate":
        migrate_railtracks()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: init, viz, migrate")
        sys.exit(1)


if __name__ == "__main__":
    main()
