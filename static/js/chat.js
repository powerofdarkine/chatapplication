let currentUser = null;
let activePeer = null;
let peers = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadCurrentUser();
    loadPeers();
    setInterval(loadPeers, 5000); // Refresh peers every 5 seconds
});

// Load current user info
async function loadCurrentUser() {
    try {
        const response = await fetch('/api/user');
        if (response.ok) {
            const data = await response.json();
            currentUser = data.username;
            document.getElementById('currentUser').textContent = `👤 ${currentUser}`;
        } else {
            // Not authenticated, redirect to login
            window.location.href = '/login.html';
        }
    } catch (error) {
        console.error('Error loading user:', error);
    }
}

// Load peer list
async function loadPeers() {
    try {
        const response = await fetch('/api/peers');
        if (response.ok) {
            const data = await response.json();
            peers = data.peers;
            renderPeerList();
        }
    } catch (error) {
        console.error('Error loading peers:', error);
    }
}

// Render peer list in sidebar
function renderPeerList() {
    const peerList = document.getElementById('peerList');
    
    if (peers.length === 0) {
        peerList.innerHTML = '<li class="peer-loading">No peers online</li>';
        return;
    }
    
    peerList.innerHTML = peers.map(peer => `
        <li class="peer-item ${activePeer === peer ? 'active' : ''}" onclick="selectPeer('${peer}')">
            <div class="peer-avatar">${peer.charAt(0).toUpperCase()}</div>
            <div class="peer-info">
                <div class="peer-name">${peer}</div>
                <div class="peer-status">● Online</div>
            </div>
        </li>
    `).join('');
}

// Select peer to chat
function selectPeer(peer) {
    activePeer = peer;
    document.getElementById('chatWelcome').style.display = 'none';
    document.getElementById('chatActive').style.display = 'flex';
    document.getElementById('activePeer').textContent = peer;
    
    renderPeerList(); // Re-render to update active state
    loadMessages(peer); // Load chat history (stub)
}

// Load messages for active peer (stub for Task 2)
function loadMessages(peer) {
    const container = document.getElementById('messagesContainer');
    container.innerHTML = `
        <div style="text-align: center; padding: 20px; color: #999;">
            <p>Chat history with ${peer}</p>
            <p><small>(P2P messaging will be implemented in Task 2)</small></p>
        </div>
    `;
}

// Send message
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message || !activePeer) return;
    
    try {
        const response = await fetch('/api/message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: `to=${activePeer}&message=${encodeURIComponent(message)}`
        });
        
        if (response.ok) {
            // Add message to UI
            appendMessage(message, 'sent');
            input.value = '';
        }
    } catch (error) {
        console.error('Error sending message:', error);
    }
}

// Append message to chat
function appendMessage(text, type) {
    const container = document.getElementById('messagesContainer');
    const time = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.innerHTML = `
        <div class="message-bubble">
            ${text}
            <div class="message-time">${time}</div>
        </div>
    `;
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

// Handle Enter key in message input
function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

// Refresh peers manually
function refreshPeers() {
    loadPeers();
}

// Logout
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        window.location.href = '/logout';
    }
}