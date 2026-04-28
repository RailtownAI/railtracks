import pytest

from railtracks.retrieval.loaders.text_loader import TextLoader
from railtracks.retrieval.models import DocumentType


class TestTextLoaderSingleFile:
    """Tests for TextLoader loading a single file."""

    async def test_txt_file_content(self, txt_file):
        """Content of a .txt file is preserved exactly."""
        docs = await TextLoader(str(txt_file)).aload()
        assert len(docs) == 1
        assert docs[0].content == "Hello, world!"

    async def test_txt_file_type(self, txt_file):
        """Document type is TEXT for .txt files."""
        docs = await TextLoader(str(txt_file)).aload()
        assert docs[0].type == DocumentType.TEXT

    async def test_txt_file_source(self, txt_file):
        """Document source is the absolute file path."""
        docs = await TextLoader(str(txt_file)).aload()
        assert docs[0].source == str(txt_file)

    async def test_txt_file_metadata_keys(self, txt_file):
        """Metadata contains file_type and encoding keys."""
        docs = await TextLoader(str(txt_file)).aload()
        assert docs[0].metadata["file_type"] == ".txt"
        assert docs[0].metadata["encoding"] == "utf-8-sig"

    async def test_md_file_type(self, md_file):
        """Document type is MARKDOWN for .md files."""
        docs = await TextLoader(str(md_file)).aload()
        assert docs[0].type == DocumentType.MARKDOWN

    async def test_md_file_metadata_file_type(self, md_file):
        """Metadata file_type reflects the .md extension."""
        docs = await TextLoader(str(md_file)).aload()
        assert docs[0].metadata["file_type"] == ".md"

    async def test_custom_encoding_stored_in_metadata(self, txt_file):
        """The encoding passed at construction is reflected in metadata."""
        docs = await TextLoader(str(txt_file), encoding="utf-8").aload()
        assert docs[0].metadata["encoding"] == "utf-8"

    def test_load_synchronous_wrapper(self, txt_file):
        """load() returns the same documents as aload() (sync path)."""
        loader = TextLoader(str(txt_file))
        docs = loader.load()
        assert len(docs) == 1
        assert docs[0].content == "Hello, world!"


class TestTextLoaderDirectory:
    """Tests for TextLoader loading a directory of files."""

    async def test_directory_yields_all_supported_files(self, text_dir):
        """All .txt and .md files in a directory are returned."""
        docs = await TextLoader(str(text_dir)).aload()
        assert len(docs) == 3

    async def test_directory_preserves_sorted_order(self, text_dir):
        """Documents from a directory are yielded in sorted path order."""
        docs = await TextLoader(str(text_dir)).aload()
        contents = [d.content for d in docs]
        assert contents == ["alpha", "# beta", "gamma"]

    async def test_empty_directory_returns_empty_list(self, tmp_path):
        """An empty directory yields no documents."""
        docs = await TextLoader(str(tmp_path)).aload()
        assert docs == []

    async def test_directory_ignores_unsupported_extensions(self, tmp_path):
        """Files with unsupported extensions in a directory are ignored."""
        (tmp_path / "keep.txt").write_text("keep", encoding="utf-8")
        (tmp_path / "skip.csv").write_text("skip", encoding="utf-8")
        docs = await TextLoader(str(tmp_path)).aload()
        assert len(docs) == 1
        assert docs[0].content == "keep"


class TestTextLoaderErrors:
    """Tests for error conditions in TextLoader."""

    async def test_missing_file_raises_file_not_found(self, tmp_path):
        """A path to a nonexistent file raises FileNotFoundError."""
        loader = TextLoader(str(tmp_path / "ghost.txt"))
        with pytest.raises(FileNotFoundError):
            await loader.aload()

    async def test_unsupported_extension_raises_value_error(self, tmp_path):
        """A file with an unsupported extension raises ValueError."""
        f = tmp_path / "data.csv"
        f.write_text("a,b", encoding="utf-8")
        loader = TextLoader(str(f))
        with pytest.raises(ValueError, match="Unsupported file extension"):
            await loader.aload()
