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
    } else if (tabName === 'attachments') {
        document.getElementById('attachmentsTab').classList.add('active');
    } else if (tabName === 'tools') {
        document.getElementById('toolsTab').classList.add('active');
    }
    
    // Add active class to clicked tab
    event.target.classList.add('active');
    currentTab = tabName;
}

let keepSSEAlive = true; // new global flag

// Initialize SSE connection
function initializeSSE() {

    if (!keepSSEAlive) return; 

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
        status.innerHTML = '<i class="fa-solid fa-circle" style="color:green;"></i> Connected';
        status.className = 'connection-status connected';
    } else {
        status.innerHTML = '<i class="fa-solid fa-circle" style="color:red;"></i> Disconnected';
        status.className = 'connection-status disconnected';
    }
}

function handleSSEMessage(data) {
    console.log('SSE Message:', data.type);
    const messagesContainer = document.getElementById('chatMessages');
    const statusBar = document.getElementById('statusBar');
    const endButton = document.getElementById('endSessionButton');
    
    switch(data.type) {
        case 'background_update':
            // Just update the status bar, don't add chat messages
            statusBar.innerHTML = `<div class="status-inner"><span class="code-accent">Background:</span> ${data.data}</div>`;
            statusBar.className = 'status';
            break;
            
        case 'message_received':
            // Just update status bar, don't add chat message
            statusBar.innerHTML = '<div class="status-inner"><i class="fa-solid fa-robot"></i> <span class="code-accent">Assistant is processing...</span></div>';
            statusBar.className = 'status processing';
            break;
            
        case 'assistant_thinking':
            // Update status bar instead of adding chat message
            statusBar.innerHTML = `<div class="status-inner"><i class="fa-solid fa-robot"></i> <span class="code-accent">${data.data}</span></div>`;
            statusBar.className = 'status processing';
            break;
            
        case 'assistant_progress':
            // Update status bar instead of adding chat message
            statusBar.innerHTML = `<div class="status-inner"><i class="fa-solid fa-rotate"></i> <span class="code-accent">${data.data}</span></div>`;
            statusBar.className = 'status processing';
            break;
            
        case 'assistant_response':
            addMessage('assistant', data.data, data.timestamp);
            setProcessing(false);
            endButton.disabled = false;
            statusBar.innerHTML = '';
            statusBar.className = 'status';
            break;
            
        case 'error':
            addMessage('system', `<i class="fa-solid fa-circle-xmark" style="color:red;"></i> ${data.data}`, data.timestamp);
            setProcessing(false);
            endButton.disabled = false;
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

    let avatarHtml = '';
    if (type === 'assistant') {
        avatarHtml = '<span class="avatar avatar-assistant"><i class="fa-solid fa-robot"></i></span>';
    }

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
        <div class="message-row" style="display: flex; gap: 10px; align-items: baseline;">
            ${avatarHtml}
            <div class="message-content">
                <div>${processedContent}</div>
                <div class="timestamp">${timestamp || new Date().toLocaleTimeString()}</div>
            </div>
        </div>
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
    const uploadButton = document.getElementById('uploadButton');
    
    sendButton.disabled = processing;
    messageInput.disabled = processing;
    uploadButton.disabled = processing;
    
    if (processing) {
        sendButton.innerHTML = '<i class="fa-solid fa-clock"></i>';
        messageInput.placeholder = 'Assistant is thinking...';
    } else {
        sendButton.textContent = 'Send';
        messageInput.placeholder = 'Type your message here...';
    }
}

async function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();
    const endButton = document.getElementById('endSessionButton');

    // Only send unsent attachments
    const unsentAttachments = attachments.filter(att => !att.sent);
    
    if ((!message && unsentAttachments.length === 0) || isProcessing) return;
    
    // Prepare message display with attachments info
    let displayMessage = message;
    if (unsentAttachments.length > 0) {
        const attachmentList = unsentAttachments.map(att => {
            const icon = getAttachmentIcon(att);
            return `${icon} ${att.name}`;
        }).join(', ');
        displayMessage = message + (message ? '\n\n' : '') + `📎 Attachments: ${attachmentList}`;
    }
    
    // Add user message to chat
    addMessage('user', displayMessage, new Date().toLocaleTimeString());
    messageInput.value = '';
    
    // Reset textarea height to original size
    messageInput.style.height = '40px';
    
    setProcessing(true);
    endButton.disabled=true;
    
    try {
        // Prepare attachments data for sending (only unsent attachments)
        const attachmentsData = await Promise.all(unsentAttachments.map(async (att) => {
            if (att.type === 'file') {
                // For files, we'll send as base64
                const base64 = await fileToBase64(att.data);
                return {
                    type: 'file',
                    name: att.name,
                    data: base64,
                    mimeType: att.mimeType,
                    size: att.size
                };
            } else {
                // For URLs, just send the URL
                return {
                    type: 'url',
                    url: att.data
                };
            }
        }));
        
        console.log('Sending message with attachments:', {
            content: message,
            attachmentsCount: attachmentsData.length,
            attachments: attachmentsData
        });
        
        const response = await fetch('/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                content: message,  // Changed from 'message' to 'content' to match HILMessage
                timestamp: new Date().toISOString(),
                attachments: attachmentsData
            })
        });
        
        if (!response.ok) {
            let errorMessage = 'Failed to send message';
            try {
                const errorData = await response.json();
                console.error('Server error response:', errorData);
                // FastAPI validation errors are in .detail
                if (errorData.detail) {
                    if (typeof errorData.detail === 'string') {
                        errorMessage = errorData.detail;
                    } else if (Array.isArray(errorData.detail)) {
                        // FastAPI validation errors are arrays
                        errorMessage = errorData.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join(', ');
                    } else {
                        errorMessage = JSON.stringify(errorData.detail);
                    }
                }
            } catch (e) {
                console.error('Could not parse error response:', e);
                errorMessage = `Server error: ${response.status} ${response.statusText}`;
            }
            throw new Error(errorMessage);
        }
        
        const result = await response.json();
        console.log('Message sent successfully:', result);
        
        // Mark unsent attachments as sent
        attachments.forEach(att => {
            if (!att.sent) {
                att.sent = true;
            }
        });
        updateAttachmentsDisplay();
        
    } catch (error) {
        console.error('Error sending message:', error);
        addMessage('system', `<i class="fa-solid fa-circle-xmark" style="color:red;"></i> Error: ${error.message}`, new Date().toLocaleTimeString());
        setProcessing(false);
        endButton.disabled = false;
    }
}

