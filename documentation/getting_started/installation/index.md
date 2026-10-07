# Installation

Railtracks requires **Python 3.10+**. Install it using your preferred package manager:

SDK

```bash
pip install railtracks
```

SDK + local observability

```bash
pip install 'railtracks[visual]'
```

[uv](https://docs.astral.sh/uv/) is a fast, modern Python package manager. If you don't have it yet, install it with `pip install uv`.

SDK

```bash
uv add railtracks
```

SDK + local observability

```bash
uv add 'railtracks[visual]'
```

SDK

```bash
conda install -c conda-forge railtracks
```

SDK + local observability

```bash
pip install 'railtracks[visual]' # (1)!
```

1. From within your newly created Conda environment

[Poetry](https://python-poetry.org/) manages dependencies and virtual environments together. Run these inside your project directory.

SDK

```bash
poetry add railtracks
```

SDK + local observability

```bash
poetry add 'railtracks[visual]'
```

The `[visual]` extra installs the Railtracks CLI's obervability components, which includes the local visualization server for observing agent runs in your browser. Read more at [Observability](https://docs.railtracks.org/observability/agenthub/local_v2/index.md).

______________________________________________________________________

## Virtual Environments

A virtual environment isolates your project's dependencies from the rest of your system, it prevents version conflicts between projects and keeps your global Python installation clean. It's strongly recommended to use one.

Pick the tool that matches your setup:

`venv` is built into Python so no installation needed.

Create a virtual environment

```bash
python -m venv .venv
```

Activate (macOS / Linux)

```bash
source .venv/bin/activate
```

Activate (Windows)

```bash
.venv\Scripts\activate
```

Once activated, your terminal prompt will show `(.venv)`. Any `pip install` commands will now install into this environment only.

[uv](https://docs.astral.sh/uv/) creates and manages virtual environments automatically when you run `uv add`. To create one explicitly:

Create a virtual environment

```bash
uv venv
```

Activate (macOS / Linux)

```bash
source .venv/bin/activate
```

Activate (Windows)

```bash
.venv\Scripts\activate
```

[conda](https://docs.conda.io/) manages both packages and environments. Create a dedicated environment for your project:

Create a conda environment

```bash
conda create -n my-project python=3.12
```

Activate the environment

```bash
conda activate my-project
```

You can replace `my-project` with any name you like.

Poetry automatically creates and manages a virtual environment for each project. No extra steps needed, just run `poetry add` or `poetry install` inside your project directory.

To see where the environment lives:

```bash
poetry env info
```
