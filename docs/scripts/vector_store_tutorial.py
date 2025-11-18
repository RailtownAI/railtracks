# --8<-- [start: chroma_imports]
from railtracks.vector_stores.chroma import ChromaVectorStore
from railtracks.rag.embedding_service import EmbeddingService
# --8<-- [end: chroma_imports   ]

# --8<-- [start: embedding_function]
embedding_function = EmbeddingService().embed
# --8<-- [end: embedding_function]

# --8<-- [start: first_step]
store = ChromaVectorStore(
    collection_name="my_collection",
    embedding_function=embedding_function,
    path="./chroma-data"
)
# --8<-- [end: first_step]

# --8<-- [start: second_step]
ids = store.upsert(["Bananas are yellow.", "Apples can be red or green."])
# --8<-- [end: second_step]

# --8<-- [start: second_step_metadata]
from railtracks.vector_stores.vector_store_base import Chunk

chunk = Chunk(
    content="The Eiffel Tower is located in Paris.",
    document="france_guide.txt",
    metadata={"category": "travel"}
)

store.upsert(chunk)
# --8<-- [end: second_step_metadata]

# --8<-- [start: third_step]
results = store.search("Where is the Eiffel Tower?", top_k=5)
# --8<-- [end: third_step]

# --8<-- [start: fourth_step]
id_to_fetch = ids[0]
details = store.fetch(id_to_fetch)
# --8<-- [end: fourth_step]

# --8<-- [start: fifth_step]
store.delete(ids_to_delete)
# --8<-- [end: fifth_step]



# --8<-- [start: first_example]
# Initialize embedding function
model = SentenceTransformer('all-MiniLM-L6-v2')

def my_embedding_function(texts):
    if isinstance(texts, str):
        texts = [texts]
    return model.encode(texts).tolist()

# Step 1: Initialize vector store
store = ChromaVectorStore(
    collection_name="knowledge_base",
    embedding_function=my_embedding_function,
    #No further specifications result in temporary store
)

# Step 2: Insert text
text = [
    "Python is a high-level programming language.",
    "Machine learning is a subset of artificial intelligence.",
    "Neural networks are inspired by biological neural networks.",
    "Deep learning uses multiple layers of neural networks."
]

text_ids = store.upsert(text)

#Check size of store matches size of text length
print(len(text) == store.count())

# Step 3: Search for relevant information
query = "What is machine learning?"
results = store.search(query, top_k=3)


print("Question: What is machine learning?")
print("Answer: " + results[0].content)
# --8<-- [end: first_example]


# --8<-- [start: second_example]
model = SentenceTransformer('all-MiniLM-L6-v2')

def my_embedding_function(texts):
    if isinstance(texts, str):
        texts = [texts]
    return model.encode(texts).tolist()


store = ChromaVectorStore(
    collection_name="article_archive",
    embedding_function=my_embedding_function,
    path="./chroma-data" #Specify local path to get existing store from or create new one
)

articles_data = [
    {"title": "AI Advances in 2024", "content": "Artificial intelligence saw major breakthroughs this year...", "author": "Jane Doe", "date": "2024-01-15"},
    {"title": "Climate Change Report", "content": "New studies show accelerating impacts of climate change...", "author": "John Smith", "date": "2024-02-20"},
    {"title": "Space Exploration Updates", "content": "Mars mission successfully lands new rover...", "author": "Alice Johnson", "date": "2024-03-10"},
    {"title": "Healthcare Innovations", "content": "Revolutionary new treatment for rare diseases approved...", "author": "Bob Williams", "date": "2024-04-05"},
    {"title": "Quantum Computing Milestone", "content": "Scientists achieve quantum advantage in practical application...", "author": "Jane Doe", "date": "2024-05-12"}
]


chunks = []
for article in articles_data:
    chunk = Chunk(
        content=f"{article['title']}: {article['content']}",
        document=f"article_{article['date']}.txt",
        metadata={
            "title": article['title'],
            "author": article['author'],
            "date": article['date']
        }
    )
    chunks.append(chunk)

article_ids = store.upsert(chunks)

search_queries = [
    "artificial intelligence",
    "space and planets",
    "medical breakthroughs",
]

results = store.search(search_queries, top_k=3)


ids_to_delete = []
for article_id in article_ids:
    article = store.fetch(article_id)
    if article.metadata['date'] < '2024-03-01':
        ids_to_delete.append(article_id)

if ids_to_delete:
    store.delete(ids_to_delete)
# --8<-- [end: second_example]