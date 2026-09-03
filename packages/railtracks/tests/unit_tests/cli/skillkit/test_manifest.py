"""Tests for the install manifest: the record that makes a re-install a sync."""

import json
from pathlib import Path

import pytest
from railtracks.cli._skillkit.manifest import (
    MANIFEST_FILE,
    MANIFEST_VERSION,
    InstalledFile,
    InstallRecord,
    file_digest,
    find_legacy_installs,
    is_ours_unmodified,
    package_version,
    prune,
    read_record,
    record_for,
    stale_files,
    version_skew,
    write_record,
)


def make_record(*, version="1.0.0", files=(("SKILL.md", "abc"),)):
    return InstallRecord(
        skill="fixture-skill",
        target="claude",
        package_version=version,
        files=tuple(InstalledFile(path=p, sha256=h) for p, h in files),
    )


def install(destination: Path, contents: dict[str, str]) -> InstallRecord:
    """Write `contents` into `destination` and return a record describing them."""
    written = []
    for relative, text in contents.items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return record_for("fixture-skill", "claude", destination, written)


# --- the record format ------------------------------------------------------


class TestRecordFormat:
    def test_round_trips(self):
        record = make_record(files=(("SKILL.md", "a"), ("references/api.md", "b")))

        assert InstallRecord.from_json(record.to_json()) == record

    def test_serialisation_is_deterministic(self):
        """A re-install that changes nothing must not churn a committed manifest."""
        record = make_record()

        assert record.to_json() == make_record().to_json()

    def test_records_the_package_version_not_a_skill_version(self, tmp_path):
        """D3: version lives on the install; nothing in SKILL.md carries one."""
        record = install(tmp_path, {"SKILL.md": "x"})

        assert record.package_version == package_version()

    def test_records_a_hash_per_file(self, tmp_path):
        """Path alone cannot answer 'is this still what we wrote?'."""
        record = install(tmp_path, {"SKILL.md": "x", "references/api.md": "y"})

        assert {f.path for f in record.files} == {"SKILL.md", "references/api.md"}
        assert all(len(f.sha256) == 64 for f in record.files)

    def test_paths_are_relative_and_posix(self, tmp_path):
        """The manifest travels with the repo, so it cannot hold absolute paths."""
        record = install(tmp_path, {"scripts/nested/demo.py": "x"})

        assert record.files[0].path == "scripts/nested/demo.py"

    @pytest.mark.parametrize(
        "text",
        [
            "not json at all",
            "[]",
            json.dumps({"manifest_version": MANIFEST_VERSION}),
            json.dumps({"manifest_version": MANIFEST_VERSION + 1, "skill": "x"}),
            json.dumps({"skill": "x", "target": "claude", "files": []}),
        ],
    )
    def test_unreadable_records_degrade_to_none(self, text):
        """A corrupt or future manifest must cost a prompt, never an exception."""
        assert InstallRecord.from_json(text) is None


class TestReadWrite:
    def test_write_then_read(self, tmp_path):
        record = make_record()
        write_record(tmp_path, record)

        assert read_record(tmp_path) == record

    def test_missing_manifest_reads_as_none(self, tmp_path):
        assert read_record(tmp_path) is None

    def test_corrupt_manifest_reads_as_none(self, tmp_path):
        (tmp_path / MANIFEST_FILE).write_text("{ broken", encoding="utf-8")

        assert read_record(tmp_path) is None


# --- proving a file is ours -------------------------------------------------


