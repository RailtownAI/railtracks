# Railtracks CLI

[![PyPI version](https://img.shields.io/pypi/v/railtracks-cli)](https://github.com/RailtownAI/railtracks/releases)
[![Python Versions](https://img.shields.io/pypi/pyversions/railtracks-cli?logo=python&)](https://pypi.org/project/railtracks/)
[![License](https://img.shields.io/pypi/l/railtracks-cli)](https://opensource.org/licenses/MIT)
[![PyPI - Downloads](https://img.shields.io/pepy/dt/railtracks-cli)](https://pypistats.org/packages/railtracks-cli)
[![Docs](https://img.shields.io/badge/docs-latest-00BFFF.svg?logo=)](https://railtownai.github.io/railtracks/)
[![GitHub stars](https://img.shields.io/github/stars/RailtownAI/railtracks.svg?style=social&label=Star)](https://github.com/RailtownAI/railtracks)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/h5ZcahDc)

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
