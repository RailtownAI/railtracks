# Contributing to Railtracks

Thank you for your interest in contributing to Railtracks! This guide will help you get set up for development.

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

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/RailtownAI/railtracks
   cd railtracks
   ```

2. **Install development dependencies**

    Dev dependencies are not all required, but will be useful for devs working with the project.
   ```bash
   python -m venv .venv
   source .venv/bin/activate # for mac and linux 
   pip install uv
   uv sync --group dev 
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
pip install "railtracks[integrations]"  # With integrations
pip install "railtracks[all]"           # With all extras

# CLI tool (includes core SDK)
pip install railtracks-cli
```

## Package Structure

### Core SDK (`packages/railtracks/`)

The main SDK with optional dependencies:
- `chat` - FastAPI chat interface
- `integrations` - The integration tooling to connect to various data sources.
- `all` - All optional dependencies

### CLI (`packages/railtracks-cli/`)
Command-line interface that gives you a visualizer to use with the system. 

## Testing Guidelines

- Write tests in the appropriate `tests/` directory of the package of intrest
- Use `pytest` for running tests

## Submitting Changes

1. **Create a fork**
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
   - Describe your changes using the template provided
   - Link any related issues
   - Ensure CI checks passes

   **Note on Tests: Our repo uses end-to-end testing for ensuring appropriate external API invocations. Once you create a PR, the workflow checks that run on your PR include all the tests that do not require keys or secrets. After the passing of these tests, a maintainer will run the end-to-end tests before giving your PR an approval or providing you with the relevant output of end-to-end failures.

## Common Issues

### Test failures
- Run tests from the repository root for full test suite, excluding the `end_to_end` tests with the following:
```python
pytest -s -v packages/railtracks/tests/unit_tests/ packages/railtracks/tests/integration_tests/

```
- Individual package tests can be run from within each package directory

## Questions?

If you run into issues:
1. Check this contributing guide
2. Look at existing issues on GitHub
3. Reach out the maintainers on discord
4. Create a new issue with detailed information about your problem

Thank you for contributing to Railtracks! 🚂
