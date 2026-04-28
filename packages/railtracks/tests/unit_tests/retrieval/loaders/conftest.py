import json

import pytest


@pytest.fixture
def txt_file(tmp_path):
    """A single .txt file with simple content."""
    f = tmp_path / "sample.txt"
    f.write_text("Hello, world!", encoding="utf-8")
    return f


@pytest.fixture
def md_file(tmp_path):
    """A single .md file with markdown content."""
    f = tmp_path / "sample.md"
    f.write_text("# Title\n\nSome content.", encoding="utf-8")
    return f


@pytest.fixture
def text_dir(tmp_path):
    """Directory with mixed .txt and .md files in known sorted order."""
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.md").write_text("# beta", encoding="utf-8")
    (tmp_path / "c.txt").write_text("gamma", encoding="utf-8")
    return tmp_path


@pytest.fixture
def json_object_file(tmp_path):
    """A .json file containing a single JSON object."""
    f = tmp_path / "data.json"
    f.write_text(
        json.dumps({"title": "Doc", "body": "Content here", "score": 42}),
        encoding="utf-8",
    )
    return f


@pytest.fixture
def json_array_file(tmp_path):
    """A .json file containing an array of two JSON objects."""
    f = tmp_path / "data.json"
    f.write_text(
        json.dumps([
            {"title": "First", "body": "Content 1"},
            {"title": "Second", "body": "Content 2"},
        ]),
        encoding="utf-8",
    )
    return f


@pytest.fixture
def json_dir(tmp_path):
    """Directory with two .json files in known sorted order."""
    (tmp_path / "a.json").write_text(json.dumps({"key": "val_a"}), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps({"key": "val_b"}), encoding="utf-8")
    return tmp_path


@pytest.fixture
def csv_file(tmp_path):
    """A simple .csv file with headers and two data rows."""
    f = tmp_path / "data.csv"
    f.write_text("name,age,city\nAlice,30,NYC\nBob,25,LA\n", encoding="utf-8")
    return f


@pytest.fixture
def csv_dir(tmp_path):
    """Directory with two .csv files in known sorted order."""
    (tmp_path / "a.csv").write_text("col1,col2\nv1,v2\n", encoding="utf-8")
    (tmp_path / "b.csv").write_text("col1,col2\nv3,v4\n", encoding="utf-8")
    return tmp_path
