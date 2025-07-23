# Railtracks CLI

A powerful Python development server with file watching and JSON API for visualizing and debugging your railtracks projects.

## What is Railtracks CLI?

Railtracks CLI is a development tool that provides:

- **Local Development Server**: A web-based visualizer for your railtracks projects
- **File Watching**: Automatic detection of JSON file changes in your project
- **JSON API**: RESTful endpoints to interact with your project data
- **Modern UI**: A downloadable frontend interface for project visualization

## Quick Start

### 1. Installation

The railtracks CLI is included with the railtracks framework. You can run it directly:

```bash
# From the railtracks-cli directory
python railtracks.py [command]

# Or create an alias for easier access
alias railtracks="python /path/to/railtracks-cli/railtracks.py"
```

### 2. Initialize Your Project

First, initialize the railtracks environment in your project directory:

```bash
railtracks init
```

This command will:

- Create a `.railtracks` directory in your project
- Add `.railtracks` to your `.gitignore` file
- Download and extract the latest frontend UI

### 3. Start the Development Server

```bash
railtracks viz
```

This starts the development server at `http://localhost:3000` with:

- File watching for JSON changes
- API endpoints for data access
- Web-based visualizer interface

## Project Structure

After initialization, your project will have this structure:

```
your-project/
├── .railtracks/          # Railtracks working directory
│   ├── ui/              # Frontend interface files
│   └── *.json           # Your project JSON files
├── .gitignore           # Updated to exclude .railtracks
└── your-source-files/   # Your actual project files
```

## File Watching

The CLI automatically watches the `.railtracks` directory for JSON file changes:

- **Real-time Detection**: Monitors file modifications with debouncing
- **JSON Validation**: Validates JSON syntax when files are accessed
- **Console Logging**: Reports file changes in the terminal

## License

See LICENSE in the root directory.
