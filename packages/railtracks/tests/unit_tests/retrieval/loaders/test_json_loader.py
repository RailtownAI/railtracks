import json

import pytest
from railtracks.retrieval.loaders.json_loader import JSONLoader
from railtracks.retrieval.models import DocumentType


class TestJSONLoaderSingleObject:
    """Tests for JSONLoader with a file containing a single JSON object."""

    async def test_single_object_yields_one_document(self, json_object_file):
        """A JSON object file produces exactly one Document."""
        docs = await JSONLoader(str(json_object_file)).aload()
        assert len(docs) == 1

    async def test_single_object_content_keys_star_serialises_full_object(self, json_object_file):
        """content_keys='*' (default) serialises the whole object as content."""
        docs = await JSONLoader(str(json_object_file)).aload()
        parsed = json.loads(docs[0].content)
        assert parsed["title"] == "Doc"
        assert parsed["score"] == 42

    async def test_single_object_document_type(self, json_object_file):
        """Document type is JSON."""
        docs = await JSONLoader(str(json_object_file)).aload()
        assert docs[0].type == DocumentType.JSON

    async def test_single_object_source_is_file_path(self, json_object_file):
        """Document source is the absolute file path."""
        docs = await JSONLoader(str(json_object_file)).aload()
        assert docs[0].source == str(json_object_file)

    async def test_single_object_index_zero_in_metadata(self, json_object_file):
        """The object's index (0) is stored in metadata."""
        docs = await JSONLoader(str(json_object_file)).aload()
        assert docs[0].metadata["index"] == 0


class TestJSONLoaderArray:
    """Tests for JSONLoader with a file containing an array of objects."""

    async def test_array_yields_one_document_per_element(self, json_array_file):
        """An array of N objects yields N Documents."""
        docs = await JSONLoader(str(json_array_file)).aload()
        assert len(docs) == 2

    async def test_array_indices_in_metadata(self, json_array_file):
        """Each Document's metadata carries the correct zero-based index."""
        docs = await JSONLoader(str(json_array_file)).aload()
        assert docs[0].metadata["index"] == 0
        assert docs[1].metadata["index"] == 1

    async def test_array_order_preserved(self, json_array_file):
        """Documents are yielded in the same order as the array."""
        docs = await JSONLoader(str(json_array_file), content_keys=["title"]).aload()
        assert "First" in docs[0].content
        assert "Second" in docs[1].content


class TestJSONLoaderContentKeys:
    """Tests for the content_keys parameter."""

    async def test_explicit_content_keys_build_content_string(self, json_object_file):
        """Explicit content_keys join the matching values into content."""
        docs = await JSONLoader(
            str(json_object_file), content_keys=["title", "body"]
        ).aload()
        assert "title: Doc" in docs[0].content
        assert "body: Content here" in docs[0].content

    async def test_explicit_content_keys_exclude_from_metadata(self, json_object_file):
        """Keys listed in content_keys are not repeated in metadata."""
        docs = await JSONLoader(
            str(json_object_file), content_keys=["title"]
        ).aload()
        assert "title" not in docs[0].metadata

    async def test_non_content_keys_go_to_metadata(self, json_object_file):
        """Keys not in content_keys (and not ignored) end up in metadata."""
        docs = await JSONLoader(
            str(json_object_file), content_keys=["title"]
        ).aload()
        assert docs[0].metadata["body"] == "Content here"
        assert docs[0].metadata["score"] == 42

    async def test_content_separator_joins_values(self, json_object_file):
        """content_separator is used between the values of multiple content_keys."""
        docs = await JSONLoader(
            str(json_object_file),
            content_keys=["title", "body"],
            content_separator=" | ",
        ).aload()
        assert "title: Doc | body: Content here" == docs[0].content

    async def test_missing_content_key_raises_value_error(self, json_object_file):
        """A content_key not present in the object raises ValueError."""
        loader = JSONLoader(str(json_object_file), content_keys=["nonexistent"])
        with pytest.raises(ValueError, match="not found in object"):
            await loader.aload()


class TestJSONLoaderIgnoreKeys:
    """Tests for the ignore_keys parameter."""

    async def test_ignore_keys_excluded_from_content_star(self, json_object_file):
        """Ignored keys are excluded from the serialised content when using '*'."""
        docs = await JSONLoader(
            str(json_object_file), ignore_keys=["score"]
        ).aload()
        parsed = json.loads(docs[0].content)
        assert "score" not in parsed

    async def test_ignore_keys_excluded_from_metadata(self, json_object_file):
        """Ignored keys do not appear in metadata."""
        docs = await JSONLoader(
            str(json_object_file),
            content_keys=["title"],
            ignore_keys=["score"],
        ).aload()
        assert "score" not in docs[0].metadata


class TestJSONLoaderDirectory:
    """Tests for JSONLoader loading a directory."""

    async def test_directory_loads_all_json_files(self, json_dir):
        """All .json files in a directory are loaded."""
        docs = await JSONLoader(str(json_dir)).aload()
        assert len(docs) == 2

    async def test_directory_sorted_order(self, json_dir):
        """Files from a directory are streamed in sorted order."""
        docs = await JSONLoader(str(json_dir), content_keys=["key"]).aload()
        assert "val_a" in docs[0].content
        assert "val_b" in docs[1].content

    async def test_empty_directory_returns_empty_list(self, tmp_path):
        """An empty directory yields no documents."""
        docs = await JSONLoader(str(tmp_path)).aload()
        assert docs == []


class TestJSONLoaderErrors:
    """Tests for error conditions in JSONLoader."""

    async def test_missing_file_raises_file_not_found(self, tmp_path):
        """A path to a nonexistent file raises FileNotFoundError."""
        loader = JSONLoader(str(tmp_path / "ghost.json"))
        with pytest.raises(FileNotFoundError):
            await loader.aload()

    async def test_unsupported_extension_raises_value_error(self, tmp_path):
        """A file with a non-.json extension raises ValueError."""
        f = tmp_path / "data.txt"
        f.write_text("{}", encoding="utf-8")
        loader = JSONLoader(str(f))
        with pytest.raises(ValueError, match="JSONLoader expects a .json file"):
            await loader.aload()

    async def test_array_of_scalars_raises_value_error(self, tmp_path):
        """A JSON array of non-objects (e.g. strings) raises ValueError."""
        f = tmp_path / "bad.json"
        f.write_text(json.dumps(["a", "b", "c"]), encoding="utf-8")
        loader = JSONLoader(str(f))
        with pytest.raises(ValueError, match="array of objects"):
            await loader.aload()

    async def test_scalar_json_raises_value_error(self, tmp_path):
        """A JSON file containing a bare scalar raises ValueError."""
        f = tmp_path / "bad.json"
        f.write_text("42", encoding="utf-8")
        loader = JSONLoader(str(f))
        with pytest.raises(ValueError):
            await loader.aload()
