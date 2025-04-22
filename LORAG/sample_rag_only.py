import openai
import os

# Initialize OpenAI with your API key
openai.api_key = "sk-fG2zr4un7AuKbK7O99JocEiOO9OUF-S9L-tUfxed78T3BlbkFJEolke0bDBQwq0S7AVrnzDOknQBLUHEiitc09qdIrcA"

import os
from openai import OpenAI
import numpy as np


# Helper function to compute cosine similarity between two vectors.
def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def get_embedding(text, model="text-embedding-ada-002"):
    """
    Returns the embedding of the given text using OpenAI's Embeddings API.
    """
    client = OpenAI()

    response = client.embeddings.create(
        input=text,
        model=model
    )
    # The API can return multiple embeddings; we assume a single input so we take the first element
    return np.array(response.data[0].embedding)

def load_documents_from_folder(folder_path="data"):
    """
    Load all text files from the specified folder and return a list of (filename, text).
    """
    docs = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            # if is txtx
            if filename.endswith(".txt"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                    docs.append((filename, text))
    return docs

def build_document_embeddings(folder_path="data", model="text-embedding-ada-002"):
    """
    Read documents from folder, compute embeddings, and return
    a list of (filename, text, embedding).
    """
    documents = load_documents_from_folder(folder_path)
    doc_embeddings = []
    for filename, text in documents:
        emb = get_embedding(text, model=model)
        doc_embeddings.append((filename, text, emb))
    return doc_embeddings

def retrieve_documents(question, doc_embeddings, max_return=3, model="text-embedding-ada-002"):
    """
    Given a question and a list of (filename, text, embedding) for documents,
    return the top 'max_return' most relevant documents.
    """
    # 1. Get embedding for the query
    query_emb = get_embedding(question, model=model)
    
    # 2. Rank documents by similarity
    scores = []
    for (filename, text, emb) in doc_embeddings:
        score = cosine_similarity(query_emb, emb)
        scores.append((score, filename, text))
    
    # 3. Sort and return top N
    scores.sort(key=lambda x: x[0], reverse=True)
    top_docs = scores[:max_return]
    return top_docs


    

if __name__ == "__main__":
    # --- BUILD EMBEDDINGS ONCE ---
    # In an actual application, you'd do this once at startup and possibly store/cache them
    doc_embeddings = build_document_embeddings(folder_path="data")
    
    # --- USAGE EXAMPLE ---
    user_question = "What is the deadline for the project?"
    max_return = 3
    
    top_docs = retrieve_documents(user_question, doc_embeddings, max_return=max_return)
    
    print(f"Top {max_return} documents relevant to your question:")
    for i, (score, filename, text) in enumerate(top_docs, start=1):
        print(f"\n{i}. {filename} (score: {score:.4f+0.2})")
        # Optionally, show an excerpt of the text:
        print(f"Excerpt: {text[:200]}...")