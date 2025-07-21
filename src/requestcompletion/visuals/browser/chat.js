let eventSource = null;
let isProcessing = false;
let messageCount = 0;
let currentTab = 'chat';
let toolsData = [];

// Configure marked.js for better security and styling
if (typeof marked !== 'undefined') {
    marked.setOptions({
        breaks: true, // Convert \n to <br>
        gfm: true,    // GitHub Flavored Markdown
        sanitize: false, // Allow HTML (we trust our content)
        smartLists: true,
        smartypants: true
    });
}

// Tab switching functionality
function switchTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Remove active class from all tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected tab content
    if (tabName === 'chat') {
        document.getElementById('chatTab').classList.add('active');
    } else if (tabName === 'tools') {
        document.getElementById('toolsTab').classList.add('active');
    }
    
    // Add active class to clicked tab
    event.target.classList.add('active');
    currentTab = tabName;
}

// Initialize SSE connection
function initializeSSE() {
    eventSource = new EventSource('/events');
    
    eventSource.onopen = function(event) {
        console.log('SSE connection opened');
        updateConnectionStatus(true);
    };
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            handleSSEMessage(data);
        } catch (error) {
            console.error('Error parsing SSE message:', error);
        }
    };
    
    eventSource.onerror = function(event) {
        console.error('SSE connection error:', event);
        updateConnectionStatus(false);
        
        // Reconnect after 3 seconds
        setTimeout(() => {
            if (eventSource.readyState === EventSource.CLOSED) {
                console.log('Attempting to reconnect...');
                initializeSSE();
            }
        }, 3000);
    };
}

function updateConnectionStatus(connected) {
    const status = document.getElementById('connectionStatus');
    if (connected) {
        status.textContent = '🟢 Connected';
        status.className = 'connection-status connected';
    } else {
        status.textContent = '🔴 Disconnected';
        status.className = 'connection-status disconnected';
    }
}

function handleSSEMessage(data) {
    console.log('📡 SSE Message received:', data.type, data);
    const messagesContainer = document.getElementById('chatMessages');
    const statusBar = document.getElementById('statusBar');
    
    switch(data.type) {
        case 'background_update':
            // Just update the status bar, don't add chat messages
            statusBar.innerHTML = `<span class="code-accent">Background:</span> ${data.data}`;
            statusBar.className = 'status';
            break;
            
        case 'message_received':
            // Just update status bar, don't add chat message
            statusBar.innerHTML = '🤖 <span class="code-accent">Assistant is processing...</span>';
            statusBar.className = 'status processing';
            break;
            
        case 'assistant_thinking':
            // Update status bar instead of adding chat message
            statusBar.innerHTML = `🤖 <span class="code-accent">${data.data}</span>`;
            statusBar.className = 'status processing';
            break;
            
        case 'assistant_progress':
            // Update status bar instead of adding chat message
            statusBar.innerHTML = `🔄 <span class="code-accent">${data.data}</span>`;
            statusBar.className = 'status processing';
            break;
            
        case 'assistant_response':
            addMessage('assistant', data.data, data.timestamp);
            setProcessing(false);
            statusBar.innerHTML = '';
            statusBar.className = 'status';
            break;
            
        case 'error':
            addMessage('system', `❌ ${data.data}`, data.timestamp);
            setProcessing(false);
            break;
            
        case 'tool_invoked':
            addTool(data.data);
            break;
            
        case 'heartbeat':
            // Keep connection alive
            break;
            
        default:
            console.log('Unknown message type:', data.type, data);
    }
}

