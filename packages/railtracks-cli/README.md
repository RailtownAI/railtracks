# Railtracks CLI

A simple CLI to help developers visualize and debug their agents with real-time updates.

## What is Railtracks CLI?

Railtracks CLI is a development tool that provides:

- **Local Development Server**: A web-based visualizer for your railtracks projects
- **Real-time File Watching**: Server-Sent Events (SSE) for instant file change notifications
- **Auto-Browser Launch**: Automatically opens your browser when starting the server
- **JSON API**: RESTful endpoints to interact with your project data
- **Ultra-Fast Shutdown**: Responds to Ctrl+C in under 0.5 seconds
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
# Start server and automatically open browser
railtracks viz

# Start server without opening browser
railtracks viz --no-browser
```

This starts the development server at `http://localhost:3030` with:

- **Real-time file watching** with SSE notifications
- **Auto-browser opening** (can be disabled with `--no-browser`)
- **API endpoints** for data access
- **Ultra-fast shutdown** (Ctrl+C responds in <0.5 seconds)
- **Portable Web-based visualizer** interface that can be opened in any web environment

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

## Real-time File Watching

The CLI automatically watches the `.railtracks` directory for JSON file changes:

- **Server-Sent Events (SSE)**: Real-time notifications via `/api/sse` endpoint
- **Instant Updates**: File changes are detected and broadcast immediately
- **Debounced Detection**: Prevents duplicate notifications for rapid file changes
- **JSON Validation**: Validates JSON syntax when files are accessed
- **Console Logging**: Reports file changes in the terminal

## API Endpoints

The server provides several RESTful endpoints:

### File Management

- **GET `/api/files`** - List all JSON files with metadata (name, size, modification time)
- **GET `/api/json/{filename}`** - Load specific JSON file content with validation

### Real-time Updates

- **GET `/api/sse`** - Server-Sent Events for real-time file change notifications
- **POST `/api/refresh`** - Trigger frontend refresh manually

## Performance Features

### Ultra-Fast Shutdown

- **Before**: 5-30+ seconds to respond to Ctrl+C
- **After**: 0.1-0.5 seconds to shutdown completely
- Optimized for single-user local development
- Immediate signal handling with aggressive shutdown strategy

### Real-time Performance

- SSE heartbeat every 1 second
- Shutdown detection every 0.05 seconds
- Debounced file change detection (0.5 second interval)
- Non-blocking browser launch

## Command Line Options

```bash
# Initialize environment
railtracks init

# Start server with auto-browser opening (default)
railtracks viz

# Start server without opening browser
railtracks viz --no-browser

# Get help
railtracks --help
```

## Development Workflow

1. **Initialize** your project with `railtracks init`
2. **Start** the development server with `railtracks viz`
3. **Browser opens** automatically to `http://localhost:3030`
4. **Add JSON files** to the `.railtracks` directory
5. **See real-time updates** in the web interface
6. **Stop server** with Ctrl+C (responds instantly)

## Browser Compatibility

The web interface works in:

- **Desktop browsers**: Chrome, Firefox, Safari, Edge
- **Mobile browsers**: iOS Safari, Chrome Mobile
- **Extensions**: VS Code extensions, Chrome extensions
- **Embedded**: Can be embedded in other applications

## Troubleshooting

### Server won't start

- Check if port 3030 is available
- Ensure you have internet connection for UI download
- Verify Python 3.7+ is installed

### Browser doesn't open automatically

- Use `railtracks viz --no-browser` and open manually
- Check browser settings for popup blocking
- Navigate to `http://localhost:3030` manually

### Slow shutdown

- The new version should shutdown in under 0.5 seconds
- If still slow, try pressing Ctrl+C twice
- Check for any long-running processes in the `.railtracks` directory

## Contributing

This tool is designed for single-user local development. Features are optimized for:

- **Immediate user response** over graceful shutdown
- **Real-time updates** over polling
- **Simple setup** over complex configuration
- **Fast iteration** over production-grade reliability
