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

## Configuration

### Port Configuration

The server runs on port 3000 by default. To change this, modify the `RailtracksServer` class in `railtracks.py`:

```python
server = RailtracksServer(port=8080)  # Change port number
```

### UI Source

The frontend UI is a portable React UI that works on any web platform (web, mobile, visual studio extension, chrome extension, etc) and is downloaded from a CDN. To use a different source, update the `latest_ui_url` variable:

```python
latest_ui_url = "https://your-cdn.com/railtracks-ui/latest.zip"
```

## Troubleshooting

### Common Issues

**1. Port Already in Use**

```
Error: [Errno 48] Address already in use
```

**Solution:** Change the port number or stop the process using port 3000.

**2. Download Failed**

```
Failed to download UI: <urlopen error [Errno 8] nodename nor servname provided, or not known>
```

**Solution:** Check your internet connection and try again.

**3. Invalid JSON**

```
Invalid JSON in filename.json: Expecting property name enclosed in double quotes
```

**Solution:** Fix the JSON syntax in your file.

**4. File Not Found**

```
404: File filename.json not found
```

**Solution:** Ensure the JSON file exists in the `.railtracks` directory.

### Debug Mode

For detailed logging, you can modify the print functions in `railtracks.py` to include more verbose output.

## Integration with Railtracks Framework

The CLI is designed to work seamlessly with the railtracks framework:

1. **State Export**: Export your railtracks project state to JSON files
2. **Real-time Monitoring**: Watch execution progress and node states
3. **Debugging**: Visualize complex node graphs and data flows
4. **Development**: Iterate quickly with live reloading

### Example Integration

```python
# In your railtracks project
from railtracks import run
import json
from pathlib import Path

# Your railtracks workflow
result = run(your_workflow)

# Export state to .railtracks directory
state_file = Path(".railtracks/execution-state.json")
with open(state_file, "w") as f:
    json.dump(result.state, f, indent=2)
```

## Contributing

To contribute to the railtracks CLI:

1. **UI Development**: The frontend UI is downloaded from a CDN. To develop locally:

   - Build your UI changes
   - Host them on a CDN
   - Update the `latest_ui_url` in the code

2. **CLI Features**: Add new commands by extending the `main()` function

3. **API Extensions**: Add new endpoints by extending the `RailtracksHTTPHandler` class

## License

This CLI tool is part of the railtracks framework and follows the same licensing terms.

## Support

For issues and questions:

- Check the troubleshooting section above
- Review the railtracks framework documentation
- Open an issue in the project repository
