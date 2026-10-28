from pathlib import Path

from railtracks.paths import ensure_gitignore


def test_ensure_gitignore_writes_into_railtracks_dir(tmp_path: Path):
    home = tmp_path / ".railtracks"
    home.mkdir()

    assert ensure_gitignore(home) is True
    assert "*" in (home / ".gitignore").read_text().splitlines()


def test_ensure_gitignore_finds_railtracks_dir_from_nested_path(tmp_path: Path):
    nested = tmp_path / ".railtracks" / "data" / "events"
    nested.mkdir(parents=True)

    assert ensure_gitignore(nested) is True
    assert (tmp_path / ".railtracks" / ".gitignore").exists()
    assert not (nested / ".gitignore").exists()


def test_ensure_gitignore_keeps_existing_file(tmp_path: Path):
    home = tmp_path / ".railtracks"
    home.mkdir()
    (home / ".gitignore").write_text("custom\n")

    assert ensure_gitignore(home) is False
    assert (home / ".gitignore").read_text() == "custom\n"


def test_ensure_gitignore_skips_paths_outside_railtracks_dir(tmp_path: Path):
    events = tmp_path / "my_events"
    events.mkdir()

    assert ensure_gitignore(events) is False
    assert not list(tmp_path.rglob(".gitignore"))
