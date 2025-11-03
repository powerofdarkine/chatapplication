let currentUser = null;
let activePeer = null;
let peers = [];
let connectedPeers = new Set();  // Set of peer IDs we're connected to
let lastEventTimestamp = 0;
let lastMessageTimestamp = 0;
let p2pRegistered = false;
let pendingConnectionRequest = null; // {from: peerId} when showing request modal

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('[Chat] Initializing...');
    
    loadCurrentUser();
    
    // Periodic tasks
    setInterval(loadPeers, 5000);                  // Refresh peers every 5s
    setInterval(pollPeerEvents, 3000);             // Poll peer events every 3s
    setInterval(pollMessages, 2000);               // Poll messages every 2s
    setInterval(pollConnectionRequests, 2000);     // Poll connection requests every 2s
    setInterval(pollConnectionResponses, 2000);    // Poll connection responses every 2s
    setInterval(sendHeartbeat, 15000);             // Send heartbeat every 15s
    setInterval(updateP2PStatus, 5000);            // Update P2P status every 5s
});

// Load current user info
async function loadCurrentUser() {
    try {
        const response = await fetch('/api/user');
        if (response.ok) {
            const data = await response.json();
            currentUser = data.username;
            document.getElementById('currentUser').textContent = `👤 ${currentUser}`;
            
            console.log('[Chat] Logged in as:', currentUser);
            
            // Register P2P after login
            await registerP2P();
            
            // Load initial peer list
            await loadPeers();
            
        } else {
            // Not authenticated, redirect to login
            window.location.href = '/login.html';
        }
    } catch (error) {
        console.error('[Chat] Error loading user:', error);
    }
}

// Register this peer with the tracker and start P2P daemon
async function registerP2P() {
    if (p2pRegistered) return;
    
    try {
        console.log('[Chat] Registering P2P...');
        
        const response = await fetch('/api/submit-info', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                display_name: currentUser,
                channels: ['general']
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            p2pRegistered = true;
            console.log('[Chat] P2P registered:', data);
            
            // Update status
            document.getElementById('p2pStatus').innerHTML = 
                `P2P: <span style="color: #28a745;">●</span> Port ${data.p2p_port}`;
        } else {
            console.error('[Chat] Failed to register P2P');
        }
    } catch (error) {
        console.error('[Chat] Error registering P2P:', error);
    }
}

// Load peer list
async function loadPeers() {
    try {
        const response = await fetch('/api/get-list');
        if (response.ok) {
            const data = await response.json();
            peers = data.peers || [];
            renderPeerList();
            
            // Update count
            document.getElementById('peerCount').textContent = `(${peers.length})`;
        }
    } catch (error) {
        console.error('[Chat] Error loading peers:', error);
    }
}

// Render peer list in sidebar
function renderPeerList() {
    const peerList = document.getElementById('peerList');
    
    if (peers.length === 0) {
        peerList.innerHTML = '<li class="peer-loading">No peers online</li>';
        return;
    }
    
    peerList.innerHTML = peers.map(peer => {
        const isConnected = connectedPeers.has(peer.peer_id);
        const isActive = activePeer === peer.peer_id;
        const statusClass = peer.status === 'ONLINE' ? '' : 'offline';
        
        return `
            <li class="peer-item ${isActive ? 'active' : ''}" onclick="selectPeer('${peer.peer_id}')">
                <div class="peer-avatar">${peer.display_name.charAt(0).toUpperCase()}</div>
                <div class="peer-info">
                    <div class="peer-name">
                        ${peer.display_name}
                        ${isConnected ? '<span class="badge">Connected</span>' : ''}
                    </div>
                    <div class="peer-status ${statusClass}">● ${peer.status}</div>
                </div>
            </li>
        `;
    }).join('');
}

// Select peer to chat
async function selectPeer(peerId) {
    activePeer = peerId;
    
    // Show chat window
    document.getElementById('chatWelcome').style.display = 'none';
    document.getElementById('chatActive').style.display = 'flex';
    document.getElementById('activePeer').textContent = peerId;
    
    // Clear messages
    document.getElementById('messagesContainer').innerHTML = '';
    
    // Reset "End Session" button to default
    const endBtn = document.getElementById('endSessionBtn');
    if (endBtn) {
        endBtn.textContent = 'End Session';
        endBtn.onclick = endChat; // Set to endChat function
    }
    
    // Re-render peer list to update active state
    renderPeerList();
    
    // Enable/disable input based on connection state
    const inputEl = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    
    // Check if already connected
    if (!connectedPeers.has(peerId)) {
        // Disable input while requesting connection
        inputEl.disabled = true;
        sendBtn.disabled = true;
        inputEl.placeholder = 'Sending connection request...';
        
        // Send connection request instead of connecting directly
        await requestConnection(peerId);
    } else {
        // Already connected - enable input
        updateConnectionStatus(true);
        inputEl.disabled = false;
        sendBtn.disabled = false;
        inputEl.placeholder = 'Type your message...';
    }
}