// Helper function to convert file to base64
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result);
        reader.onerror = error => reject(error);
    });
}

async function endSession(event) {
    keepSSEAlive = false;
    updateConnectionStatus(false);
    event.preventDefault();
    
    const endButton = document.getElementById('endSessionButton');
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    
    if (isProcessing) return;
    
    if (eventSource) {
        eventSource.close();
    }

    
    // Disable UI elements
    endButton.disabled = true;
    messageInput.disabled = true;
    sendButton.disabled = true;
    
    // Add system message
    addMessage('system', '🔚 Session ending...', new Date().toLocaleTimeString());
    
    try {
        const response = await fetch('/shutdown', { method: 'POST' });
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.detail || 'Failed to shut down server');
        }
        
        console.log('Shutdown triggered successfully:', result);
        addMessage('system', '<i class="fa-solid fa-circle-check" style="color: green;"></i> Server shutting down', new Date().toLocaleTimeString());
        
    } catch (error) {
        console.error('Error shutting down:', error);
        addMessage('system', `<i class="fa-solid fa-circle-xmark" style="color:red;"></i> Error shutting down: ${error.message}`, new Date().toLocaleTimeString());
        
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
    // Allow Shift+Enter for new lines - no action needed, default behavior
}

function autoResize(textarea) {
    // Reset height to auto to get the correct scrollHeight
    textarea.style.height = 'auto';
    
    // Calculate the new height based on content
    const newHeight = Math.min(textarea.scrollHeight, 320); // Max height of 320px (about 12 lines)

    // Set the new height
    textarea.style.height = (newHeight + 5) + 'px';

    // Ensure minimum height
    if (newHeight < 30) {
        textarea.style.height = '30px';
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
        const statusIcon = tool.success ? '<i class="fa-solid fa-circle-check" style="color: green;"></i>' : '<i class="fa-solid fa-circle-xmark" style="color:red;"></i>';
        
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
    // Focus on input and set initial height
    const messageInput = document.getElementById('messageInput');
    messageInput.focus();
    autoResize(messageInput); // Set initial height
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (eventSource) {
        eventSource.close();
    }
});

// Upload functionality
let attachments = []; // Array to store attachments {type: 'file'|'url', name: string, data: File|string, sent: boolean}

function toggleUploadModal() {
    const modal = document.getElementById('uploadModal');
    const urlInput = document.getElementById('urlInput');
    
    if (modal.style.display === 'none' || modal.style.display === '') {
        modal.style.display = 'flex';
        urlInput.value = ''; // Clear URL input when opening
    } else {
        modal.style.display = 'none';
    }
}

