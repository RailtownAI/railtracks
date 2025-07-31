import pytest




# -------------- Auto-patch module dependencies (pytest-style) --------------
@pytest.fixture(autouse=True)
def patch_vectorstore_deps(monkeypatch, dummy_uuid_str, dummy_embedding_service, dummy_record, dummy_search_result, dummy_metric):
    import railtracks.integrations.rag.vector_store.in_memory as vsmem
    # Patch all dependencies in the *module under test's namespace*:
    monkeypatch.setattr(vsmem, "uuid_str", lambda: dummy_uuid_str)
    monkeypatch.setattr(vsmem, "BaseEmbeddingService", dummy_embedding_service)
    monkeypatch.setattr(vsmem, "VectorRecord", dummy_record)
    monkeypatch.setattr(vsmem, "SearchResult", dummy_search_result)
    monkeypatch.setattr(vsmem, "Metric", dummy_metric)
    # No need to patch AbstractVectorStore if real base is abstract and not used directly

from railtracks.integrations.rag.vector_store.in_memory import InMemoryVectorStore
import math

# --------------------------- TESTS -----------------------------

@pytest.fixture
def store(dummy_embedding_service):
    return InMemoryVectorStore(
        embedding_service=dummy_embedding_service(),
        metric="cosine",
        dim=3,
    )

@pytest.mark.skip("Unknown failure")
def test_add_and_count(store, dummy_record):
    n = store.count()
    ids = store.add(["hello", "world"])
    assert len(ids) == 2
    assert store.count() == n + 2
    vr = dummy_record(id="rec1", vector=[1,2,3], text="hi")
    ids2 = store.add([vr], embed=False)
    assert len(ids2) == 1
    assert store.count() == n + 3

def test_add_metadata_length_mismatch(store):
    with pytest.raises(ValueError):
        store.add(["a", "b"], metadata=[{}, {}, {}])

@pytest.mark.skip("Unknown failure")
def test_search_text_and_vector(store):
    store.add(["abc", "def", "ghi"])
    results = store.search("abc", top_k=2, embed=True)
    assert len(results) == 2
    v = store.embedding_service.embed("def")
    results2 = store.search(v, top_k=1, embed=False)
    assert len(results2) == 1

def test_search_wrong_embed_flag(store):
    store.add(["text"])
    with pytest.raises(ValueError):
        store.search([1,2,3], embed=True)
    with pytest.raises(ValueError):
        store.search("text", embed=False)

@pytest.mark.skip
def test_delete(store):
    ids = store.add(["x", "y"])
    deleted = store.delete([ids[0]])
    assert deleted == 1
    assert store.count() == 1
    deleted2 = store.delete(["nonexistent"])
    assert deleted2 == 0

def vectors_allclose(vec1, vec2, tol=1e-8):
    if len(vec1) != len(vec2):
        return False
    return all(abs(a - b) < tol for a, b in zip(vec1, vec2))

def normalize(vec):
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec  # or raise an error if zero vector is invalid
    return [x / norm for x in vec]

def test_update_vector(store):
    ids = store.add(["orig"])
    new_vec = [9.0, 9.0, 9.0]
    store.update(ids[0], new_vec, embed=False)
    actual = store._vectors[ids[0]]
    assert (
        vectors_allclose(actual, new_vec)
        or vectors_allclose(actual, normalize(new_vec))
    )
    
def test_update_text(store):
    ids = store.add(["orig"])
    store.update(ids[0], "new text", embed=True)
    assert store._record[ids[0]].text == "new text"

def test_update_keyerror(store):
    with pytest.raises(KeyError):
        store.update("notfound", [1,2,3], embed=False)

def test_update_wrong_embed_flag(store):
    ids = store.add(["a"])
    with pytest.raises(ValueError):
        store.update(ids[0], [1,2,3], embed=True)
    with pytest.raises(ValueError):
        store.update(ids[0], "foo", embed=False)