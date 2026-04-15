# Installation

Railtracks requires **Python 3.10+**. Install it using your preferred package manager:

=== "pip"

    ```bash title="SDK"
    pip install railtracks
    ```

    ```bash title="SDK + local observability"
    pip install 'railtracks[visual]'
    ```

=== "uv"

    [uv](https://docs.astral.sh/uv/) is a fast, modern Python package manager. If you don't have it yet, install it with `pip install uv`.

    ```bash title="SDK"
    uv add railtracks
    ```

    ```bash title="SDK + local observability"
    uv add 'railtracks[visual]'
    ```

=== "conda"

    ```bash title="SDK"
    conda install -c conda-forge railtracks
    ```

    ```bash title="SDK + local observability"
    pip install 'railtracks[visual]' # (1)!
    ```
    
    1. From within your newly created Conda environment

=== "poetry"

    [Poetry](https://python-poetry.org/) manages dependencies and virtual environments together. Run these inside your project directory.

    ```bash title="SDK"
    poetry add railtracks
    ```

    ```bash title="SDK + local observability"
    poetry add 'railtracks[visual]'
    ```

The `[visual]` extra installs the Railtracks CLI's obervability components, which includes the local visualization server for observing agent runs in your browser. Read more at [Observability](../../observability/agenthub/local.md).

---

## Virtual Environments

A virtual environment isolates your project's dependencies from the rest of your system, it prevents version conflicts between projects and keeps your global Python installation clean. It's strongly recommended to use one.

Pick the tool that matches your setup:

=== "venv"

    `venv` is built into Python so no installation needed.

    ```bash title="Create a virtual environment"
    python -m venv .venv
    ```

    ```bash title="Activate (macOS / Linux)"
    source .venv/bin/activate
    ```

    ```bash title="Activate (Windows)"
    .venv\Scripts\activate
    ```

    Once activated, your terminal prompt will show `(.venv)`. Any `pip install` commands will now install into this environment only.

=== "uv"

    [uv](https://docs.astral.sh/uv/) creates and manages virtual environments automatically when you run `uv add`. To create one explicitly:

    ```bash title="Create a virtual environment"
    uv venv
    ```

    ```bash title="Activate (macOS / Linux)"
    source .venv/bin/activate
    ```

    ```bash title="Activate (Windows)"
    .venv\Scripts\activate
    ```

=== "conda"

    [conda](https://docs.conda.io/) manages both packages and environments. Create a dedicated environment for your project:

    ```bash title="Create a conda environment"
    conda create -n my-project python=3.12
    ```

    ```bash title="Activate the environment"
    conda activate my-project
    ```

    You can replace `my-project` with any name you like.

=== "poetry"

    Poetry automatically creates and manages a virtual environment for each project. No extra steps needed, just run `poetry add` or `poetry install` inside your project directory.

    To see where the environment lives:

    ```bash
    poetry env info
    ```