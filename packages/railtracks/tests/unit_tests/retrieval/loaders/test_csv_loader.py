import pytest
from railtracks.retrieval.loaders.csv_loader import CSVLoader
from railtracks.retrieval.models import DocumentType


class TestCSVLoaderBasic:
    """Tests for CSVLoader loading a single file with default settings."""

    async def test_yields_one_document_per_row(self, csv_file):
        """Each data row produces one Document."""
        docs = await CSVLoader(str(csv_file)).aload()
        assert len(docs) == 2

    async def test_document_type_is_csv(self, csv_file):
        """Document type is CSV."""
        docs = await CSVLoader(str(csv_file)).aload()
        assert all(d.type == DocumentType.CSV for d in docs)

    async def test_source_includes_row_index_suffix(self, csv_file):
        """Document source is the file path plus a per-row suffix."""
        docs = await CSVLoader(str(csv_file)).aload()
        assert [d.source for d in docs] == [
            f"{csv_file}#0",
            f"{csv_file}#1",
        ]

    async def test_document_ids_are_unique_per_row(self, csv_file):
        """Per-row sources produce distinct Document IDs (upsert correctness)."""
        docs = await CSVLoader(str(csv_file)).aload()
        assert len({d.id for d in docs}) == len(docs)

    async def test_default_content_includes_all_columns(self, csv_file):
        """Without content_columns, all columns appear in content."""
        docs = await CSVLoader(str(csv_file)).aload()
        assert "name: Alice" in docs[0].content
        assert "age: 30" in docs[0].content
        assert "city: NYC" in docs[0].content

    async def test_row_index_in_metadata(self, csv_file):
        """row_index is stored in metadata and matches the row position."""
        docs = await CSVLoader(str(csv_file)).aload()
        assert docs[0].metadata["row_index"] == 0
        assert docs[1].metadata["row_index"] == 1

    async def test_content_separator_joins_columns(self, csv_file):
        """content_separator is used to join column values in content."""
        docs = await CSVLoader(str(csv_file), content_separator=" | ").aload()
        assert "name: Alice | age: 30 | city: NYC" == docs[0].content

    def test_load_synchronous_wrapper(self, csv_file):
        """load() returns the same documents as aload() (sync path)."""
        loader = CSVLoader(str(csv_file))
        docs = loader.load()
        assert len(docs) == 2
        assert docs[0].metadata["row_index"] == 0


class TestCSVLoaderContentColumns:
    """Tests for the content_columns parameter."""

    async def test_content_columns_restricts_content(self, csv_file):
        """Only the specified columns appear in content."""
        docs = await CSVLoader(str(csv_file), content_columns=["name"]).aload()
        assert "name: Alice" in docs[0].content
        assert "age" not in docs[0].content
        assert "city" not in docs[0].content

    async def test_non_content_columns_go_to_metadata(self, csv_file):
        """Columns not listed in content_columns end up in metadata."""
        docs = await CSVLoader(str(csv_file), content_columns=["name"]).aload()
        assert docs[0].metadata["age"] == "30"
        assert docs[0].metadata["city"] == "NYC"

    async def test_content_columns_not_repeated_in_metadata(self, csv_file):
        """Columns in content_columns are not duplicated in metadata."""
        docs = await CSVLoader(str(csv_file), content_columns=["name"]).aload()
        assert "name" not in docs[0].metadata

    async def test_unknown_content_column_raises_value_error(self, csv_file):
        """A content_column that does not exist in the CSV raises ValueError."""
        loader = CSVLoader(str(csv_file), content_columns=["nonexistent"])
        with pytest.raises(ValueError, match="content_columns not found in CSV headers"):
            await loader.aload()


