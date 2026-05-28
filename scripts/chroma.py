# --8<-- [start: chroma_vector_store]
from railtracks.vector_stores.chroma import ChromaVectorStore
from railtracks.vector_stores.vector_store_base import Chunk
from railtracks.rag.embedding_service import EmbeddingService
# --8<-- [end: chroma_vector_store]

# --8<-- [start: embedding_function]
embedding_function = EmbeddingService().embed
# --8<-- [end: embedding_function]

# --8<-- [start: data]
articles_data = [
    {"title": "AI Advances in 2024", 
     "content": "Artificial intelligence saw major breakthroughs this year...", 
     "author": "Jane Doe", 
     "date": "2024-01-15",
     "document" : "ai news"},

    {"title": "Climate Change Report", 
     "content": "New studies show accelerating impacts of climate change...", 
     "author": "John Smith", 
     "date": "2024-02-20",
     "document" : "climate news"},

    {"title": "Space Exploration Updates", 
     "content": "Mars mission successfully lands new rover...", 
     "author": "Alice Johnson", 
     "date": "2024-03-10",
     "document" : "space news"},

    {"title": "Healthcare Innovations", 
     "content": "Revolutionary new treatment for rare diseases approved...", 
     "author": "Bob Williams", 
     "date": "2024-04-05",
     "document" : "science news"},

    {"title": "Quantum Computing Milestone", 
     "content": "Scientists achieve quantum advantage in practical application...", 
     "author": "Jane Doe", 
     "date": "2024-04-05",
     "document" : "science news"},

    {"title": "AI Advances in 2024", 
     "content": "Industry leaders debate ethical concerns around autonomous systems...", 
     "author": "John Smith", 
     "date": "2024-01-15",
     "document" : "ai news"},

    {"title": "Global Climate Outlook", 
     "content": "Experts warn that several regions may face increased droughts...", 
     "author": "Alice Johnson", 
     "date": "2024-02-20",
     "document" : "climate news"},

    {"title": "Space Exploration Updates", 
     "content": "New satellite network launches to improve global communication...", 
     "author": "Jane Doe", 
     "date": "2024-03-10",
     "document" : "space news"},

    {"title": "Healthcare Innovations", 
     "content": "Hospitals begin adopting AI-driven triage tools to reduce wait times...", 
     "author": "Bob Williams", 
     "date": "2024-04-05",
     "document" : "science news"},

    {"title": "Quantum Computing Milestone", 
     "content": "Commercial companies begin piloting quantum-based optimization services...", 
     "author": "Alice Johnson", 
     "date": "2024-04-07",
     "document" : "science news"}
]
# --8<-- [end: data]

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

chunks = []
for article in articles_data:
    chunk = Chunk(
        content=article['content'],
        document=article['document'],
        metadata={
            "title": article['title'],
            "author": article['author'],
            "date": article['date']
        }
    )
    chunks.append(chunk)

id_list = store.upsert(chunks)
# --8<-- [end: first_chroma_example]


