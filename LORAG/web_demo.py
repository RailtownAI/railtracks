"""
Web interface for the LORAG system.
"""

import os
import json
from flask import Flask, request, jsonify, render_template_string
from lorag import LORAG
from lorag.utils import write_file

# Create data directory if it doesn't exist
os.makedirs("data", exist_ok=True)

# Initialize LORAG system
lorag = LORAG(api_key=os.getenv("OPENAI_API_KEY"))

# Create Flask app
app = Flask(__name__)

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>LORAG Demo</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
        }
        .container {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
        }
        .panel {
            flex: 1;
            min-width: 300px;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            background-color: #f9f9f9;
        }
        textarea {
            width: 100%;
            height: 150px;
            margin-bottom: 10px;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        input[type="text"] {
            width: 100%;
            padding: 8px;
            margin-bottom: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        select {
            width: 100%;
            padding: 8px;
            margin-bottom: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        button {
            background-color: #4CAF50;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover {
            background-color: #45a049;
        }
        .result {
            margin-top: 20px;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            background-color: #fff;
        }
        .result-item {
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid #eee;
        }
        .result-item:last-child {
            border-bottom: none;
        }
        .file-name {
            font-weight: bold;
            color: #333;
        }
        .similarity {
            color: #666;
            font-size: 0.9em;
        }
        .content {
            margin-top: 10px;
            white-space: pre-wrap;
        }
        .methods {
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }
        .error {
            color: red;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h1>LORAG: Layered or Hybrid RAG System</h1>
    
    <div class="container">
        <div class="panel">
            <h2>Add Text</h2>
            <form id="addTextForm">
                <label for="textName">Text Name:</label>
                <input type="text" id="textName" name="textName" required>
                
                <label for="textContent">Text Content:</label>
                <textarea id="textContent" name="textContent" required></textarea>
                
                <button type="submit">Add Text</button>
            </form>
            <div id="addTextResult"></div>
        </div>
        
        <div class="panel">
            <h2>Search</h2>
            <form id="searchForm">
                <label for="searchQuery">Search Query:</label>
                <input type="text" id="searchQuery" name="searchQuery" required>
                
                <label for="searchMode">Search Mode:</label>
                <select id="searchMode" name="searchMode">
                    <option value="all">All</option>
                    <option value="raw">Raw</option>
                    <option value="smart">Smart</option>
                    <option value="order">Order</option>
                </select>
                
                <label for="nReturn">Number of Results:</label>
                <input type="number" id="nReturn" name="nReturn" value="3" min="1" max="10">
                
                <label for="effort">Effort Level:</label>
                <input type="number" id="effort" name="effort" value="2" min="1" max="5">
                
                <button type="submit">Search</button>
            </form>
            <div id="searchResult"></div>
        </div>
    </div>
    
    <script>
        // Add Text Form
        document.getElementById('addTextForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const textName = document.getElementById('textName').value;
            const textContent = document.getElementById('textContent').value;
            
            const response = await fetch('/api/add_text', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: textName,
                    content: textContent
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                document.getElementById('addTextResult').innerHTML = `
                    <p>Text added successfully with ID: ${result.file_id}</p>
                `;
                document.getElementById('textName').value = '';
                document.getElementById('textContent').value = '';
            } else {
                document.getElementById('addTextResult').innerHTML = `
                    <p class="error">Error: ${result.error}</p>
                `;
            }
        });
        
        // Search Form
        document.getElementById('searchForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const searchQuery = document.getElementById('searchQuery').value;
            const searchMode = document.getElementById('searchMode').value;
            const nReturn = document.getElementById('nReturn').value;
            const effort = document.getElementById('effort').value;
            
            document.getElementById('searchResult').innerHTML = '<p>Searching...</p>';
            
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query: searchQuery,
                    search_mode: searchMode,
                    n_return: parseInt(nReturn),
                    effort: parseInt(effort)
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                let html = '<div class="result">';
                
                if (result.results.length === 0) {
                    html += '<p>No results found.</p>';
                } else {
                    html += `<p>Found ${result.results.length} results using methods: ${result.methods_used.join(', ')}</p>`;
                    
                    result.results.forEach((item, index) => {
                        html += `
                            <div class="result-item">
                                <div class="file-name">${index + 1}. ${item.file_name}</div>
                                <div class="similarity">Similarity: ${item.weighted_score ? item.weighted_score.toFixed(4) : item.similarity ? item.similarity.toFixed(4) : 'N/A'}</div>
                                <div class="content">${item.content}</div>
                                <div class="methods">Methods: ${item.methods ? item.methods.join(', ') : item.method}</div>
                            </div>
                        `;
                    });
                }
                
                html += '</div>';
                document.getElementById('searchResult').innerHTML = html;
            } else {
                document.getElementById('searchResult').innerHTML = `
                    <p class="error">Error: ${result.error}</p>
                `;
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Render the web interface."""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/add_text', methods=['POST'])
def api_add_text():
    """Add text to the LORAG system."""
    try:
        data = request.json
        name = data.get('name')
        content = data.get('content')
        
        if not name or not content:
            return jsonify({'success': False, 'error': 'Name and content are required'})
        
        file_id = lorag.add_text(content, name)
        
        return jsonify({'success': True, 'file_id': file_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/search', methods=['POST'])
def api_search():
    """Search the LORAG system."""
    try:
        data = request.json
        query = data.get('query')
        search_mode = data.get('search_mode', 'all')
        n_return = data.get('n_return', 5)
        effort = data.get('effort', 2)
        
        if not query:
            return jsonify({'success': False, 'error': 'Query is required'})
        
        results = lorag.search(query, search_mode=search_mode, n_return=n_return, effort=effort)
        
        return jsonify({
            'success': True, 
            'results': results['results'],
            'methods_used': results['methods_used']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    # Create sample text
    sample_text = """
    LORAG (Layered or Hybrid RAG) is a flexible system that combines multiple search and retrieval methods.
    
    It can be configured in various "modes" to adapt to different use cases and resource constraints:
    
    1. "all" mode: Execute and return the results from all available search methods.
    
    2. "raw" mode: Similar to "all", but returns raw data along with intermediate scores.
    
    3. "smart" mode: The system asks an AI layer to consider the weighted outputs from each method.
    
    4. "order" mode: Search methods are used in a specific order, starting with faster methods.
    
    LORAG supports multiple search methods, including embedding-based search, file name lookup, summary-based search, regex search, and more.
    """
    
    lorag.add_text(sample_text, "lorag_description")
    print("Added sample text to LORAG system")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=50148, debug=True)