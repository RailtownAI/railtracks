import math
from typing import Any, Dict
from types import SimpleNamespace
import pytest
from unittest.mock import MagicMock
import pickle

import railtracks.rag.vector_store.in_memory as vsmem

# -------------- Auto-patch module dependencies (pytest-style) --------------
@pytest.fixture(autouse=True)
def patch_vectorstore_deps(monkeypatch, dummy_embedding_service, dummy_record, dummy_search_result, dummy_metric):
    
    # Create a mock that returns unique strings on each call
    mock_uuid = MagicMock()
    mock_uuid.side_effect = [f"uuid{i}" for i in range(1000)]

    # Patch dependencies in the module under test's namespace
    monkeypatch.setattr(vsmem, "uuid_str", mock_uuid)
    monkeypatch.setattr(vsmem, "BaseEmbeddingService", dummy_embedding_service)
    monkeypatch.setattr(vsmem, "VectorRecord", dummy_record)
    monkeypatch.setattr(vsmem, "SearchEntry", dummy_search_result)
    monkeypatch.setattr(vsmem, "Metric", dummy_metric)

from railtracks.rag.vector_store.in_memory import InMemoryVectorStore

# --------------------------- helpers -----------------------------

def vectors_allclose(vec1, vec2, tol=1e-8):
    if len(vec1) != len(vec2):
        return False
    return all(abs(a - b) < tol for a, b in zip(vec1, vec2))

def normalize(vec):
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]

# --------------------------- TESTS -----------------------------

@pytest.fixture
def store_cos(dummy_embedding_service):
    # cosine metric with normalization defaulting to True in real code; but patched Metric may differ
    return InMemoryVectorStore(
        embedding_service=dummy_embedding_service(),
        metric="cosine",
        dim=3,
        normalize=True,  # explicit to avoid test-dummy metric equality quirks
    )

@pytest.fixture
def store_l2(dummy_embedding_service):
    # l2 metric: default normalization should be False
    return InMemoryVectorStore(
        embedding_service=dummy_embedding_service(),
        metric="l2",
        dim=3,
    )

def test_persist_and_load_roundtrip(tmp_path, store_cos, dummy_record):
    # Add a couple of known records
    ids = store_cos.add([
        dummy_record(id="r1", vector=[1.0, 0.0, 0.0], text="one"),
        dummy_record(id="r2", vector=[0.0, 1.0, 0.0], text="two"),
    ], embed=False)

    # Persist to a directory (implicit filename)
    out_dir = tmp_path / "vs_dir"
    out_dir.mkdir()
    store_cos.persist(out_dir)
    pkl_path = out_dir / "in_memory_store.pkl"
    assert pkl_path.exists()

    # Load back
    loaded = InMemoryVectorStore.load(pkl_path)
    # EXPECTED: load() should return a store instance (currently missing return)
    assert isinstance(loaded, InMemoryVectorStore)
    assert loaded.count() == store_cos.count()
    assert loaded._dim == store_cos._dim
    assert loaded.metric.value == store_cos.metric.value
    assert loaded._normalize == store_cos._normalize
    # embedding_service is not persisted (by design)
    assert loaded.embedding_service is None

    # Vectors and records should round-trip
    assert set(loaded._vectors.keys()) == set(store_cos._vectors.keys())
    for k, v in store_cos._vectors.items():
        assert vectors_allclose(loaded._vectors[k], v)

    for k, rec in store_cos._record.items():
        loaded_rec = loaded._record[k]
        assert loaded_rec.id == rec.id
        assert vectors_allclose(loaded_rec.vector, rec.vector)
        assert loaded_rec.text == rec.text

def test_persist_to_explicit_file_path(tmp_path, store_l2, dummy_record):
    # Explicit .pkl path
    file_path = tmp_path / "custom_name.pkl"
    store_l2.add([dummy_record(id="x", vector=[1, 2, 3], text="x")], embed=False)
    store_l2.persist(file_path)
    assert file_path.exists() and file_path.is_file()

