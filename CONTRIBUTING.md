# Contributing Guide

Welcome! This guide will help you set up your development environment and contribute effectively to our project.

## Development Setup

### Prerequisites

- **Python Version**: Ensure Python 3.10+ is installed on your system.
- **Environment Manager**: You can use either `venv` or `conda` for creating a virtual environment.

### Steps to Set Up Your Development Environment

#### 1. Create and Activate a Virtual Environment

**Using `venv`**  
1. Create a virtual environment:  
   ```bash
   python -m venv .venv
   ```
2. Activate the virtual environment:  
   - On Windows:  
     ```bash
     .venv\Scripts\activate
     ```
   - On macOS/Linux:  
     ```bash
     source .venv/bin/activate
     ```

**Using `conda`**  
1. Create a Conda environment:  
   ```bash
   conda create -n myenv python=3.10
   ```
2. Activate the Conda environment:  
   ```bash
   conda activate myenv
   ```

#### 2. Install Required Packages

1. Install the package in editable mode:  
   ```bash
   pip install -e .
   ```

---

## Running Tests

To verify your changes and ensure everything works correctly, run:  
```bash
pytest tests
```

---

## How to Contribute

1. Make your changes in a new branch or fork.
2. Commit your changes with a meaningful message.
3. Open a Pull Request (PR) into the `main` branch.

We look forward to your contributions! 🎉
