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
upserted_item = store.upsert("Oranges are orange")
upserted_list = store.upsert(["Bananas are yellow.", "Apples can be red or green."])
# --8<-- [end: second_step]

# --8<-- [start: second_step_metadata]
from railtracks.vector_stores.vector_store_base import Chunk

meta_data_chunk = Chunk(
    content="The Eiffel Tower is located in Paris.",
    document="france_guide.txt",
    metadata={"category": "travel"}
)

custom_id_chunk = Chunk(
    content="My favourite ai library is Railtracks",
)

custom_id_meta_chunk = Chunk(
    content="big ben is in London",
    document="england_guide.txt",
    metadata={"category": "travel"}
)

travel_chunks = [meta_data_chunk, custom_id_meta_chunk]

upserted_chunk = store.upsert(custom_id_chunk)
upserted_chunk_list = store.upsert(travel_chunks)
# --8<-- [end: second_step_metadata]

# --8<-- [start: third_step]
results = store.search("Where is the Eiffel Tower?", top_k=5)
print("Question: Where is the Eiffel Tower?")
print("Answer: " + results[0].content)
# --8<-- [end: third_step]

# --8<-- [start: third_step_complex]
search_queries = ["Where is the Eiffel Tower?", "what is the best ai library?"]
results2 = store.search(search_queries, top_k=1)
eiffel_tower_location = results2[0][0]
best_ai_library = results2[1][0]
# --8<-- [end: third_step_complex]

# --8<-- [start: fourth_step]
important_result = store.fetch("important_id_i_need_access_to")[0]
# print the fetched chunk string
print(important_result.content)

# get list of Fetch Results
more_results = store.fetch(upserted_chunk_list)

print(more_results[0].content)
print(more_results[1].content)
# --8<-- [end: fourth_step]

# --8<-- [start: fifth_step]
store.delete(upserted_chunk)
store.delete(upserted_chunk_list)
# --8<-- [end: fifth_step]


# --8<-- [start: first_example]
# Initialize embedding function
embedding_function = EmbeddingService().embed

# Step 1: Initialize vector store
store = ChromaVectorStore(
    collection_name="temporary_knowledge_base",
    embedding_function=embedding_function,
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

store = ChromaVectorStore(
    collection_name="article_archive",
    embedding_function=embedding_function,
    path="./chroma-data"
)

articles_data = [
    {"title": "AI Advances in 2024", "content": "Artificial intelligence saw major breakthroughs this year...", "author": "Jane Doe", "date": "2024-01-15"},
    {"title": "Climate Change Report", "content": "New studies show accelerating impacts of climate change...", "author": "John Smith", "date": "2024-02-20"},
    {"title": "Space Exploration Updates", "content": "Mars mission successfully lands new rover...", "author": "Alice Johnson", "date": "2024-03-10"},
    {"title": "Healthcare Innovations", "content": "Revolutionary new treatment for rare diseases approved...", "author": "Bob Williams", "date": "2024-04-05"},
    {"title": "Quantum Computing Milestone", "content": "Scientists achieve quantum advantage in practical application...", "author": "Jane Doe", "date": "2024-04-05"}
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

results2 = store.search(search_queries, top_k=3, where={"author" : "Jane Doe"})
store.delete(article_ids, where={"date" : "2024-04-05"})
# --8<-- [end: second_example]