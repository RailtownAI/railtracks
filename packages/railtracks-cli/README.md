# Railtracks CLI

A simple CLI to help developers visualize and debug their agents.

## What is Railtracks CLI?

Railtracks CLI is a development tool that provides:

- **Local Development Server**: A web-based visualizer for your railtracks projects
- **File Watching**: Automatic detection of JSON file changes in your project
- **JSON API**: RESTful endpoints to interact with your project data
- **Modern UI**: A downloadable frontend interface for project visualization

## Quick Start

### 1. Installation

```bash
pip install railtracks-cli
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

This starts the development server at `http://localhost:3030` with:

- File watching for JSON changes
- API endpoints for data access
- Portable Web-based visualizer interface that can be opened in any web environment (web, mobile, vs extension, chrome extension, etc)

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
