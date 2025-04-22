INTRODUCTION ──────────────────────────────────────────────────────── Retrieval Augmented Generation (RAG) is a technique often used alongside Large Language Models (LLMs) to improve the quality of generated responses by providing relevant context from external documents. However, standard RAG approaches sometimes encounter issues, such as returning irrelevant documents or failing to provide sufficient information because of incomplete chunking.
To address these shortcomings, we propose “LORAG” (Layered or Hybrid RAG), a system that can adaptively and intelligently combine multiple search methods, including the standard embedding-based approach. The system can be configured to use any subset of search methods, either individually or in combination, depending on the user’s needs.

────────────────────────────────────────────────────────
2. COMMON PROBLEMS WITH TRADITIONAL RAG
────────────────────────────────────────────────────────

Irrelevant Yet Related Files
– Files might be topically related but contain no direct answer. For instance, if a user asks a chemical formula question, an embedding approach could surface a company’s financial report that only mentions “chemicals” in passing.

Chunk Size and Contextual Weighting
– Very long files can become “messy”: they may contain multiple, diverse topics, making it hard to match a single query effectively.
– Very short files (over-chunked) split a cohesive idea into separate parts, risking partial or incomplete embeddings.

Over-Emphasis on Semantic Similarity of Queries
– Embedding-based matching prioritizes semantic similarity. If the user’s query is phrased in a certain style (“a question about X”), the system might be biased toward documents that feature questions rather than solutions.

Loss of Context in Summaries
– A single summary for a large document may be too broad, or it may oversimplify the text and lose critical details that a user’s query relies on.

Coverage of All Relevant Documents
– If the user wants “all information” on a topic, RAG might retrieve top matches but omit other important documents due to embedding cutoffs or threshold-based retrieval.

────────────────────────────────────────────────────────
3. OVERVIEW OF THE LORAG MODULE
────────────────────────────────────────────────────────
LORAG is a flexible system that combines multiple search and retrieval methods. It can be configured in various “modes” to adapt to different use cases and resource constraints. This modular approach helps overcome the limitations of relying solely on a single RAG method.

────────────────────────────────────────────────────────
4. MODES OF LORAG SEARCH
────────────────────────────────────────────────────────

"all"
– Execute and return the results from all available search methods. Pre-configured weights can be used to combine the results.

"raw"
– Similar to “all”, but returns raw data along with intermediate scores. Users can handle the ensemble weighting themselves.

"smart"
– The system asks an AI layer to consider the weighted outputs from each method, then make a decision on which results to keep.
• "n_ai": the top N results from each method that the AI can access.
• "n_out": the number of final results to return after the AI’s selection.

"order"
– Search methods are used in a specific order, typically starting with faster or cheaper methods. If additional information is needed (e.g., no clear winner), the system escalates to more complex methods.

────────────────────────────────────────────────────────
5. SPECIAL CALLING PARAMETERS
────────────────────────────────────────────────────────
• "blacklist_file"
– A list of files to ignore. If the initial results are unsatisfactory, this parameter helps exclude unhelpful files in subsequent searches.

• "effort"
– A measure of how much computational budget or depth of search the system should use. Higher effort may trigger more sophisticated or slower methods.

• "search_mode"
– Determines which mode to run (“all”, “raw”, “smart”, or “order”).

• "n_return"
– Sets how many files to return. If left unspecified, the system defaults to 100.

• "n_token"
– Attempts to return files such that the total token count stays within a certain limit (particularly relevant for GPT-4 or similar models). This conflicts with “n_return” if used together.

• "n_confidence"
– The number of top files to consider for confidence scoring. If unspecified, it defaults to the value of “n_return”.

... (open to more)

────────────────────────────────────────────────────────
6. SPECIAL RETURN PARAMETERS
────────────────────────────────────────────────────────
• "weights"
– Outputs the weighting data from each method, allowing insight into how each document or chunk was scored.

• "confidence"
– A measure of how likely a returned document is relevant. The system may assign a confidence score to each file, up to “n_confidence” or “n_return”, whichever is higher.

... (open to more)

────────────────────────────────────────────────────────
7. SEARCH METHODS
────────────────────────────────────────────────────────

