# Setup for development

## Setup steps

1. Setup your python venv in this repository: `python -m venv .venv`
1. Activate your venv: `.venv\Scripts\activate`
1. Ensure you have [flit installed](https://flit.pypa.io/en/stable/)
1. `flit install --python .venv/Scripts/python.exe`
1. `flit build`

## Running Tests

`pytest`

## Release Process

- Ensure you bump the version (semver) in `src/railtownai_rc/**init**.py`
- Commit the change and get it merged into `main`
- Create a Release through GitHub and tag it as the version that was bumped "v1.0.3"
