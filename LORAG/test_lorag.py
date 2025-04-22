"""
Test script for the LORAG system.
"""

import os
import json
from lorag import LORAG
from lorag.utils import write_file

def main():
    """Test the LORAG system."""
    # OpenAI API key
    
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    # Initialize LORAG system
    lorag = LORAG(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Add text directly to LORAG system
    text = """
    LORAG (Layered or Hybrid RAG) is a flexible system that combines multiple search and retrieval methods.
    
    It can be configured in various "modes" to adapt to different use cases and resource constraints:
    
    1. "all" mode: Execute and return the results from all available search methods.
    
    2. "raw" mode: Similar to "all", but returns raw data along with intermediate scores.
    
    3. "smart" mode: The system asks an AI layer to consider the weighted outputs from each method.
    
    4. "order" mode: Search methods are used in a specific order, starting with faster methods.
    
    LORAG supports multiple search methods, including embedding-based search, file name lookup, summary-based search, regex search, and more.
    """
    
    file_id = lorag.add_text(text, "lorag_test")
    print(f"Added text to LORAG system with ID: {file_id}")
    
    # Test different search modes
    test_queries = [
        "What is LORAG?",
        "Explain the different modes in LORAG",
        "What search methods does LORAG support?"
    ]
    
    search_modes = ["all", "raw", "smart", "order"]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        
        for mode in search_modes:
            print(f"\n  Mode: {mode}")
            
            try:
                results = lorag.search(query, search_mode=mode, n_return=1, effort=2)
                
                if mode == "raw":
                    print(f"    Raw results available: {len(results['raw_results'])}")
                else:
                    if results['results']:
                        top_result = results['results'][0]
                        print(f"    Top result: {top_result['file_name']}")
                        print(f"    Similarity: {top_result.get('weighted_score', top_result.get('similarity', 0)):.4f}")
                        print(f"    Content: {top_result['content'][:100]}...")
                    else:
                        print("    No results found.")
            except Exception as e:
                print(f"    Error: {str(e)}")
    
    print("\nLORAG system test completed successfully!")

if __name__ == "__main__":
    main()