function handleFileSelect(event) {
    const files = event.target.files;
    
    for (let file of files) {
        attachments.push({
            type: 'file',
            name: file.name,
            data: file,
            size: file.size,
            mimeType: file.type,
            sent: false
        });
    }
    
    updateAttachmentsDisplay();
    toggleUploadModal();
    
    // Reset file input so same file can be selected again
    event.target.value = '';
}

function handleUrlSubmit() {
    const urlInput = document.getElementById('urlInput');
    const url = urlInput.value.trim();
    
    if (!url) return;
    
    // Basic URL validation
    try {
        new URL(url);
        
        attachments.push({
            type: 'url',
            name: url,
            data: url,
            sent: false
        });
        
        updateAttachmentsDisplay();
        toggleUploadModal();
    } catch (e) {
        alert('Please enter a valid URL');
    }
}

function handleUrlKeyPress(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        handleUrlSubmit();
    }
}

function removeAttachment(index) {
    attachments.splice(index, 1);
    updateAttachmentsDisplay();
}

function updateAttachmentsDisplay() {
    const attachmentsList = document.getElementById('attachmentsList');
    const attachmentsTabButton = document.getElementById('attachmentsTabButton');
    
    // Always show the Attachments tab if there are any attachments (sent or unsent)
    if (attachments.length === 0) {
        attachmentsTabButton.style.display = 'none';
        attachmentsList.innerHTML = '<div class="no-tools-message">No attachments yet.</div>';
        return;
    }
    
    attachmentsTabButton.style.display = 'block';
    
    const attachmentsHTML = attachments.map((attachment, index) => {
        let icon = 'fa-file';
        let statusIcon = attachment.sent 
            ? '<i class="fa-solid fa-circle-check" style="color: #00ff88;"></i>' 
            : '<i class="fa-solid fa-clock" style="color: #ffd700;"></i>';
        
        if (attachment.type === 'url') {
            icon = 'fa-link';
        } else if (attachment.mimeType) {
            if (attachment.mimeType.startsWith('image/')) icon = 'fa-image';
            else if (attachment.mimeType.startsWith('video/')) icon = 'fa-video';
            else if (attachment.mimeType.startsWith('audio/')) icon = 'fa-file-audio';
            else if (attachment.mimeType === 'application/pdf') icon = 'fa-file-pdf';
        }
        
        const removeButton = attachment.sent 
            ? `<button class="remove-attachment-button" disabled title="Already sent">
                   <i class="fa-solid fa-check"></i> Sent
               </button>`
            : `<button class="remove-attachment-button" onclick="removeAttachment(${index})" title="Remove attachment">
                   <i class="fa-solid fa-trash"></i> Remove
               </button>`;
        
        return `
            <div class="tool-item ${attachment.sent ? 'success' : ''}">
                <div class="attachment-header">
                    <div class="tool-header-left">
                        <span class="tool-name">${statusIcon} <i class="fa-solid ${icon}"></i> ${attachment.name}</span>
                        ${attachment.type === 'file' ? `<span class="tool-id">${formatFileSize(attachment.size)}</span>` : '<span class="tool-id">URL</span>'}
                    </div>
                    ${removeButton}
                </div>
            </div>
        `;
    }).join('');
    
    attachmentsList.innerHTML = attachmentsHTML;
}

function toggleAttachmentDetails(index) {
    const details = document.getElementById(`attachment-details-${index}`);
    const toggle = document.getElementById(`attachment-toggle-${index}`);
    
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

function clearAttachments() {
    attachments = [];
    updateAttachmentsDisplay();
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function getAttachmentIcon(attachment) {
    if (attachment.type === 'url') {
        return '🔗';
    }
    
    if (attachment.mimeType) {
        if (attachment.mimeType.startsWith('image/')) return '🖼️';
        if (attachment.mimeType.startsWith('video/')) return '🎥';
        if (attachment.mimeType.startsWith('audio/')) return '🎵';
        if (attachment.mimeType === 'application/pdf') return '📄';
    }
    
    return '📎';
}

// Close modal when clicking outside
document.addEventListener('click', function(event) {
    const modal = document.getElementById('uploadModal');
    const uploadButton = document.getElementById('uploadButton');
    
    if (modal && modal.style.display === 'flex') {
        if (event.target === modal) {
            toggleUploadModal();
        }
    }
});
