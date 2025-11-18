# --8<-- [start: chroma_vector_store]
from railtracks.vector_stores.chroma import ChromaVectorStore
from railtracks.rag.embedding_service import EmbeddingService
# --8<-- [end: chroma_vector_store]

# --8<-- [start: embedding_function]
embedding_function = EmbeddingService().embed
# --8<-- [end: embedding_function]

# --8<-- [start: first_chroma_example]
# 1) Temporary/Ephemeral in RAM Chroma
temporary_store = ChromaVectorStore(
        collection_name="ephemeral_collection",
        embedding_function=embedding_function,
)

# 2) Persistent local Chroma
local_store = ChromaVectorStore(
        collection_name="persistent_collection",
        embedding_function=embedding_function,
        path="/var/lib/chroma",  # example filesystem path
)

# 3) Remote HTTP Chroma
store = ChromaVectorStore(
        collection_name="remote_collection",
        embedding_function=embedding_function,
        host="chroma.example.local",
        port=8000,
)
# --8<-- [end: first_chroma_example]

