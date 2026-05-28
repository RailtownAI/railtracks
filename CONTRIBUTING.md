# Contributing to Railtracks

Thank you for your interest in contributing to Railtracks! This guide will help you get set up for development. And *potentially* the first merge!

## Repository Structure

```
Root
├── docs/                         # Shared documentation
├── packages/railtracks/
│   ├── pyproject.toml            # Root development environment
│   ├── tests/                    # SDK tests
│   └── src/railtracks/           # Core SDK package          
└── configs like CI workflows, README, etc.
```
### External
- [Workbook and tutorial drive](https://drive.google.com/drive/u/2/folders/1qoodjEodiFjk81aM9rauT-6zeD48SAUU): Intended for long tutorials or examples in notebook format.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- [Optional] A package manager like `pip` or `poetry`. We use `uv` for development environment management, but you can also use `venv` or `conda` if you prefer.

### Installing code and dependencies

1. **Clone the repository**
   ```bash
   git clone https://github.com/RailtownAI/railtracks
   ```

2. **Install development dependencies**

   Dev dependencies are not all required, but will be useful for devs working with the project.
   ```bash
   uv sync --group dev
   ```
## Development Workflow

### Identify an issue or feature
Check the [GitHub Issues](https://github.com/RailtownAI/railtracks/issues) for existing bugs or feature requests. You can also create a new issue if you have an idea for improvement or want to report a bug, do this before starting work to avoid duplication. 

### Code Style
Ensure linting is enabled on auto or ran before commits. We check `ruff` for linting and formatting. You can run it manually with:
```bash
# Fix potential bugs and security alert and raise alert for others.
ruff check --fix
# Fix formatting issue like margins
ruff format
```

### Documentation

Run the following command on root to build and launch documentation locally. A `site/` directory will be generated with the built documentation that you can open in your browser (default: localhost:8000).

Ensure documentation is updated for any new features or changes, verify their render before a PR.

```bash
mkdocs serve
```

### Dependencies

Dependencies can be added in pyproject.toml, if developing sub-module, add under `optional-dependencies`. Examples include:
- `chat` - FastAPI chat interface
- `integrations` - The integration tooling to connect to various data sources.
- `all` - All optional dependencies

### Testing

- Write tests in the appropriate `tests/` directory of the package of interest
- Use `pytest` for running tests

## Submitting Changes

1. **Create a fork**
   ```bash
   git checkout -b feature/issue_id/your-feature-name
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

   **Note on Tests: Our repo uses end-to-end testing for ensuring appropriate external API invocations. Once you create a PR, the workflow checks that run on your PR include all the tests that do not require keys or secrets.


### Test Environment & Persistence

Railtracks uses environment variables to prevent filesystem pollution during test runs.

When running the test suite, the `RAILTRACKS_TEST_MODE` environment variable is automatically enabled via `conftest.py`. In this mode:

- Session persistence is disabled by default.
- No `.railtracks` directory will be created or modified.
- This prevents accidental deletion or pollution of user data during testing.

If a test needs to verify persistence behavior, it can opt in by enabling:

```bash
RAILTRACKS_ALLOW_PERSISTENCE=1
```

A helper fixture (`allow_persistence`) is provided in the test suite for this purpose.

These environment variables only affect test runs and do not change production behavior.


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