def test_add_sets_record_id_equal_to_returned_id(store_cos):
    # For text inputs, the record.id should match the returned id
    ids = store_cos.add(["foo"])
    rid = ids[0]
    assert rid in store_cos._record
    # EXPECTED: record.id should equal the stored key id (currently a bug in add)
    assert store_cos._record[rid].id == rid

def test_add_attaches_metadata_to_records(store_cos):
    # Metadata length checks are present; also ensure metadata is stored on records
    md = [{"tag": "t1"}, {"x": 1}]
    ids = store_cos.add(["a", "b"], metadata=md)
    assert len(ids) == 2
    # EXPECTED: metadata should be saved on each record (currently ignored in add)
    assert store_cos._record[ids[0]].metadata == md[0]
    assert store_cos._record[ids[1]].metadata == md[1]

def test_dimension_validation_on_add_mismatch(store_cos, dummy_record):
    # Store is initialized with dim=3
    with pytest.raises(ValueError):
        store_cos.add([dummy_record(id="bad", vector=[1, 2, 3, 4], text="bad")], embed=False)

def test_auto_dim_detection_and_mismatch(dummy_embedding_service, dummy_record):
    # Start with dim=None and detect from first add
    s = InMemoryVectorStore(
        embedding_service=dummy_embedding_service(),
        metric="cosine",
        dim=None,
    )
    s.add([dummy_record(id="a", vector=[1, 2], text="a")], embed=False)
    assert s._dim == 2
    with pytest.raises(ValueError):
        s.add([dummy_record(id="b", vector=[1, 2, 3], text="b")], embed=False)

def test_normalization_behavior_cosine_default(dummy_embedding_service, dummy_record):
    s = InMemoryVectorStore(
        embedding_service=dummy_embedding_service(),
        metric="cosine",  # default normalize=True
        dim=3,
    )
    s.add([dummy_record(id="n1", vector=[3.0, 4.0, 0.0], text="n1")], embed=False)
    stored = s._vectors["n1"]
    assert vectors_allclose(stored, normalize([3.0, 4.0, 0.0]))

def test_normalization_behavior_override_false(dummy_embedding_service, dummy_record):
    s = InMemoryVectorStore(
        embedding_service=dummy_embedding_service(),
        metric="cosine",
        dim=3,
        normalize=False,  # explicitly disable normalization
    )
    s.add([dummy_record(id="n2", vector=[3.0, 4.0, 0.0], text="n2")], embed=False)
    stored = s._vectors["n2"]
    assert vectors_allclose(stored, [3.0, 4.0, 0.0])

def test_normalization_behavior_l2_default(dummy_embedding_service, dummy_record):
    s = InMemoryVectorStore(
        embedding_service=dummy_embedding_service(),
        metric="l2",  # default normalize=False
        dim=3,
    )
    s.add([dummy_record(id="n3", vector=[3.0, 4.0, 0.0], text="n3")], embed=False)
    stored = s._vectors["n3"]
    assert vectors_allclose(stored, [3.0, 4.0, 0.0])

def test_search_ordering_and_topk(dummy_embedding_service, dummy_record):
    # Use L2 without normalization for predictable ordering
    s = InMemoryVectorStore(
        embedding_service=dummy_embedding_service(),
        metric="l2",
        dim=3,
        normalize=False,
    )
    s.add([
        dummy_record(id="p", vector=[0.0, 0.0, 0.0], text="p"),
        dummy_record(id="q", vector=[1.0, 0.0, 0.0], text="q"),
        dummy_record(id="r", vector=[0.0, 1.0, 0.0], text="r"),
    ], embed=False)

    # Query near "q" with vector
    results = s.search([0.9, 0.0, 0.0], top_k=3, embed=False)
    entries = list(results)
    ids_by_order = [e.record.id for e in entries]
    assert ids_by_order[0] == "q"  # closest
    assert set(ids_by_order) == {"p", "q", "r"}  # all included with top_k=3

