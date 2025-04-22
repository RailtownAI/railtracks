from setuptools import setup, find_packages

setup(
    name="lorag",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "openai>=1.0.0",
        "numpy>=1.20.0",
        "tiktoken>=0.5.0",
        "flask>=2.0.0",
        "datasets>=2.0.0",
        "tqdm>=4.0.0"
    ],
)