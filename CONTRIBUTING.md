# Contributing to RailTracks

Thank you for your interest in contributing to RailTracks! This guide will help you get set up for development.

## Repository Structure

This is a mono-repo containing multiple packages:

```
railtracks/
├── pyproject.toml              # Root development environment
├── docs/                       # Shared documentation
├── packages/
│   ├── railtracks/            # Core SDK package
│   │   ├── src/railtracks/    # Python module (underscore)
│   │   ├── tests/             # SDK tests
│   │   └── pyproject.toml
│   └── railtracks-cli/        # CLI package  
│       ├── src/railtracks_cli/ # Python module (underscore)
│       ├── tests/             # CLI tests
│       └── pyproject.toml
└── LICENSE
```

**Important:** Package names use dashes (`railtracks-cli`) but Python modules use underscores (`railtracks_cli`).

## Development Setup

### Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) or pip

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/RailtownAI/railtracks
   cd railtracks
   ```

2. **Install development dependencies**

    Dev dependencies are not required, but will be useful for devs working with the project.
   ```bash

   # Or using pip
   pip install -r "requirements-dev.txt"
   ```
```

## Development Workflow

### Code Style

```bash
# Run linter
ruff check

# Fix auto-fixable issues
ruff check --fix

# Format code
ruff format
```

### Documentation

```bash
# Serve documentation locally
cd docs
mkdocs serve

# Build documentation
mkdocs build
```

### Package Installation for End Users

Individual packages can be installed separately:

```bash
# Core SDK
pip install railtracks
pip install "railtracks[llm]"           # With LLM extras
pip install "railtracks[integrations]"  # With integrations
pip install "railtracks[all]"           # With all extras

# CLI tool (includes core SDK)
pip install railtracks-cli
```

## Package Structure

### Core SDK (`packages/railtracks/`)

The main SDK with optional dependencies:
- `llm` - LLM integrations (OpenAI, Anthropic, etc.). This is how you use our agents. 
- `mcp` - Model Context Protocol support
- `chat` - FastAPI chat interface
- `integrations` - The integration tooling to connect to various data sources.
- `all` - All optional dependencies

### CLI (`packages/railtracks-cli/`)
Command-line interface that gives you many insights into the system. 

## Testing Guidelines

- Write tests in the appropriate `tests/` directory
- Use `pytest` for running tests

## Submitting Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write tests for new functionality
   - Update documentation if needed
   - Follow existing code style

3. **Run quality checks**
   ```bash
   # Run tests
   pytest
   
   # Check code quality
   ruff check --fix
   ruff format
   ```

4. **Commit and push**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   git push origin feature/your-feature-name
   ```

5. **Create a Pull Request**
   - Describe your changes
   - Link any related issues
   - Ensure CI passes

## Common Issues

### "Module not found" errors
- Ensure you've installed both packages: `pip install -e packages/railtracks packages/railtracks-cli`
- Remember: package names use dashes, Python modules use underscores

### Dependency resolution errors
- Install packages in order: `railtracks` first, then `railtracks-cli`
- The CLI depends on the SDK, so SDK must be available first

### Test failures
- Run tests from the repository root for full test suite
- Individual package tests can be run from within each package directory

## Questions?

If you run into issues:
1. Check this contributing guide
2. Look at existing issues on GitHub
3. Create a new issue with detailed information about your problem

Thank you for contributing to RailTracks! 🚂
