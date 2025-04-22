"""
Search engine module for LORAG.

This module provides functionality for searching documents using different methods.
"""

import os
import json
import numpy as np
from typing import List, Dict, Any, Optional, Union, Tuple
from .database import ChunkDatabase, FileDatabase
from .search_methods import (
    BaseSearchMethod,
    EmbeddingSearch,
    FileNameLookup,
    FileNameEmbeddingSearch,
    SummaryRAGChunk,
    SummaryRAGDocument,
    RegexSearch,
    FileStructureTraversal,
    SQLQuery,
    QueryRewriting
)
from .text_processing import TextProcessor

class DocumentSearchEngine:
    """Search engine for LORAG."""
    
    def __init__(self, 
            api_key: str, 
            chunk_db: ChunkDatabase, 
            file_db: FileDatabase, 
            text_processor: TextProcessor):
        """Initialize the search engine.
        
        Args:
            api_key: OpenAI API key
            chunk_db: Chunk database instance
            file_db: File database instance
            text_processor: Text processor instance
        """
        self.api_key = api_key
        self.chunk_db = chunk_db
        self.file_db = file_db
        self.text_processor = text_processor
        
        # Initialize search methods
        self.search_methods = {
            'embedding': EmbeddingSearch(self.chunk_db, self.file_db, api_key),
            'file_name_lookup': FileNameLookup(self.chunk_db, self.file_db),
            'file_name_embedding': FileNameEmbeddingSearch(self.chunk_db, self.file_db, api_key),
            'summary_rag_chunk': SummaryRAGChunk(self.chunk_db, self.file_db, api_key),
            'summary_rag_document': SummaryRAGDocument(self.chunk_db, self.file_db, api_key),
            'regex': RegexSearch(self.chunk_db, self.file_db),
            'file_structure': FileStructureTraversal(self.chunk_db, self.file_db),
            'sql_query': SQLQuery(self.chunk_db, self.file_db),
            'query_rewriting': QueryRewriting(self.chunk_db, self.file_db, api_key)
        }
    
    def search(self, query: str, search_mode: str = "all", n_return: int = 5, 
               n_token: Optional[int] = None, n_confidence: Optional[int] = None,
               blacklist_file: Optional[List[str]] = None, effort: int = 1,
               weights: Optional[Dict[str, float]] = None, **kwargs) -> Dict[str, Any]:
        """Search for relevant documents.
        
        Args:
            query: The search query
            search_mode: Search mode ("all", "raw", "smart", or "order")
            n_return: Number of results to return
            n_token: Maximum token count for results
            n_confidence: Number of top files to consider for confidence scoring
            blacklist_file: List of files to ignore
            effort: Computational budget or depth of search
            weights: Weights for each search method
            **kwargs: Additional search parameters
            
        Returns:
            Search results
        """
        # Set default weights if not provided
        if weights is None:
            weights = {
                'embedding': 1.0,
                'file_name_embedding': 0.7,
                'summary_rag_chunk': 0.6,
                'summary_rag_document': 0.5,
                'regex': 0.4,
                'file_structure': 0.3,
                'sql_query': 0.2,
                'query_rewriting': 0.9
            }
        
        # Set default n_confidence if not provided
        if n_confidence is None:
            n_confidence = n_return
        
        # Initialize blacklist
        if blacklist_file is None:
            blacklist_file = []
        
        # Execute search based on mode
        if search_mode == "all":
            return self._search_all(query, n_return, n_token, n_confidence, blacklist_file, effort, weights, **kwargs)
        elif search_mode == "raw":
            return self._search_raw(query, n_return, n_token, n_confidence, blacklist_file, effort, weights, **kwargs)
        elif search_mode == "smart":
            return self._search_smart(query, n_return, n_token, n_confidence, blacklist_file, effort, weights, **kwargs)
        elif search_mode == "order":
            return self._search_order(query, n_return, n_token, n_confidence, blacklist_file, effort, weights, **kwargs)
        else:
            raise ValueError(f"Invalid search mode: {search_mode}")
    
    def _search_all(self, query: str, n_return: int, n_token: Optional[int], 
                   n_confidence: int, blacklist_file: List[str], effort: int,
                   weights: Dict[str, float], **kwargs) -> Dict[str, Any]:
        """Execute and return results from all available search methods.
        
        Args:
            query: The search query
            n_return: Number of results to return
            n_token: Maximum token count for results
            n_confidence: Number of top files to consider for confidence scoring
            blacklist_file: List of files to ignore
            effort: Computational budget or depth of search
            weights: Weights for each search method
            **kwargs: Additional search parameters
            
        Returns:
            Search results
        """
        # Determine which methods to use based on effort
        methods_to_use = []
        
        if effort >= 1:
            methods_to_use.extend(['embedding', 'file_name_lookup'])
        
        if effort >= 2:
            methods_to_use.extend(['file_name_embedding', 'regex'])
        
        if effort >= 3:
            methods_to_use.extend(['summary_rag_document'])
        
        if effort >= 4:
            methods_to_use.extend(['summary_rag_chunk', 'file_structure'])
        
        if effort >= 5:
            methods_to_use.extend(['query_rewriting', 'sql_query'])
        
        # Execute each search method
        all_results = {}
        
        for method_name in methods_to_use:
            method = self.search_methods[method_name]
            
            # Special handling for query rewriting
            if method_name == 'query_rewriting':
                # Use embedding search with rewritten query
                results = method.search(query, n_return=n_return, 
                                       search_method=self.search_methods['embedding'], 
                                       **kwargs)
            else:
                results = method.search(query, n_return=n_return, **kwargs)
            
            all_results[method_name] = results
        
        # Combine and weight results
        combined_results = self._combine_results(all_results, weights, blacklist_file)
        
        # Sort by weighted score
        combined_results.sort(key=lambda x: x['weighted_score'], reverse=True)
        
        # Filter by token count if specified
        if n_token is not None:
            filtered_results = []
            total_tokens = 0
            
            for result in combined_results:
                content_tokens = self.text_processor.count_tokens(result['content']) if result.get('content') else 0
                
                if total_tokens + content_tokens <= n_token:
                    filtered_results.append(result)
                    total_tokens += content_tokens
                else:
                    break
            
            combined_results = filtered_results
        
        # Limit to n_return
        limited_results = combined_results[:n_return]
        
        # Calculate confidence scores
        confidence_scores = self._calculate_confidence(limited_results, n_confidence)
        
        # Prepare final results
        final_results = {
            'results': limited_results,
            'confidence': confidence_scores,
            'weights': weights,
            'methods_used': methods_to_use
        }
        
        return final_results
    
    def _search_raw(self, query: str, n_return: int, n_token: Optional[int], 
                   n_confidence: int, blacklist_file: List[str], effort: int,
                   weights: Dict[str, float], **kwargs) -> Dict[str, Any]:
        """Return raw data along with intermediate scores.
        
        Args:
            query: The search query
            n_return: Number of results to return
            n_token: Maximum token count for results
            n_confidence: Number of top files to consider for confidence scoring
            blacklist_file: List of files to ignore
            effort: Computational budget or depth of search
            weights: Weights for each search method
            **kwargs: Additional search parameters
            
        Returns:
            Raw search results
        """
        # Determine which methods to use based on effort
        methods_to_use = []
        
        if effort >= 1:
            methods_to_use.extend(['embedding', 'file_name_lookup'])
        
        if effort >= 2:
            methods_to_use.extend(['file_name_embedding', 'regex'])
        
        if effort >= 3:
            methods_to_use.extend(['summary_rag_document'])
        
        if effort >= 4:
            methods_to_use.extend(['summary_rag_chunk', 'file_structure'])
        
        if effort >= 5:
            methods_to_use.extend(['query_rewriting', 'sql_query'])
        
        # Execute each search method
        all_results = {}
        
        for method_name in methods_to_use:
            method = self.search_methods[method_name]
            
            # Special handling for query rewriting
            if method_name == 'query_rewriting':
                # Use embedding search with rewritten query
                results = method.search(query, n_return=n_return, 
                                       search_method=self.search_methods['embedding'], 
                                       **kwargs)
            else:
                results = method.search(query, n_return=n_return, **kwargs)
            
            all_results[method_name] = results
        
        # Prepare raw results
        raw_results = {
            'raw_results': all_results,
            'weights': weights,
            'methods_used': methods_to_use
        }
        
        return raw_results
    
    def _search_smart(self, query: str, n_return: int, n_token: Optional[int], 
                     n_confidence: int, blacklist_file: List[str], effort: int,
                     weights: Dict[str, float], n_ai: int = 3, n_out: int = 5,
                     **kwargs) -> Dict[str, Any]:
        """Use AI to select the best results from each method.
        
        Args:
            query: The search query
            n_return: Number of results to return
            n_token: Maximum token count for results
            n_confidence: Number of top files to consider for confidence scoring
            blacklist_file: List of files to ignore
            effort: Computational budget or depth of search
            weights: Weights for each search method
            n_ai: Number of top results from each method for AI to consider
            n_out: Number of final results to return after AI selection
            **kwargs: Additional search parameters
            
        Returns:
            AI-selected search results
        """
        # Determine which methods to use based on effort
        methods_to_use = []
        
        if effort >= 1:
            methods_to_use.extend(['embedding', 'file_name_lookup'])
        
        if effort >= 2:
            methods_to_use.extend(['file_name_embedding', 'regex'])
        
        if effort >= 3:
            methods_to_use.extend(['summary_rag_document'])
        
        if effort >= 4:
            methods_to_use.extend(['summary_rag_chunk', 'file_structure'])
        
        if effort >= 5:
            methods_to_use.extend(['query_rewriting', 'sql_query'])
        
        # Execute each search method
        all_results = {}
        
        for method_name in methods_to_use:
            method = self.search_methods[method_name]
            
            # Special handling for query rewriting
            if method_name == 'query_rewriting':
                # Use embedding search with rewritten query
                results = method.search(query, n_return=n_ai, 
                                       search_method=self.search_methods['embedding'], 
                                       **kwargs)
            else:
                results = method.search(query, n_return=n_ai, **kwargs)
            
            all_results[method_name] = results
        
        # Combine results for AI selection
        combined_results = []
        
        for method_name, results in all_results.items():
            for result in results:
                # Add method information
                result['method'] = method_name
                result['weight'] = weights.get(method_name, 0.5)
                
                combined_results.append(result)
        
        # Filter out blacklisted files
        filtered_results = [r for r in combined_results if r.get('file_name') not in blacklist_file]
        
        # Prepare data for AI selection
        ai_input = {
            'query': query,
            'results': filtered_results,
            'n_out': n_out
        }
        
        # Use AI to select the best results
        selected_results = self._ai_select_results(ai_input)
        
        # Calculate confidence scores
        confidence_scores = self._calculate_confidence(selected_results, n_confidence)
        
        # Prepare final results
        final_results = {
            'results': selected_results,
            'confidence': confidence_scores,
            'weights': weights,
            'methods_used': methods_to_use
        }
        
        return final_results
    
    def _search_order(self, query: str, n_return: int, n_token: Optional[int], 
                     n_confidence: int, blacklist_file: List[str], effort: int,
                     weights: Dict[str, float], **kwargs) -> Dict[str, Any]:
        """Search methods in a specific order, escalating if needed.
        
        Args:
            query: The search query
            n_return: Number of results to return
            n_token: Maximum token count for results
            n_confidence: Number of top files to consider for confidence scoring
            blacklist_file: List of files to ignore
            effort: Computational budget or depth of search
            weights: Weights for each search method
            **kwargs: Additional search parameters
            
        Returns:
            Search results
        """
        # Define search order based on effort
        search_order = []
        
        if effort >= 1:
            search_order.append('file_name_lookup')
        
        if effort >= 2:
            search_order.append('embedding')
        
        if effort >= 3:
            search_order.append('file_name_embedding')
        
        if effort >= 4:
            search_order.append('regex')
        
        if effort >= 5:
            search_order.append('summary_rag_document')
        
        # Execute search methods in order
        all_results = []
        
        for method_name in search_order:
            method = self.search_methods[method_name]
            
            # Execute search
            results = method.search(query, n_return=n_return, **kwargs)
            
            # Add results
            all_results.extend(results)
            
            # Check if we have enough results
            if len(all_results) >= n_return:
                break
        
        # Filter out blacklisted files
        filtered_results = [r for r in all_results if r.get('file_name') not in blacklist_file]
        
        # Sort by similarity
        filtered_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        
        # Filter by token count if specified
        if n_token is not None:
            token_filtered_results = []
            total_tokens = 0
            
            for result in filtered_results:
                content_tokens = self.text_processor.count_tokens(result['content']) if result.get('content') else 0
                
                if total_tokens + content_tokens <= n_token:
                    token_filtered_results.append(result)
                    total_tokens += content_tokens
                else:
                    break
            
            filtered_results = token_filtered_results
        
        # Limit to n_return
        limited_results = filtered_results[:n_return]
        
        # Calculate confidence scores
        confidence_scores = self._calculate_confidence(limited_results, n_confidence)
        
        # Prepare final results
        final_results = {
            'results': limited_results,
            'confidence': confidence_scores,
            'weights': weights,
            'methods_used': search_order
        }
        
        return final_results
    
    def _combine_results(self, all_results: Dict[str, List[Dict[str, Any]]], 
                        weights: Dict[str, float], blacklist_file: List[str]) -> List[Dict[str, Any]]:
        """Combine results from multiple search methods.
        
        Args:
            all_results: Results from each search method
            weights: Weights for each search method
            blacklist_file: List of files to ignore
            
        Returns:
            Combined and weighted results
        """
        # Combine all results
        combined_results = []
        
        for method_name, results in all_results.items():
            for result in results:
                # Check if file is blacklisted
                if result.get('file_name') in blacklist_file:
                    continue
                
                # Check if result already exists
                existing_result = None
                
                for r in combined_results:
                    if (r.get('file_id') == result.get('file_id') and 
                        r.get('chunk_id') == result.get('chunk_id')):
                        existing_result = r
                        break
                
                if existing_result:
                    # Update existing result
                    existing_result['methods'].append(method_name)
                    existing_result['similarities'].append(result.get('similarity', 0))
                    
                    # Update weighted score
                    method_weight = weights.get(method_name, 0.5)
                    similarity = result.get('similarity', 0)
                    existing_result['weighted_score'] += method_weight * similarity
                else:
                    # Create new result
                    method_weight = weights.get(method_name, 0.5)
                    similarity = result.get('similarity', 0)
                    weighted_score = method_weight * similarity
                    
                    new_result = {
                        'file_id': result.get('file_id'),
                        'file_name': result.get('file_name'),
                        'file_path': result.get('file_path'),
                        'chunk_id': result.get('chunk_id'),
                        'chunk_name': result.get('chunk_name'),
                        'content': result.get('content'),
                        'summary': result.get('summary'),
                        'methods': [method_name],
                        'similarities': [similarity],
                        'weighted_score': weighted_score
                    }
                    
                    combined_results.append(new_result)
        
        return combined_results
    
    def _calculate_confidence(self, results: List[Dict[str, Any]], n_confidence: int) -> Dict[str, float]:
        """Calculate confidence scores for results.
        
        Args:
            results: Search results
            n_confidence: Number of top files to consider for confidence scoring
            
        Returns:
            Confidence scores
        """
        # Limit to n_confidence
        top_results = results[:n_confidence]
        
        # Calculate confidence scores
        confidence_scores = {}
        
        for i, result in enumerate(top_results):
            # Calculate confidence based on position and weighted score
            position_weight = 1.0 - (i / len(top_results)) if len(top_results) > 1 else 1.0
            score_weight = result.get('weighted_score', 0)
            
            # Normalize score weight
            max_score = max([r.get('weighted_score', 0) for r in top_results])
            normalized_score = score_weight / max_score if max_score > 0 else 0
            
            # Calculate confidence
            confidence = 0.7 * position_weight + 0.3 * normalized_score
            
            # Add to confidence scores
            confidence_scores[result.get('file_name', f"result_{i}")] = confidence
        
        return confidence_scores
    
    def _ai_select_results(self, ai_input: Dict[str, Any], add_content:bool=False) -> List[Dict[str, Any]]:
        """Use AI to select the best results.
        
        Args:
            ai_input: Input data for AI selection
            
        Returns:
            AI-selected results
        """
        # Prepare input for AI
        query = ai_input['query']
        results = ai_input['results']
        n_out = ai_input['n_out']
        
        # Create a summary of each result
        result_summaries = []
        
        for i, result in enumerate(results):
            summary = f"Result {i+1}:\n"
            summary += f"File: {result.get('file_name', 'Unknown')}\n"
            summary += f"Method: {result.get('method', 'Unknown')}\n"
            summary += f"Similarity: {result.get('similarity', 0)}\n"
            summary += f"Weight: {result.get('weight', 0)}\n"
            if add_content==True:
                summary += f"Summary: {result.get('summary', 'No summary available')}\n"
                summary += f"Content: {result.get('content', 'No content available')[:200]}...\n"
                
            result_summaries.append(summary)
        
        # Combine summaries
        all_summaries = "\n".join(result_summaries)
        
        # Create prompt for AI
        prompt = f"""
        Query: {query}
        
        Available Results:
        {all_summaries}
        
        Please select the {n_out} most relevant results for the query. Consider the following criteria:
        1. Relevance to the query.
        2. Quality and completeness of information.
        3. Diversity of sources.
        
        File is defined as a embedding search of the query against the complete file.
        
        
        For each selected result, provide the result number and a brief explanation of why it was selected.
        """
        
        # Get AI response
        from openai import OpenAI
        self.client = OpenAI()
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional engineering that selects the most relevant search results for a query."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse AI response to get selected result indices
        ai_response = response.choices[0].message.content
        selected_indices = []
        
        for i in range(len(results)):
            if f"Result {i+1}:" in ai_response:
                selected_indices.append(i)
        
        # Limit to n_out
        selected_indices = selected_indices[:n_out]
        
        # Get selected results
        selected_results = [results[i] for i in selected_indices]
        
        return selected_results