def test_topk_greater_than_count_returns_all(store_l2, dummy_record):
    store_l2.add([dummy_record(id="a", vector=[1, 0, 0], text="a")], embed=False)
    res = store_l2.search([0, 0, 0], top_k=5, embed=False)
    assert len(list(res)) == 1  # only one item in store

def test_search_without_embedding_service_raises(dummy_record):
    # No embedding service set
    s = InMemoryVectorStore(embedding_service=None, metric="cosine", dim=3)
    s.add([dummy_record(id="v", vector=[0, 0, 0], text="v")], embed=False)
    with pytest.raises(RuntimeError):
        s.search("text query", embed=True)

def test_update_vector_changes_vector_and_preserves_id(store_cos):
    ids = store_cos.add(["orig"])
    rid = ids[0]
    original_text = store_cos._record[rid].text
    new_vec = [9.0, 9.0, 9.0]
    store_cos.update(rid, new_vec, embed=False)

    # Vector updated (normalized if cosine normalization is enabled)
    actual_vec = store_cos._vectors[rid]
    assert vectors_allclose(actual_vec, new_vec) or vectors_allclose(actual_vec, normalize(new_vec))
    # id preserved
    assert store_cos._record[rid].id == rid
    # EXPECTED: text should generally remain unchanged when only vector is updated
    assert store_cos._record[rid].text == original_text

def test_update_adds_metadata_fields(store_cos):
    ids = store_cos.add(["foo"])
    rid = ids[0]
    store_cos.update(rid, "foo+", embed=True, label="updated", version=2)
    rec = store_cos._record[rid]
    # Text updated
    assert rec.text == "foo+"
    # At minimum, new metadata fields should appear on the record
    assert rec.metadata.get("label") == "updated"
    assert rec.metadata.get("version") == 2

def test_delete_multiple_partial(store_cos):
    ids = store_cos.add(["a", "b", "c"])
    n_deleted = store_cos.delete([ids[0], "nonexistent"])
    assert n_deleted == 1
    assert store_cos.count() == 2

def test_search_on_empty_returns_empty(dummy_embedding_service):
    s = InMemoryVectorStore(
        embedding_service=dummy_embedding_service(),
        metric="cosine",
        dim=3,
    )
    res = s.search([0, 0, 0], top_k=5, embed=False)
    assert len(list(res)) == 0

def test_uuid_called_once_per_text_add(monkeypatch, store_cos):
    # The implementation should generate a single id per item added.
    # Note: Current implementation appears to generate two UUIDs per text item in add().
    import railtracks.rag.vector_store.in_memory as vsmem
    vsmem.uuid_str.reset_mock()
    items = ["x", "y", "z"]
    store_cos.add(items)
    # EXPECTED: exactly len(items) uuid_str calls (currently will be double)
    assert vsmem.uuid_str.call_count == len(items)
    

def test_load_reconstructs_records_with_patched_VectorRecord(tmp_path, store_cos, dummy_record):
    # Persist with DummyRecord in store, then load and ensure records are reconstructed
    ids = store_cos.add(
        [
            dummy_record(id="r1", vector=[1.0, 0.0, 0.0], text="one"),
            dummy_record(id="r2", vector=[0.0, 1.0, 0.0], text="two"),
        ],
        embed=False,
    )
    file_path = tmp_path / "store.pkl"
    store_cos.persist(file_path)

    loaded = InMemoryVectorStore.load(file_path)
    assert isinstance(loaded, InMemoryVectorStore)

    for rid in ids:
        rec = loaded._record[rid]
        assert isinstance(rec, dummy_record)
        assert rec.id == rid
        assert rec.vector == loaded._vectors[rid]
        assert rec.text in ("one", "two")

