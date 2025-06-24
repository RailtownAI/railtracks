# Setup for development

## Setup Steps

We use Python 3.10+ for development, so make sure you have that installed.

### 1. Setup and activate your virtual environment
##### Using `venv`
1. Create your virtual environment `python -m venv .venv`
1. Activate your venv: `.venv\Scripts\activate`

or
##### Using `conda`
1. Create your conda environment `conda create -n myenv python=3.10`
2. Activate your conda environment `conda activate myenv`


### 2. Install required packages

1. Install the editable package locally `pip install -e .`



## Running Tests
`pytest tests`

## How to Contribute

- Commit the change and put up a PR into `main`