class TestIsOursUnmodified:
    def test_true_for_a_recorded_untouched_file(self, tmp_path):
        record = install(tmp_path, {"SKILL.md": "x"})

        assert is_ours_unmodified(tmp_path / "SKILL.md", tmp_path, record)

    def test_false_once_edited(self, tmp_path):
        record = install(tmp_path, {"SKILL.md": "x"})
        (tmp_path / "SKILL.md").write_text("edited by hand", encoding="utf-8")

        assert not is_ours_unmodified(tmp_path / "SKILL.md", tmp_path, record)

    def test_false_for_a_file_we_never_recorded(self, tmp_path):
        record = install(tmp_path, {"SKILL.md": "x"})
        (tmp_path / "theirs.md").write_text("hand written", encoding="utf-8")

        assert not is_ours_unmodified(tmp_path / "theirs.md", tmp_path, record)

    def test_false_with_no_record_at_all(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("x", encoding="utf-8")

        assert not is_ours_unmodified(tmp_path / "SKILL.md", tmp_path, None)


# --- what a sync may remove -------------------------------------------------


class TestStaleFiles:
    def test_untouched_dropped_file_is_removable(self, tmp_path):
        record = install(tmp_path, {"SKILL.md": "x", "references/gone.md": "y"})

        removable, edited = stale_files(tmp_path, record, [tmp_path / "SKILL.md"])

        assert removable == [tmp_path / "references/gone.md"]
        assert edited == []

    def test_edited_dropped_file_is_kept(self, tmp_path):
        """Somebody put work into it; a sync is not licensed to throw that away."""
        record = install(tmp_path, {"SKILL.md": "x", "references/gone.md": "y"})
        (tmp_path / "references/gone.md").write_text("mine now", encoding="utf-8")

        removable, edited = stale_files(tmp_path, record, [tmp_path / "SKILL.md"])

        assert removable == []
        assert edited == [tmp_path / "references/gone.md"]

    def test_files_still_shipped_are_untouched(self, tmp_path):
        record = install(tmp_path, {"SKILL.md": "x", "references/api.md": "y"})

        removable, edited = stale_files(
            tmp_path, record, [tmp_path / "SKILL.md", tmp_path / "references/api.md"]
        )

        assert (removable, edited) == ([], [])

    def test_already_deleted_files_are_not_reported(self, tmp_path):
        record = install(tmp_path, {"SKILL.md": "x", "references/gone.md": "y"})
        (tmp_path / "references/gone.md").unlink()

        assert stale_files(tmp_path, record, [tmp_path / "SKILL.md"]) == ([], [])

    def test_no_previous_record_removes_nothing(self, tmp_path):
        """Never having written a manifest is not evidence that a file is ours."""
        (tmp_path / "stranger.md").write_text("x", encoding="utf-8")

        assert stale_files(tmp_path, None, []) == ([], [])


class TestPrune:
    def test_removes_files_and_the_directories_they_empty(self, tmp_path):
        install(tmp_path, {"references/nested/gone.md": "y"})

        prune(tmp_path, [tmp_path / "references/nested/gone.md"])

        assert not (tmp_path / "references").exists()
        assert tmp_path.exists()

    def test_keeps_directories_that_still_hold_something(self, tmp_path):
        install(tmp_path, {"references/gone.md": "y", "references/stays.md": "z"})

        prune(tmp_path, [tmp_path / "references/gone.md"])

        assert (tmp_path / "references/stays.md").is_file()

    def test_never_removes_the_skill_directory_itself(self, tmp_path):
        install(tmp_path, {"only.md": "y"})

        prune(tmp_path, [tmp_path / "only.md"])

        assert tmp_path.is_dir()


# --- version skew -----------------------------------------------------------


class TestVersionSkew:
    def test_reports_a_different_version(self):
        message = version_skew(make_record(version="0.0.1-ancient"))

        assert message is not None
        assert "0.0.1-ancient" in message

    def test_silent_when_versions_match(self):
        assert version_skew(make_record(version=package_version())) is None

    def test_silent_without_a_record(self):
        assert version_skew(None) is None

    def test_silent_when_the_recorded_version_is_unknown(self):
        """An install made outside a packaged environment is not skew evidence."""
        assert version_skew(make_record(version="unknown")) is None


# --- legacy detection: report only, never remove ----------------------------


class TestFindLegacyInstalls:
    def test_finds_a_copilot_marker_block(self, tmp_path):
        instructions = tmp_path / ".github" / "copilot-instructions.md"
        instructions.parent.mkdir(parents=True)
        instructions.write_text(
            "# Mine\n<!-- railtracks:fixture-skill:start -->\nbody\n"
            "<!-- railtracks:fixture-skill:end -->\n",
            encoding="utf-8",
        )

        found = find_legacy_installs("fixture-skill", tmp_path)

        assert [(f.target, f.shape, f.confirmed) for f in found] == [
            ("Copilot", "region", True)
        ]

    def test_copilot_block_for_another_skill_is_not_ours_to_report(self, tmp_path):
        instructions = tmp_path / ".github" / "copilot-instructions.md"
        instructions.parent.mkdir(parents=True)
        instructions.write_text(
            "<!-- railtracks:other-skill:start -->\n<!-- railtracks:other-skill:end -->\n",
            encoding="utf-8",
        )

        assert find_legacy_installs("fixture-skill", tmp_path) == []

    def test_finds_a_cursor_rules_file(self, tmp_path):
        rule = tmp_path / ".cursor" / "rules" / "fixture-skill.mdc"
        rule.parent.mkdir(parents=True)
        rule.write_text(
            "---\ndescription: x\nalwaysApply: false\n---\n\nbody\n", encoding="utf-8"
        )

        found = find_legacy_installs("fixture-skill", tmp_path)

        assert [(f.target, f.shape, f.confirmed) for f in found] == [
            ("Cursor", "file", True)
        ]

    def test_a_cursor_file_that_does_not_look_like_ours_is_still_reported_unconfirmed(
        self, tmp_path
    ):
        """§3.3: an `.mdc` carries nothing saying railtracks, so a name match is a
        reason to tell the user and never a reason to delete their file."""
        rule = tmp_path / ".cursor" / "rules" / "fixture-skill.mdc"
        rule.parent.mkdir(parents=True)
        rule.write_text("---\nalwaysApply: true\n---\n\nhand written\n", encoding="utf-8")

        found = find_legacy_installs("fixture-skill", tmp_path)

        assert found[0].confirmed is False
        assert "may be yours" in found[0].advice()

    def test_finds_nothing_in_a_clean_repo(self, tmp_path):
        assert find_legacy_installs("fixture-skill", tmp_path) == []

    def test_detection_never_touches_the_files_it_finds(self, tmp_path):
        rule = tmp_path / ".cursor" / "rules" / "fixture-skill.mdc"
        rule.parent.mkdir(parents=True)
        rule.write_text("---\nalwaysApply: false\n---\n", encoding="utf-8")
        before = file_digest(rule)

        find_legacy_installs("fixture-skill", tmp_path)

        assert rule.is_file() and file_digest(rule) == before