def test_load_legacy_object_records(tmp_path):
    # Backwards-compatibility: load a pickle that contains non-dict record objects.
    class OldRecord:
        def __init__(self, id, vector, text, metadata=None):
            self.id = id
            self.vector = vector
            self.text = text
            self.metadata = metadata or {}

    vectors = {"old1": [1.0, 2.0, 3.0]}
    legacy_payload = {
        "metric": "cosine",
        "dim": 3,
        "normalize": True,
        "vectors": vectors,
        # Use a picklable object type
        "record": {
            "old1": SimpleNamespace(
                id="old1",
                vector=[1.0, 2.0, 3.0],
                text="legacy",
                metadata={"z": 9},
            )
        },
    }

    p = tmp_path / "legacy.pkl"
    with open(p, "wb") as f:
        pickle.dump(legacy_payload, f)

    loaded = InMemoryVectorStore.load(p)
    assert isinstance(loaded, InMemoryVectorStore)
    assert loaded._vectors["old1"] == [1.0, 2.0, 3.0]

    # Fallback path: loader should preserve non-dict objects as-is
    rec = loaded._record["old1"]
    from types import SimpleNamespace as SN
    assert isinstance(rec, SN)
    assert rec.id == "old1"
    assert rec.vector == [1.0, 2.0, 3.0]
    assert rec.text == "legacy"
    assert rec.metadata == {"z": 9}

def test_persist_metric_is_string_in_pickle(tmp_path, store_l2, dummy_record):
    store_l2.add([dummy_record(id="m1", vector=[1, 2, 3], text="t")], embed=False)
    file_path = tmp_path / "store.pkl"
    store_l2.persist(file_path)

    with open(file_path, "rb") as f:
        data: Dict[str, Any] = pickle.load(f)
    # Metric should be persisted in a value-safe form (typically a string)
    assert isinstance(data["metric"], str)
    assert data["metric"].lower() in {"l2", "cosine", "dot"}

def test_persist_has_no_embedding_service_in_pickle(tmp_path, store_cos, dummy_record):
    store_cos.add([dummy_record(id="p1", vector=[1.0, 0.0, 0.0], text="x")], embed=False)
    file_path = tmp_path / "store.pkl"
    store_cos.persist(file_path)

    with open(file_path, "rb") as f:
        data: Dict[str, Any] = pickle.load(f)
    # Ensure we don't leak services into persisted payload
    assert "embedding_service" not in data

def test_add_vectorrecord_merges_metadata(store_cos, dummy_record):
    base = dummy_record(id="vr1", vector=[1.0, 0.0, 0.0], text="t", metadata={"a": 1, "b": 2})
    ids = store_cos.add([base], embed=False, metadata=[{"b": 3, "c": 4}])
    rid = ids[0]
    rec = store_cos._record[rid]
    # Merge semantics: provided metadata overrides conflicts, preserves existing keys
    assert rec.metadata == {"a": 1, "b": 3, "c": 4}

def test_update_merges_metadata_preserving_existing(store_cos, dummy_record):
    # Seed a record with existing metadata
    ids = store_cos.add(
        [dummy_record(id="u1", vector=[1.0, 0.0, 0.0], text="orig", metadata={"a": 1, "b": 2})],
        embed=False,
    )
    rid = ids[0]
    # Update with new text (embed=True path) and merge metadata
    store_cos.update(rid, "new text", embed=True, b="x", c=3)
    rec = store_cos._record[rid]
    assert rec.text == "new text"
    # Existing preserved, updated overridden, new added
    assert rec.metadata == {"a": 1, "b": "x", "c": 3}

def test_record_vector_matches_stored_after_add(store_cos):
    ids = store_cos.add(["normalize-me"])
    rid = ids[0]
    # Record vector should mirror stored vector exactly (including normalization)
    assert store_cos._record[rid].vector == store_cos._vectors[rid]

def test_record_vector_matches_stored_after_update(store_cos):
    ids = store_cos.add(["orig"])
    rid = ids[0]
    store_cos.update(rid, [3.0, 4.0, 0.0], embed=False)
    assert store_cos._record[rid].vector == store_cos._vectors[rid]

def test_search_topk_zero_returns_empty(store_l2, dummy_record):
    store_l2.add([dummy_record(id="a1", vector=[0, 0, 0], text="a")], embed=False)
    res = store_l2.search([0, 0, 0], top_k=0, embed=False)
    assert list(res) == []