Query Rewriting
– Rewrites the user’s query to improve searchability (for example, translating a question into a statement).

Embedding (Standard RAG)
– Splits documents into chunks (when necessary), then uses embeddings to semantically retrieve the most relevant chunks.

File Name Lookup
– Allows selection or filtering by file name, especially useful when the user already knows which file to reference.

File Name RAG
– Embedding-based retrieval but only on the file names, which can be helpful when explicit file names are used as references.

Summary RAG: Chunk
– Uses summaries of each chunk as the searchable text.

Summary RAG: Document
– Uses a single summary of the entire document. While this is highly compressed, it can be faster but may lose finer details.

Regex Search
– Searches for exact or pattern-based matches within the text, valuable when specific terms or IDs are needed.

File Structure Traversal
– Considers the hierarchical folder structure to locate documents. For instance, it can search parent directories or subdirectories if direct matches are not found in a single folder.

SQL Query
– Generates and executes SQL queries on the chunk database’s metadata. This is useful when performing more complex queries involving multiple filters or joins (e.g., date ranges, tag intersections).

────────────────────────────────────────────────────────
8. DATA STRUCTURE
────────────────────────────────────────────────────────
Two databases are used to store and manage the text: one for chunks, and one for file-level details.

Chunk Database
• id: unique chunk ID (e.g., 1234)
• chunk_name: combination of file name and chunk index (e.g., "file1:1")
• file_name_embedding: embedding of the chunk name
• tags: list of descriptive tags for the chunk (e.g., ["tag1", "tag2"])
• puretext: the raw text content of the chunk
• summary: an AI-generated summary of the chunk
• embedding: the semantic embedding vector for the chunk

File Database
• id: unique file ID (e.g., 5678)
• name: the file’s name (e.g., "file1")
• file_name_embedding: embedding of the file name
• tags: consolidated tags from all chunks in the file
• file_path: the file’s location in the system
• puretext: a copy of (or link to) the file’s entire text
• summary: an AI-generated summary of the entire file (larger or more comprehensive than a single chunk summary)
• embedding: a global embedding for the entire file

────────────────────────────────────────────────────────
9. ADDITIONAL CONSIDERATIONS
────────────────────────────────────────────────────────

Chunk Size & Overlap
– Determining the optimal chunk size is tricky: too large and you lose specificity; too small and you split cohesive concepts. Overlaps can help capture context that crosses chunk boundaries.

Handling Conflicting or Redundant Information
– Multiple chunks or files may contain contradictory or redundant data. The system should detect these overlaps and unify, rank, or highlight inconsistencies to the user.

Multi-Lingual Queries and Content
– If users ask questions in various languages, consider adding language detection and translation layers to ensure embeddings are comparable across languages.

Document Versioning and Freshness
– Files may be updated over time, requiring re-chunking and re-embedding. Make sure the system can track or invalidate old embeddings when the original text changes significantly.

Performance and Scalability
– As the number of files grows, you may need more efficient indexing or parallel search. Techniques like approximate nearest neighbor (ANN) for embeddings can reduce latency.

Security, Privacy, and Access Control
– Some documents may be confidential. The system’s search functionality needs to respect user permissions to avoid exposing restricted information.

End-to-End Logging and Monitoring
– Log which methods contributed to the final answers. This helps in debugging retrieval failures and auditing the system’s behavior.

Evaluating “Completeness” of Results
– When a user asks for “all info”, ensure the system has a strategy to confirm whether additional relevant files exist beyond the initial retrieval.

Cost vs. Quality Trade-Off
– Using all methods (like “all” or “smart” with high “effort”) may be more expensive. For budget or time constraints, “order” mode allows prioritizing cheaper methods first and escalating if needed.

────────────────────────────────────────────────────────
SUMMARY
────────────────────────────────────────────────────────
LORAG aims to address the pitfalls of traditional RAG by offering a suite of retrieval methods, adjustable parameters for controlling search depth and output size, and flexible modes of operation. It stores data in a structured manner—across chunk-level and file-level databases—making it easier to combine multiple retrieval strategies. By doing so, it helps ensure that users get more accurate, relevant, and complete answers for their queries.