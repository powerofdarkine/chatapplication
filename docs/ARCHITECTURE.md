# System Architecture

## High-Level Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                           Browser (Client)                            │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │   login.html    │  │   index.html     │  │    chat.js       │   │
│  │  (Auth Form)    │  │  (Chat UI)       │  │  (Application)   │   │
│  └─────────────────┘  └──────────────────┘  └──────────────────┘   │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTP :8080
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Proxy Server (start_proxy.py)                     │
│                            Port 8080                                  │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Routes all HTTP requests to Backend:9001                      │ │
│  │  - Forwards /api/* → Backend                                   │ │
│  │  - Forwards /static/* → Backend                                │ │
│  │  - Forwards /www/* → Backend                                   │ │
│  └────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTP :9001
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│               Backend/WebApp (start_sampleapp.py)                     │
│                            Port 9001                                  │
│  ┌──────────────┐  ┌───────────────┐  ┌───────────────────────┐    │
│  │  WeApRous    │  │   Tracker     │  │  P2P Daemon Manager   │    │
│  │  (HTTP)      │  │  (Registry)   │  │  (Per-User Sockets)   │    │
│  └──────────────┘  └───────────────┘  └───────────────────────┘    │
│         │                  │                      │                   │
│         │  /api/login      │  register_peer()     │  spawn daemon     │
│         │  /api/submit-info│  get_peers()         │  port 9100+       │
│         │  /api/get-list   │  heartbeat()         │                   │
│         │  /api/heartbeat  │  get_expired()       │                   │
│         │  /api/p2p-*      │  broadcast_event()   │                   │
└─────────┴──────────────────┴──────────────────────┴───────────────────┘
                                │
                                │ P2P TCP (CONNECT/ACCEPT handshake)
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    P2P Daemon (p2p_daemon.py)                         │
│                         Ports 9100-9199                               │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Per-User daemon listens on unique port (9100 + user_index)   │ │
│  │  - Server socket: Accept incoming CONNECT                      │ │
│  │  - Client socket: Initiate outgoing CONNECT                    │ │
│  │  - Message loop: CHAT/PING/PONG/CLOSE                         │ │
│  │  - Keepalive: PING every 10s, idle timeout 30s                │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Proxy Server (daemon/proxy.py)

**Purpose**: Reverse proxy to route HTTP requests

**Responsibilities**:
- Listen on port 8080
- Forward all requests to backend on port 9001
- Pass through headers (including X-Forwarded-For)
- Stream responses back to client

**Implementation**: Pure socket + threading (no frameworks)

### 2. Backend Server (daemon/weaprous.py + start_sampleapp.py)

**Purpose**: HTTP server for authentication, static files, and API endpoints

**Responsibilities**:
- Cookie-based session management
- Serve static files (HTML/CSS/JS)
- REST API for peer operations
- Manage P2P daemon lifecycle
- Queue messages from P2P daemons for browser polling

**Key Endpoints**:
- `POST /api/login` - Authenticate user, set cookie
- `POST /api/submit-info` - Register peer, spawn P2P daemon
- `GET /api/get-list` - Get list of online peers
- `POST /api/broadcast-peer` - Poll for peer events (join/leave/update). Note: current implementation responds immediately (short-poll);
- `POST /api/heartbeat` - Update last_seen, return expired peers
- `POST /api/p2p-request` - Send connection request
- `POST /api/p2p-accept` - Accept and establish P2P connection
- `POST /api/p2p-reject` - Reject connection request
- `GET /api/p2p-get-requests` - Poll pending connection requests
- `GET /api/p2p-get-responses` - Poll accept/reject responses
- `POST /api/p2p-send` - Send message via P2P daemon
- `POST /api/p2p-receive` - Poll incoming messages
- `POST /api/p2p-disconnect` - Close P2P connection
- `GET /api/p2p-status` - Get daemon status

**Implementation**: WeApRous custom framework (stdlib only)

### 3. Tracker (daemon/tracker.py)

**Purpose**: Centralized peer registry with health monitoring

**Responsibilities**:
- Register/unregister peers with IP, port, display name
- Track last_seen timestamp for each peer
- Mark peers offline after 45s timeout
- Broadcast events (peer-joined, peer-left, peer-updated)
- Queue events for long-polling clients
- Background cleanup thread (checks every 5s)

**Data Structure**:
```python
peers = {
  'user1': {
    'peer_id': 'user1',
    'ip': '127.0.0.1',
    'port': 9100,
    'display_name': 'User One',
    'status': 'ONLINE',
    'last_seen': 1730678400.0
  }
}
```

**Thread Safety**: RLock for all operations

### 4. P2P Daemon (daemon/p2p_daemon.py)

**Purpose**: Direct TCP connection manager for peer messaging

**Responsibilities**:
- Listen on assigned port (9100 + user_index)
- Handle incoming CONNECT handshakes (server role)
- Initiate outgoing CONNECT handshakes (client role)
- Maintain active connections map
- Send/receive JSON-per-line messages
- PING/PONG keepalive (10s interval)
- Idle timeout detection (30s)
- Graceful shutdown with CLOSE messages

**Connection States**:
1. HANDSHAKE: Exchange CONNECT/ACCEPT/REJECT
2. CONNECTED: Active messaging (CHAT/PING/PONG)
3. CLOSING: CLOSE sent, awaiting socket close
4. CLOSED: Connection terminated

**Message Types**:
- `CHAT`: User message with msg_id and body
- `PING`: Keepalive request
- `PONG`: Keepalive response
- `CLOSE`: Graceful termination (optional body)

**Threading**:
- Main thread: Server socket accept loop
- Per-connection thread: Message receive loop
- Keepalive thread: PING sender (global)

### 5. Frontend (static/js/chat.js)

**Purpose**: Browser-side chat application logic

**Responsibilities**:
- Render peer list
- Poll for events (/api/broadcast-peer every 3s)
- Poll for messages (/api/p2p-receive every 2s)
- Poll for connection requests (/api/p2p-get-requests every 2s)
- Poll for connection responses (/api/p2p-get-responses every 2s)
- Send heartbeat (/api/heartbeat every 15s)
- Handle user interactions (send message, end session, accept/reject requests)
- Update UI based on connection state

**State Management**:
```javascript
let currentUser = null;
let activePeer = null;
let connectedPeers = new Set();
let lastMessageTimestamp = 0;
let p2pRegistered = false;
let pendingConnectionRequest = null;
```

**UI Flow**:
1. Login → /login
2. Register P2P → /api/submit-info (daemon spawned)
3. Discover peers → /api/get-list + /api/broadcast-peer
4. Request connection → /api/p2p-request
5. Target sees modal → Accept → /api/p2p-accept
6. Requester detects connection → Enable chat input
7. Send messages → /api/p2p-send
8. Receive messages → /api/p2p-receive
9. End session → /api/p2p-send (CLOSE) → /api/p2p-disconnect

## Data Flow

### Scenario 1: User Login

```
Browser → Proxy:8080 → Backend:9001
POST /api/login {username, password}

Backend:
1. Validate credentials (hardcoded dict)
2. Generate session token (Base64 encoded)
3. Set-Cookie: session=token
4. Return 200 + redirect /

Browser:
1. Store cookie
2. Navigate to /
3. Load index.html
4. chat.js calls /api/user (authenticated)
5. Backend validates cookie, returns {username}
```

### Scenario 2: Peer Discovery

```
Browser (User A):
1. Calls /api/submit-info {display_name}

Backend:
1. Spawn P2P daemon on port 9100
2. tracker.register_peer('user1', ip, 9100, ...)
3. Broadcast peer-joined event to all other peers
4. Return {status: 'registered', port: 9100}

Browser (User B, polling /api/broadcast-peer):
1. Receives {type: 'peer-joined', peer: {...}}
2. Adds user1 to peer list
3. Renders peer item in UI
```

### Scenario 3: P2P Connection Establishment

```
Browser A → Proxy → Backend:
POST /api/p2p-request {to_peer: 'user2'}

Backend:
1. Store request in connection_requests['user2']
2. Return {status: 'request_sent'}

Browser B (polling /api/p2p-get-requests):
1. Receives [{from: 'user1', timestamp: ...}]
2. Show modal: "user1 wants to connect. Accept?"

User B clicks Accept:

Browser B → Proxy → Backend:
POST /api/p2p-accept {from_peer: 'user1'}

Backend:
1. Get user1 peer info (ip:127.0.0.1, port:9100)
2. daemon_B.connect_to_peer('127.0.0.1', 9100, 'user1', nonce)
3. Store response in connection_responses['user1']

P2P Layer:
Daemon B → Daemon A:
  "CONNECT user1 user2 nonce\n"

Daemon A (server role):
  Accept socket
  Send: "ACCEPT user2 user1 nonce\n"
  Mark connected

Daemon B (client role):
  Receive ACCEPT
  Mark connected
  Call on_peer_connected('user1')

Browser A (polling /api/p2p-status):
1. Detects active_connections contains 'user2'
2. Updates connectedPeers set
3. Enables chat input
```

### Scenario 4: P2P Messaging

```
Browser A:
1. User types "Hello"
2. Calls POST /api/p2p-send {to_peer: 'user2', message: 'Hello', type: 'CHAT'}

Backend A:
1. daemon_A.send_message('user2', 'Hello', 'CHAT')

P2P Layer:
Daemon A → Daemon B:
  {"type":"CHAT","from":"user1","to":"user2","msg_id":"uuid","body":"Hello","timestamp":123}\n

Daemon B:
1. _handle_message() parses JSON
2. Calls on_message('user1', 'user2', msg)

Backend B:
1. on_message callback queues message for user2

Browser B (polling /api/p2p-receive):
1. Receives [{type: 'CHAT', from: 'user1', body: 'Hello', ...}]
2. appendMessage('Hello', 'received', 'user1')
3. Plays notification sound
```

### Scenario 5: Session End

```
Browser A:
1. User clicks "End Session"
2. Confirms dialog
3. Calls POST /api/p2p-send {to_peer: 'user2', message: '__SESSION_ENDED__', type: 'CLOSE'}
4. Waits 800ms
5. Calls POST /api/p2p-disconnect {peer: 'user2'}

Backend A:
1. daemon_A.send_message('user2', '__SESSION_ENDED__', 'CLOSE')
2. daemon_A.disconnect_peer('user2')

P2P Layer:
Daemon A → Daemon B:
  {"type":"CLOSE","from":"user1","to":"user2","body":"__SESSION_ENDED__","timestamp":123}\n
  [socket close]

Daemon B:
1. _handle_message() receives CLOSE
2. Calls on_message('user1', 'user2', CLOSE_msg)
3. Marks connection closed

Backend B:
1. Queues CLOSE message for user2

Browser B (polling /api/p2p-receive):
1. Receives [{type: 'CLOSE', body: '__SESSION_ENDED__', ...}]
2. Calls handleRemoteSessionEnd('user1')
3. Shows system message: "user1 has ended the session"
4. Disables input
5. Changes button to "Close Chat"
6. Plays sound
```

### Scenario 6: Peer Timeout (Crash/Logout)

```
User A crashes (no graceful logout):

Tracker background thread (every 5s):
1. current_time - last_seen['user1'] > 45s
2. Mark user1 as offline
3. Broadcast peer-left event
4. DELETE peers['user1']

Browser B (polling /api/broadcast-peer):
1. Receives {type: 'peer-left', peer: {peer_id: 'user1'}}
2. Removes user1 from peer list
3. If chatting with user1:
   - Calls /api/p2p-disconnect
   - Shows "user1 has logged out or disconnected"
   - Disables input
   - Changes button to "Close Chat"
```

## Timing & Intervals

| Component | Action | Interval | Timeout |
|-----------|--------|----------|---------|
| Frontend | Poll peer events | 3s | short-poll (server responds immediately) |
| Frontend | Poll messages | 2s | N/A |
| Frontend | Poll connection requests | 2s | N/A |
| Frontend | Poll connection responses | 2s | N/A |
| Frontend | Send heartbeat | 15s | N/A |
| Frontend | Update P2P status | 5s | N/A |
| Backend | Tracker cleanup | 5s | N/A |
| Backend | Peer timeout threshold | N/A | 45s |
| P2P Daemon | PING keepalive | 10s | N/A |
| P2P Daemon | Idle timeout | N/A | 30s |
| P2P Daemon | Socket timeout | N/A | 1s (non-blocking) |

## Thread Model

### Backend Process
- **Main Thread**: HTTP server accept loop
- **Worker Threads**: One per HTTP request (blocking I/O)
- **Tracker Cleanup Thread**: Background peer timeout check
- **P2P Daemon Threads**: Per-user daemon (see below)

### P2P Daemon (per user)
- **Server Thread**: Accept incoming connections
- **Client Threads**: One per outgoing connection (handshake)
- **Message Loop Threads**: One per active connection (receive)
- **Keepalive Thread**: One per daemon (PING all connections)

### Thread Safety
- **Tracker**: RLock on all peer dict operations
- **P2P Daemon**: RLock on connections dict
- **Message Queues**: Lock on deque operations

## Security Considerations

1. **Authentication**: Cookie-based (Base64 encoded, not encrypted)
2. **Authorization**: Username from cookie used for all operations
3. **Input Validation**: Minimal (trust internal network)
4. **XSS Protection**: escapeHtml() in frontend
5. **DOS Protection**: None (academic project)

## Restrictions Compliance

- No external libraries (frontend or backend)
- No frameworks (Flask, Django, Express, React, Vue, Angular)
- No WebSocket or WebRTC
- Python stdlib only (socket, threading, time, json, os)
- Threading only (no asyncio)
- Pure TCP sockets for P2P
- In-memory state (no database)
- HTTP long-polling (no SSE, no WebSocket)