function addMessage(type, content, timestamp) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    // Parse markdown for assistant messages using marked.js, keep plain text for user/system messages
    let processedContent;
    if (type === 'assistant' && typeof marked !== 'undefined') {
        try {
            processedContent = marked.parse(content);
        } catch (error) {
            console.warn('Markdown parsing failed, falling back to plain text:', error);
            processedContent = content.replace(/\n/g, '<br>');
        }
    } else {
        processedContent = content.replace(/\n/g, '<br>');
    }
    
    messageDiv.innerHTML = `
        <div>${processedContent}</div>
        <div class="timestamp">${timestamp || new Date().toLocaleTimeString()}</div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    
    // Auto-scroll to bottom with smooth behavior
    setTimeout(() => {
        messagesContainer.scrollTo({
            top: messagesContainer.scrollHeight,
            behavior: 'smooth'
        });
    }, 100);
}

function setProcessing(processing) {
    isProcessing = processing;
    const sendButton = document.getElementById('sendButton');
    const messageInput = document.getElementById('messageInput');
    
    sendButton.disabled = processing;
    messageInput.disabled = processing;
    
    if (processing) {
        sendButton.textContent = 'Processing...';
        messageInput.placeholder = 'Assistant is thinking...';
    } else {
        sendButton.textContent = 'Send';
        messageInput.placeholder = 'Type your message here...';
    }
}

async function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();
    
    if (!message || isProcessing) return;
    
    // Add user message to chat
    addMessage('user', message, new Date().toLocaleTimeString());
    messageInput.value = '';
    setProcessing(true);
    
    try {
        const response = await fetch('/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                timestamp: new Date().toISOString()
            })
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.detail || 'Failed to send message');
        }
        
        console.log('Message sent successfully:', result);
        
    } catch (error) {
        console.error('Error sending message:', error);
        addMessage('system', `❌ Error: ${error.message}`, new Date().toLocaleTimeString());
        setProcessing(false);
    }
}

async function endSession() {
    if (isProcessing) return;
    
    const endButton = document.getElementById('endSessionButton');
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    
    // Disable UI elements
    endButton.disabled = true;
    messageInput.disabled = true;
    sendButton.disabled = true;
    
    // Add system message
    addMessage('system', '🔚 Session ending...', new Date().toLocaleTimeString());
    
    try {
        const response = await fetch('/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: 'EXIT',
                timestamp: new Date().toISOString()
            })
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.detail || 'Failed to end session');
        }
        
        console.log('Session ended successfully:', result);
        addMessage('system', '✅ Session ended successfully', new Date().toLocaleTimeString());
        
    } catch (error) {
        console.error('Error ending session:', error);
        addMessage('system', `❌ Error ending session: ${error.message}`, new Date().toLocaleTimeString());
        
        // Re-enable UI elements on error
        endButton.disabled = false;
        messageInput.disabled = false;
        sendButton.disabled = false;
    }
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function addTool(toolData) {
    toolsData.push(toolData);
    updateToolsDisplay();
}

function updateToolsDisplay() {
    const toolsList = document.getElementById('toolsList');
    
    if (toolsData.length === 0) {
        toolsList.innerHTML = '<div class="no-tools-message">No tools have been invoked yet.</div>';
        return;
    }
    
    const toolsHTML = toolsData.map((tool, index) => {
        const statusClass = tool.success ? 'success' : 'error';
        const statusIcon = tool.success ? '✅' : '❌';
        
        return `
            <div class="tool-item ${statusClass}">
                <div class="tool-header" onclick="toggleToolDetails(${index})">
                    <div class="tool-header-left">
                        <span class="tool-name">${statusIcon} ${tool.name}</span>
                        <span class="tool-id">#${tool.identifier}</span>
                    </div>
                    <button class="toggle-button collapsed" id="toggle-${index}">Show Details</button>
                </div>
                <div class="tool-details collapsed" id="details-${index}">
                    <div class="tool-section">
                        <strong>Arguments:</strong>
                        <pre class="tool-args">${JSON.stringify(tool.arguments, null, 2)}</pre>
                    </div>
                    <div class="tool-section">
                        <strong>Result:</strong>
                        <pre class="tool-result">${tool.result}</pre>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    toolsList.innerHTML = toolsHTML;
}

function toggleToolDetails(index) {
    const details = document.getElementById(`details-${index}`);
    const toggle = document.getElementById(`toggle-${index}`);
    
    if (details.classList.contains('collapsed')) {
        // Expand
        details.classList.remove('collapsed');
        details.classList.add('expanded');
        toggle.classList.remove('collapsed');
        toggle.classList.add('expanded');
        toggle.textContent = 'Hide Details';
    } else {
        // Collapse
        details.classList.remove('expanded');
        details.classList.add('collapsed');
        toggle.classList.remove('expanded');
        toggle.classList.add('collapsed');
        toggle.textContent = 'Show Details';
    }
}

function clearTools() {
    toolsData = [];
    updateToolsDisplay();
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing Real-time AI Chat...');
    initializeSSE();
    
    // Focus on input
    document.getElementById('messageInput').focus();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (eventSource) {
        eventSource.close();
    }
});