class TestCSVLoaderIdColumn:
    """Tests for the id_column parameter (per-row source identity)."""

    async def test_id_column_used_in_source(self, tmp_path):
        """When id_column is set, its value becomes the source suffix."""
        f = tmp_path / "with_id.csv"
        f.write_text("id,name\nr1,Alice\nr2,Bob\n", encoding="utf-8")
        docs = await CSVLoader(str(f), id_column="id").aload()
        assert [d.source for d in docs] == [f"{f}#r1", f"{f}#r2"]

    async def test_id_column_keeps_ids_stable_across_reorder(self, tmp_path):
        """Same id_column value → same Document.id when the same file is re-loaded
        with rows reordered. This is the upsert-correctness contract."""
        f = tmp_path / "data.csv"
        f.write_text("id,name\nr1,Alice\nr2,Bob\n", encoding="utf-8")
        docs1 = await CSVLoader(str(f), id_column="id").aload()

        f.write_text("id,name\nr2,Bob\nr1,Alice\n", encoding="utf-8")
        docs2 = await CSVLoader(str(f), id_column="id").aload()

        by_id_1 = {d.source.rsplit("#", 1)[1]: d.id for d in docs1}
        by_id_2 = {d.source.rsplit("#", 1)[1]: d.id for d in docs2}
        assert by_id_1 == by_id_2

    async def test_unknown_id_column_raises_value_error(self, csv_file):
        """An id_column not present in the CSV headers raises ValueError."""
        loader = CSVLoader(str(csv_file), id_column="nonexistent")
        with pytest.raises(ValueError, match="id_column not found in CSV headers"):
            await loader.aload()


class TestCSVLoaderIgnoreColumns:
    """Tests for the ignore_columns parameter."""

    async def test_non_ignored_non_content_column_appears_in_metadata(self, csv_file):
        """A non-content column with no ignore_columns entry IS present in metadata."""
        docs = await CSVLoader(str(csv_file), content_columns=["name"]).aload()
        assert "age" in docs[0].metadata
        assert "city" in docs[0].metadata

    async def test_ignore_columns_excluded_from_metadata(self, csv_file):
        """Ignored columns do not appear in metadata."""
        docs = await CSVLoader(
            str(csv_file),
            content_columns=["name"],
            ignore_columns=["city"],
        ).aload()
        assert "city" not in docs[0].metadata


class TestCSVLoaderDirectory:
    """Tests for CSVLoader loading a directory."""

    async def test_directory_loads_all_csv_files(self, csv_dir):
        """All .csv files in a directory are loaded."""
        docs = await CSVLoader(str(csv_dir)).aload()
        assert len(docs) == 2

    async def test_directory_sorted_order(self, csv_dir):
        """Files from a directory are processed in sorted path order."""
        docs = await CSVLoader(str(csv_dir)).aload()
        assert "v1" in docs[0].content
        assert "v3" in docs[1].content

    async def test_empty_directory_returns_empty_list(self, tmp_path):
        """An empty directory yields no documents."""
        docs = await CSVLoader(str(tmp_path)).aload()
        assert docs == []

    async def test_empty_csv_file_returns_no_documents(self, tmp_path):
        """A CSV file with headers but no data rows yields no Documents."""
        f = tmp_path / "empty.csv"
        f.write_text("col1,col2\n", encoding="utf-8")
        docs = await CSVLoader(str(f)).aload()
        assert docs == []


class TestCSVLoaderErrors:
    """Tests for error conditions in CSVLoader."""

    async def test_missing_file_raises_file_not_found(self, tmp_path):
        """A path to a nonexistent file raises FileNotFoundError."""
        loader = CSVLoader(str(tmp_path / "ghost.csv"))
        with pytest.raises(FileNotFoundError):
            await loader.aload()

    async def test_unsupported_extension_raises_value_error(self, tmp_path):
        """A file with a non-.csv extension raises ValueError."""
        f = tmp_path / "data.txt"
        f.write_text("a,b\n1,2\n", encoding="utf-8")
        loader = CSVLoader(str(f))
        with pytest.raises(ValueError, match="CSVLoader expects a .csv file"):
            await loader.aload()