// Request connection to a peer (NEW)
async function requestConnection(peerId) {
    const inputEl = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    
    try {
        console.log(`[Chat] Requesting connection to: ${peerId}`);
        
        updateConnectionStatus(false, 'Sending request...');
        
        const response = await fetch('/api/p2p-request', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                to_peer: peerId
            })
        });
        
        if (response.ok) {
            console.log(`[Chat] Connection request sent to ${peerId}`);
            
            updateConnectionStatus(false, 'Waiting for peer to accept...');
            inputEl.placeholder = 'Waiting for peer to accept...';
            
            appendSystemMessage(`Connection request sent to ${peerId}. Waiting for acceptance...`);
        } else {
            const error = await response.json();
            console.error(`[Chat] Failed to send request to ${peerId}:`, error);
            
            updateConnectionStatus(false, 'Request failed');
            inputEl.placeholder = 'Connection request failed';
            
            appendSystemMessage(`Failed to send request: ${error.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('[Chat] Error requesting connection:', error);
        updateConnectionStatus(false, 'Request error');
        inputEl.placeholder = 'Connection request error';
    }
}

// Connect to a peer via P2P
async function connectToPeer(peerId) {
    const inputEl = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    
    try {
        console.log(`[Chat] Connecting to peer: ${peerId}`);
        
        updateConnectionStatus(false, 'Connecting...');
        
        const response = await fetch('/api/p2p-connect', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                to_peer: peerId
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            connectedPeers.add(peerId);
            
            console.log(`[Chat] Connected to ${peerId}`);
            
            updateConnectionStatus(true);
            renderPeerList();
            
            // Wait a bit for connection to stabilize before allowing messages
            await new Promise(resolve => setTimeout(resolve, 300));
            
            // Enable input after successful connection
            inputEl.disabled = false;
            sendBtn.disabled = false;
            inputEl.placeholder = 'Type your message...';
            inputEl.focus();
            
            appendSystemMessage(`P2P connection established with ${peerId}`);
        } else {
            const error = await response.json();
            console.error(`[Chat] Failed to connect to ${peerId}:`, error);
            
            updateConnectionStatus(false, 'Connection failed');
            
            // Keep input disabled
            inputEl.disabled = true;
            sendBtn.disabled = true;
            inputEl.placeholder = 'Connection failed - peer may be offline';
            
            appendSystemMessage(`Failed to connect: ${error.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('[Chat] Error connecting to peer:', error);
        updateConnectionStatus(false, 'Connection error');
        
        // Keep input disabled
        inputEl.disabled = true;
        sendBtn.disabled = true;
        inputEl.placeholder = 'Connection error';
    }
}

// Update connection status display
function updateConnectionStatus(connected, customText = null) {
    const statusEl = document.getElementById('connectionStatus');
    
    if (customText) {
        statusEl.textContent = `(${customText})`;
        statusEl.style.color = '#999';
    } else if (connected) {
        statusEl.textContent = '(P2P Connected)';
        statusEl.style.color = '#28a745';
    } else {
        statusEl.textContent = '(Not connected)';
        statusEl.style.color = '#999';
    }
}

// Send message
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message || !activePeer) return;
    
    // Check if connected
    if (!connectedPeers.has(activePeer)) {
        appendSystemMessage('Not connected to peer. Click their name to connect.');
        return;
    }
    
    try {
        const response = await fetch('/api/p2p-send', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                to_peer: activePeer,
                message: message
            })
        });
        
        if (response.ok) {
            // Add message to UI
            appendMessage(message, 'sent', currentUser);
            input.value = '';
        } else {
            const error = await response.json();
            console.error('[Chat] Failed to send message:', error);
            appendSystemMessage(`Failed to send: ${error.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('[Chat] Error sending message:', error);
        appendSystemMessage('Error sending message');
    }
}

// Append message to chat
function appendMessage(text, type, from = null) {
    const container = document.getElementById('messagesContainer');
    const time = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    let senderLabel = '';
    if (type === 'received' && from) {
        senderLabel = `<div style="font-size: 11px; color: #999; margin-bottom: 4px;">${from}</div>`;
    }
    
    messageDiv.innerHTML = `
        ${senderLabel}
        <div class="message-bubble">
            ${escapeHtml(text)}
            <div class="message-time">${time}</div>
        </div>
    `;
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

// Append system message
function appendSystemMessage(text, isImportant = false) {
    const container = document.getElementById('messagesContainer');
    const time = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    
    // Different styling for important messages (disconnects, session ends)
    const bgColor = isImportant ? '#ffe6e6' : '#f0f0f0';
    const textColor = isImportant ? '#d32f2f' : '#666';
    const fontWeight = isImportant ? 'bold' : 'normal';
    
    const messageDiv = document.createElement('div');
    messageDiv.style.cssText = 'text-align: center; padding: 10px; margin: 10px 0;';
    messageDiv.innerHTML = `
        <div style="display: inline-block; background: ${bgColor}; padding: 8px 14px; border-radius: 12px; font-size: 12px; color: ${textColor}; font-weight: ${fontWeight};">
            ${escapeHtml(text)} <span style="font-size: 10px; color: #999; font-weight: normal;">${time}</span>
        </div>
    `;
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Handle Enter key in message input
function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

// Poll for peer events (peer-joined, peer-left, peer-updated)
async function pollPeerEvents() {
    if (!p2pRegistered) return;
    
    try {
        const response = await fetch('/api/broadcast-peer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                peer_id: currentUser,
                since: lastEventTimestamp
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            const events = data.events || [];
            
            if (events.length > 0) {
                console.log(`[Chat] Received ${events.length} peer events`);
                
                events.forEach(event => {
                    handlePeerEvent(event);
                    lastEventTimestamp = Math.max(lastEventTimestamp, event.ts);
                });
                
                // Refresh peer list
                await loadPeers();
            }
        }
    } catch (error) {
        console.error('[Chat] Error polling peer events:', error);
    }
}

// Handle peer events
async function handlePeerEvent(event) {
    const peer = event.peer;
    
    console.log(`[Chat] Peer event: ${event.type} - ${peer.peer_id}`);
    
    if (event.type === 'peer-joined') {
        // New peer joined - show notification
        if (activePeer && activePeer !== peer.peer_id) {
            // Only show if we're in a different chat
            appendSystemMessage(`${peer.display_name} joined the network`);
        }
        
    } else if (event.type === 'peer-left') {
        // Peer left or timed out - MUST close P2P connection
        console.log(`[Chat] Peer left: ${peer.peer_id}, was connected: ${connectedPeers.has(peer.peer_id)}`);
        
        if (connectedPeers.has(peer.peer_id)) {
            // Disconnect P2P socket
            try {
                await fetch('/api/p2p-disconnect', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ peer: peer.peer_id })
                });
            } catch (e) {
                console.error(`[Chat] Error disconnecting from ${peer.peer_id}:`, e);
            }
            
            connectedPeers.delete(peer.peer_id);
            
            // Update active chat UI
            if (activePeer === peer.peer_id) {
                appendSystemMessage(`${peer.display_name} has logged out or disconnected`, true);
                updateConnectionStatus(false, 'Peer offline');
                
                // Disable input
                document.getElementById('sendBtn').disabled = true;
                document.getElementById('messageInput').disabled = true;
                document.getElementById('messageInput').placeholder = 'Peer has logged out...';
                
                // Change "End Session" button to "Close Chat"
                const endBtn = document.getElementById('endSessionBtn');
                if (endBtn) {
                    endBtn.textContent = 'Close Chat';
                    endBtn.onclick = function() {
                        // Just close the chat window
                        document.getElementById('chatActive').style.display = 'none';
                        document.getElementById('chatWelcome').style.display = 'flex';
                        activePeer = null;
                        renderPeerList();
                    };
                }
                
                // Play notification sound
                playNotificationSound();
            }
        } else if (activePeer === peer.peer_id) {
            // We're chatting with peer but not P2P connected yet (shouldn't happen but handle it)
            appendSystemMessage(`${peer.display_name} has logged out`, true);
            updateConnectionStatus(false, 'Peer offline');
            
            // Disable input and change button
            document.getElementById('sendBtn').disabled = true;
            document.getElementById('messageInput').disabled = true;
            document.getElementById('messageInput').placeholder = 'Peer has logged out...';
            
            const endBtn = document.getElementById('endSessionBtn');
            if (endBtn) {
                endBtn.textContent = 'Close Chat';
                endBtn.onclick = function() {
                    document.getElementById('chatActive').style.display = 'none';
                    document.getElementById('chatWelcome').style.display = 'flex';
                    activePeer = null;
                    renderPeerList();
                };
            }
            
            playNotificationSound();
        }
        
    } else if (event.type === 'peer-updated') {
        console.log(`[Chat] Peer updated: ${peer.display_name}`);
    }
}

// Poll for connection requests (NEW)
async function pollConnectionRequests() {
    if (!p2pRegistered) return;
    
    // Don't check if modal is already showing
    if (pendingConnectionRequest) return;
    
    try {
        const response = await fetch('/api/p2p-get-requests');
        
        if (response.ok) {
            const data = await response.json();
            const requests = data.requests || [];
            
            // Show modal for first pending request
            if (requests.length > 0) {
                const request = requests[0]; // Take first one
                showConnectionRequestModal(request.from);
            }
        }
    } catch (error) {
        console.error('[Chat] Error polling connection requests:', error);
    }
}

// Poll for connection responses (accept/reject notifications) (NEW)
async function pollConnectionResponses() {
    if (!p2pRegistered) return;
    
    try {
        const response = await fetch('/api/p2p-get-responses');
        
        if (response.ok) {
            const data = await response.json();
            const responses = data.responses || [];
            
            responses.forEach(resp => {
                if (resp.status === 'rejected') {
                    // Handle rejection
                    console.log(`[Chat] Connection rejected by ${resp.from}`);
                    
                    // If we're waiting for this peer, show rejection message
                    if (activePeer === resp.from) {
                        appendSystemMessage(`${resp.from} rejected your connection request`, true);
                        updateConnectionStatus(false, 'Request rejected');
                        
                        // Close chat window after 2 seconds
                        setTimeout(() => {
                            document.getElementById('chatActive').style.display = 'none';
                            document.getElementById('chatWelcome').style.display = 'flex';
                            activePeer = null;
                            renderPeerList();
                        }, 2000);
                        
                        playNotificationSound();
                    }
                } else if (resp.status === 'accepted') {
                    // Handle acceptance - connection will be detected by updateP2PStatus
                    console.log(`[Chat] Connection accepted by ${resp.from}`);
                }
            });
        }
    } catch (error) {
        console.error('[Chat] Error polling connection responses:', error);
    }
}

// Show connection request modal (NEW)
function showConnectionRequestModal(fromPeer) {
    pendingConnectionRequest = { from: fromPeer };
    
    const modal = document.getElementById('connectionRequestModal');
    const message = document.getElementById('connectionRequestMessage');
    const acceptBtn = document.getElementById('acceptRequestBtn');
    const rejectBtn = document.getElementById('rejectRequestBtn');
    
    message.textContent = `${fromPeer} wants to connect with you. Accept?`;
    
    // Set up buttons
    acceptBtn.onclick = () => acceptConnectionRequest(fromPeer);
    rejectBtn.onclick = () => rejectConnectionRequest(fromPeer);
    
    // Show modal
    modal.style.display = 'flex';
    
    console.log(`[Chat] Showing connection request from ${fromPeer}`);
}

// Accept connection request (NEW)
async function acceptConnectionRequest(fromPeer) {
    const modal = document.getElementById('connectionRequestModal');
    const message = document.getElementById('connectionRequestMessage');
    
    message.textContent = `Establishing connection with ${fromPeer}...`;
    
    try {
        const response = await fetch('/api/p2p-accept', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                from_peer: fromPeer
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            connectedPeers.add(fromPeer);
            
            console.log(`[Chat] Connection accepted from ${fromPeer}`);
            
            // Hide modal
            modal.style.display = 'none';
            pendingConnectionRequest = null;
            
            // If we're chatting with this peer, enable input
            if (activePeer === fromPeer) {
                updateConnectionStatus(true);
                document.getElementById('messageInput').disabled = false;
                document.getElementById('sendBtn').disabled = false;
                document.getElementById('messageInput').placeholder = 'Type your message...';
                appendSystemMessage(`P2P connection established with ${fromPeer}`);
            }
            
            // Update peer list
            renderPeerList();
            
            // Play sound
            playNotificationSound();
        } else {
            const error = await response.json();
            console.error(`[Chat] Failed to accept connection:`, error);
            alert(`Failed to establish connection: ${error.error}`);
            
            modal.style.display = 'none';
            pendingConnectionRequest = null;
        }
    } catch (error) {
        console.error('[Chat] Error accepting connection:', error);
        alert('Error establishing connection');
        
        modal.style.display = 'none';
        pendingConnectionRequest = null;
    }
}

// Reject connection request (NEW)
async function rejectConnectionRequest(fromPeer) {
    const modal = document.getElementById('connectionRequestModal');
    
    try {
        await fetch('/api/p2p-reject', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                from_peer: fromPeer
            })
        });
        
        console.log(`[Chat] Connection request from ${fromPeer} rejected`);
    } catch (error) {
        console.error('[Chat] Error rejecting connection:', error);
    }
    
    // Hide modal
    modal.style.display = 'none';
    pendingConnectionRequest = null;
}

// Poll for incoming P2P messages
async function pollMessages() {
    if (!p2pRegistered) return;
    
    try {
        const response = await fetch('/api/p2p-receive', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                since: lastMessageTimestamp
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            const messages = data.messages || [];
            
            messages.forEach(msg => {
                // Handle CLOSE message (session ended by remote peer)
                if (msg.type === 'CLOSE') {
                    console.log(`[Chat] Received CLOSE from ${msg.from}`);
                    
                    // Check if it's a session end notification
                    if (msg.body === '__SESSION_ENDED__' || !msg.body) {
                        handleRemoteSessionEnd(msg.from);
                    }
                    
                    lastMessageTimestamp = Math.max(lastMessageTimestamp, msg.timestamp);
                    return;
                }
                
                // Handle normal CHAT message
                if (msg.type === 'CHAT') {
                    // Show message if from active peer
                    if (activePeer && msg.from === activePeer) {
                        appendMessage(msg.body, 'received', msg.from);
                        playNotificationSound();
                    }
                    // Or if this peer sent us a message, could open chat automatically
                    else if (!activePeer) {
                        // Could show notification badge here
                        console.log(`[Chat] Message from ${msg.from} (not in active chat)`);
                    }
                }
                
                lastMessageTimestamp = Math.max(lastMessageTimestamp, msg.timestamp);
            });
        }
    } catch (error) {
        console.error('[Chat] Error polling messages:', error);
    }
}

// Handle when remote peer ends session
async function handleRemoteSessionEnd(peerId) {
    console.log(`[Chat] Remote peer ${peerId} ended session`);
    
    // Remove from connected peers
    if (connectedPeers.has(peerId)) {
        connectedPeers.delete(peerId);
        
        // Disconnect our side too
        try {
            await fetch('/api/p2p-disconnect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ peer: peerId })
            });
        } catch (e) {
            console.error('[Chat] Error disconnecting:', e);
        }
    }
    
    // If we're currently chatting with this peer, update UI
    if (activePeer === peerId) {
        // Show important system message
        appendSystemMessage(`${peerId} has ended the session`, true);
        
        // Update connection status
        updateConnectionStatus(false, 'Session ended by peer');
        
        // Disable input
        document.getElementById('sendBtn').disabled = true;
        document.getElementById('messageInput').disabled = true;
        document.getElementById('messageInput').placeholder = 'Session ended by peer';
        
        // Change "End Session" button to "Close Chat"
        const endBtn = document.getElementById('endSessionBtn');
        if (endBtn) {
            endBtn.textContent = 'Close Chat';
            endBtn.onclick = function() {
                // Just close the chat window without notifying peer
                document.getElementById('chatActive').style.display = 'none';
                document.getElementById('chatWelcome').style.display = 'flex';
                activePeer = null;
                renderPeerList();
            };
        }
        
        // Optional: Play alert sound
        playNotificationSound();
    }
    
    // Update peer list
    renderPeerList();
}

// Send heartbeat to tracker
async function sendHeartbeat() {
    if (!p2pRegistered) return;
    
    try {
        const response = await fetch('/api/heartbeat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                peer_id: currentUser,
                ts: Date.now()
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            const expired = data.expired_peers || [];
            
            if (expired.length > 0) {
                console.log(`[Chat] Server reported expired peers:`, expired);
                
                // Handle expired peers - CRITICAL: Close P2P sessions
                expired.forEach(async peerId => {
                    if (connectedPeers.has(peerId)) {
                        console.log(`[Chat] Closing P2P connection to expired peer: ${peerId}`);
                        
                        // Disconnect from P2P daemon
                        try {
                            await fetch('/api/p2p-disconnect', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({ peer: peerId })
                            });
                        } catch (e) {
                            console.error(`[Chat] Error disconnecting from ${peerId}:`, e);
                        }
                        
                        connectedPeers.delete(peerId);
                        
                        // Update UI if this is active chat
                        if (activePeer === peerId) {
                            appendSystemMessage(`Connection lost: ${peerId} went offline`);
                            updateConnectionStatus(false, 'Peer offline');
                            
                            // Disable send button
                            document.getElementById('sendBtn').disabled = true;
                            document.getElementById('messageInput').disabled = true;
                            document.getElementById('messageInput').placeholder = 'Peer is offline...';
                        }
                    }
                });
                
                // Refresh peer list to show offline status
                await loadPeers();
            }
        }
    } catch (error) {
        console.error('[Chat] Error sending heartbeat:', error);
    }
}

// Update P2P status display
async function updateP2PStatus() {
    if (!p2pRegistered) return;
    
    try {
        const response = await fetch('/api/p2p-status');
        
        if (response.ok) {
            const data = await response.json();
            
            if (data.daemon_running) {
                const statusEl = document.getElementById('p2pStatus');
                const connectionCount = data.active_connections ? data.active_connections.length : 0;
                
                statusEl.innerHTML = 
                    `P2P: <span style="color: #28a745;">●</span> Port ${data.port} | ${connectionCount} active`;
                
                // Check for new connections
                const oldConnected = new Set(connectedPeers);
                const newConnections = data.active_connections || [];
                
                // Update connected peers set
                connectedPeers = new Set(newConnections);
                
                // Detect newly established connections
                for (const peerId of newConnections) {
                    if (!oldConnected.has(peerId)) {
                        // New connection detected!
                        console.log(`[Chat] New P2P connection detected: ${peerId}`);
                        onConnectionEstablished(peerId);
                    }
                }
                
                renderPeerList();
            }
        }
    } catch (error) {
        console.error('[Chat] Error updating P2P status:', error);
    }
}

// Called when a new P2P connection is established (NEW)
function onConnectionEstablished(peerId) {
    console.log(`[Chat] Connection established with ${peerId}`);
    
    // If we're currently chatting with this peer, enable input
    if (activePeer === peerId) {
        const inputEl = document.getElementById('messageInput');
        const sendBtn = document.getElementById('sendBtn');
        
        updateConnectionStatus(true);
        inputEl.disabled = false;
        sendBtn.disabled = false;
        inputEl.placeholder = 'Type your message...';
        inputEl.focus();
        
        appendSystemMessage(`✅ P2P connection established with ${peerId}`);
        playNotificationSound();
    }
}

// End chat session
async function endChat() {
    if (!activePeer) return;
    
    if (confirm(`End chat session with ${activePeer}?`)) {
        try {
            const peerToEnd = activePeer;
            
            // IMPORTANT: Send "end session" message to peer BEFORE disconnecting
            if (connectedPeers.has(peerToEnd)) {
                // Send special CLOSE message to notify peer
                try {
                    await fetch('/api/p2p-send', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            to_peer: peerToEnd,
                            message: '__SESSION_ENDED__',  // Special marker
                            type: 'CLOSE'
                        })
                    });
                    
                    console.log(`[Chat] Sent end session notification to ${peerToEnd}`);
                } catch (e) {
                    console.error('[Chat] Failed to notify peer:', e);
                }
                
                // Wait longer for message to be sent and received
                await new Promise(resolve => setTimeout(resolve, 800));
                
                // Now disconnect
                await fetch('/api/p2p-disconnect', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        peer: peerToEnd
                    })
                });
                
                connectedPeers.delete(peerToEnd);
            }
            
            // Close chat window
            document.getElementById('chatActive').style.display = 'none';
            document.getElementById('chatWelcome').style.display = 'flex';
            
            activePeer = null;
            renderPeerList();
            
            console.log('[Chat] Session ended');
            
        } catch (error) {
            console.error('[Chat] Error ending session:', error);
        }
    }
}

// Play notification sound (optional)
function playNotificationSound() {
    // Simple beep using Web Audio API
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.value = 800;
        oscillator.type = 'sine';
        
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);
        
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.1);
    } catch (e) {
        // Silently fail if audio not supported
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