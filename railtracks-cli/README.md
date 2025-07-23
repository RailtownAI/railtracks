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

## API Endpoints

The development server provides these REST endpoints:

### GET `/api/files`

Lists all JSON files in the `.railtracks` directory.

**Response:**

```json
[
  {
    "name": "example.json",
    "size": 1024,
    "modified": 1640995200.0
  }
]
```

### GET `/api/json/{filename}`

Loads and validates a specific JSON file.

**Example:** `GET /api/json/example.json`

**Response:** The JSON content of the file

### POST `/api/refresh`

Triggers a frontend refresh (useful for development).

**Response:**

```json
{
  "status": "refresh_triggered"
}
```

## File Watching

The CLI automatically watches the `.railtracks` directory for JSON file changes:

- **Real-time Detection**: Monitors file modifications with debouncing
- **JSON Validation**: Validates JSON syntax when files are accessed
- **Console Logging**: Reports file changes in the terminal

## Development Workflow

### 1. Setup Your Project

```bash
# Navigate to your project directory
cd your-railtracks-project

# Initialize railtracks environment
railtracks init
```

### 2. Generate JSON Files

Create JSON files in the `.railtracks` directory that represent your project state:

```json
// .railtracks/project-state.json
{
  "nodes": [
    {
      "id": "node-1",
      "type": "llm",
      "status": "completed",
      "data": { ... }
    }
  ],
  "connections": [
    {
      "from": "node-1",
      "to": "node-2"
    }
  ]
}
```

### 3. Visualize Your Project

```bash
# Start the development server
railtracks viz
```

Open `http://localhost:3000` in your browser to see the visualizer.

### 4. Monitor Changes

The server will automatically detect when you modify JSON files and update the interface accordingly.

## Troubleshooting

## License

See LICENSE in the root directory.
