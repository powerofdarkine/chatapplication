# CO3094 Hybrid P2P Chat System

## Overview

This project implements a **hybrid P2P chat system** that combines:
- **HTTP Client-Server**: Authentication, peer discovery, session management
- **Direct P2P TCP**: Real-time messaging between peers without server relay

The system strictly adheres to CO3094 course restrictions: **no external libraries**, pure Python standard library only, vanilla HTML/CSS/JS with no frameworks.

### Key Features ✨
- Cookie-based authentication with session management
- Real-time peer discovery via HTTP polling (short-poll; frontend polls the backend periodically)
- Request/accept pattern for P2P connection establishment
- Direct TCP messaging between peers (no server relay)
- Connection health monitoring with PING/PONG keepalive
- Graceful session termination with bidirectional notification
- Automatic offline peer detection (45s timeout)
- Rejection notification system
- Fixed footer overlap in chat UI
- Session end notification to peer

### Architecture Components

| Component | Port | Purpose |
|-----------|------|---------|
| **Proxy Server** | 8080 | Routes HTTP requests to backend, load balancing |
| **Backend/WebApp** | 9001 | Authentication, peer registry, static files, P2P management |
| **P2P Daemons** | 9100-9199 | One TCP daemon per user for direct peer messaging |

**Data Flow:**
```
Browser → Proxy:8080 → Backend:9001 → P2P Daemon:910x ⟷ P2P Daemon:910y
```

### Communication Flow Diagram

```
┌─────────────┐                    ┌─────────────┐
│  Browser A  │                    │  Browser B  │
│  (user1)    │                    │  (user2)    │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │ HTTP (polling)                   │ HTTP (polling)
       │                                  │
       ▼                                  ▼
┌─────────────────────────────────────────────────┐
│         Proxy Server (Port 8080)                │
│         Routes all HTTP to Backend              │
└─────────────────┬───────────────────────────────┘
                  │
                  │ HTTP Forward
                  ▼
┌─────────────────────────────────────────────────┐
│      Backend/WebApp Server (Port 9001)          │
│  - Authentication & Session Management          │
│  - Peer Registry (Tracker)                      │
│  - P2P Daemon Manager                           │
│  - Static File Serving                          │
└───────────┬─────────────────────┬───────────────┘
            │                     │
            │ Manages             │ Manages
            ▼                     ▼
    ┌──────────────┐      ┌──────────────┐
    │ P2P Daemon A │◄────►│ P2P Daemon B │
    │  Port 9100   │ TCP  │  Port 9101   │
    │   (user1)    │Direct│   (user2)    │
    └──────────────┘      └──────────────┘
          ▲                      ▲
          │ Callbacks            │ Callbacks
          │ (on_message)         │ (on_message)
          └──────────────────────┘
```

**Key Points:**
- HTTP: Browser ↔ Proxy ↔ Backend (auth, peer discovery, events)
- TCP: P2P Daemon A ↔ P2P Daemon B (direct messaging, no server relay)
- Backend creates one P2P daemon per logged-in user
- P2P daemons call backend callbacks to queue messages for browser polling

## Quick Start

### Prerequisites
- Python 3.8 or higher
- No external dependencies required (stdlib only)

### Running the System

**Option 1: All-in-one (Windows)**
```bash
start_all.bat
```

**Option 2: Manual start**

Terminal 1 - Start Proxy:
```bash
python start_proxy.py
```

Terminal 2 - Start Backend/WebApp:
```bash
python start_sampleapp.py
```

Access the application at: `http://localhost:8080`

### Default Credentials
- User 1: `user1` / `pass123`
- User 2: `user2` / `pass456`
- Admin: `admin` / `password`

### How to Use the Chat System 💬

**Step 1: Start the System**
```bash
start_all.bat  # Windows
# Wait 5 seconds for all services to start
```

**Step 2: Open Two Browser Windows**
- Browser A (or normal window): `http://localhost:8080`
- Browser B (or incognito window): `http://localhost:8080`

**Step 3: Login**
- Browser A: Login as `user1` / `pass123`
- Browser B: Login as `user2` / `pass456`

**Step 4: Initiate Chat**
- In Browser A: Click on "user2" in the peer list
- System automatically sends connection request to user2

**Step 5: Accept Connection**
- In Browser B: A popup appears asking to accept/reject
- Click "Accept" button

**Step 6: Start Chatting**
- Both browsers now have active chat windows
- Type message in input field and press Enter or click Send
- Messages appear in real-time (via P2P TCP connection)

**Step 7: End Session**
- Click "End Session" button to close the chat
- Other peer will receive notification: "user1 has ended the session"

**Tip**: You can test rejection by clicking "Reject" in Step 5. The requester will see a rejection message and the chat window will close automatically.

## Project Structure

### Core Startup Files

| File | Purpose | Key Features |
|------|---------|--------------|
| `start_all.bat` | Windows batch launcher | Starts proxy + backend automatically in separate windows |
| `start_proxy.py` | Proxy server entry point | Listens on port 8080, forwards to backend:9001 |
| `start_sampleapp.py` | Backend/WebApp server | Handles auth, peer registry, manages P2P daemons |

### daemon/ - Core Backend Components

| File | Purpose | Key Features |
|------|---------|--------------|
| `backend.py` | Base HTTP server | Multi-threaded TCP server, handles client connections |
| `weaprous.py` | Lightweight web framework | Route registration, hook system, static file serving |
| `httpadapter.py` | HTTP request/response handler | Parses requests, builds responses, executes route hooks |
| `request.py` | HTTP request parser | Parses headers, body, query strings, cookies |
| `response.py` | HTTP response builder | Builds HTTP responses with headers, cookies, redirects |
| `proxy.py` | Reverse proxy | Round-robin load balancing, forwards HTTP to backend |
| `p2p_daemon.py` | P2P TCP daemon | Manages P2P connections, handshake, PING/PONG keepalive |
| `tracker.py` | Peer tracker | Registers peers, health monitoring, timeout detection |
| `dictionary.py` | In-memory data structure | Thread-safe peer registry |
| `utils.py` | Utility functions | Helper functions (cookie parsing, URL decoding, etc.) |

**P2P Daemon Key Features:**
- TCP handshake protocol: CONNECT → ACCEPT/REJECT
- Message types: CHAT, PING, PONG, CLOSE
- Keepalive: 10s PING, 30s idle timeout
- Thread-safe with RLock on all shared state
- Callback system for on_message events

### static/ - Frontend Assets

#### CSS Styling
| File | Purpose | Key Features |
|------|---------|--------------|
| `static/css/login.css` | Login page styles | Centered form, gradient background, responsive |
| `static/css/chat.css` | Chat UI styles | Flexbox layout, message bubbles, scrollable containers |

**Chat.css Notable Features:**
- Fixed footer with `min-height: 0` to prevent overlap (Bug #2 fix)
- Smooth scrolling in message container
- Status badges for online/offline peers
- Responsive design for mobile devices

#### JavaScript Application
| File | Purpose | Key Features |
|------|---------|--------------|
| `static/js/chat.js` | Chat application logic | Polling, P2P connection, messaging, UI updates |

**Chat.js Core Functions:**
- **Authentication**: `loadCurrentUser()`, `registerP2P()`
- **Peer Discovery**: `loadPeers()`, `pollPeerEvents()` (every 3s)
- **Connection Management**: 
  - `requestConnection()` - Send connection request
  - `pollConnectionRequests()` - Poll incoming requests (every 2s)
  - `pollConnectionResponses()` - Poll accept/reject (every 2s) - **Bug #1 fix**
  - `connectToPeer()` - Establish P2P connection
- **Messaging**:
  - `sendMessage()` - Send CHAT message
  - `pollMessages()` - Poll new messages (every 2s)
  - `appendMessage()` - Display message in UI
- **Session Control**:
  - `endChat()` - End session, send CLOSE message - **Bug #3 fix**
- **Health**: `sendHeartbeat()` (every 15s), `updateP2PStatus()` (every 5s)

### www/ - HTML Pages

| File | Purpose | Key Features |
|------|---------|--------------|
| `www/login.html` | Login page | Form with username/password, POST to /login |
| `www/login_error.html` | Error page | Shows authentication failure message |
| `www/index.html` | Main chat interface | Peer list, chat window, message input |

**index.html Layout:**
- Left sidebar: Online peers list with status indicators
- Main area: Chat window with messages container
- Footer: Message input + send button
- Header: Current user, P2P status, logout

### docs/ - Documentation

| File | Purpose | Content |
|------|---------|---------|
| `ARCHITECTURE.md` | System design | Architecture diagrams, data flows, threading model |
| `PROTOCOL.md` | API specification | HTTP endpoints, P2P messages, JSON schemas |

### config/

| File | Purpose |
|------|---------|
| `config/proxy.conf` | Proxy routing rules (maps paths to backend hosts) |

### Other Files

| File | Purpose |
|------|---------|
| `LICENSE` | MIT License |
| `CLEANUP_SUMMARY.md` | Documentation of cleanup process and bug fixes |
| `IMPLEMENTATION_SUMMARY.md` | Original implementation notes (Vietnamese) |

## Features

### Phase 1: HTTP Client-Server
- Cookie-based authentication
- Session management
- Peer registration and discovery
- HTTP polling (short-poll) for real-time events

### Phase 2: P2P Direct Messaging
- TCP handshake protocol (CONNECT/ACCEPT/REJECT)
- Direct peer-to-peer messaging
- Connection health monitoring (PING/PONG)
- Graceful session termination

### Phase 3: Combined System
- Request/accept pattern for connection establishment
- Bidirectional session end notifications
- Automatic peer offline detection (45s timeout)
- Real-time UI updates via polling

## Restrictions & Compliance

This project adheres to strict course requirements:

### Frontend
- Vanilla HTML/CSS/JS only (no frameworks)
- No WebSocket or WebRTC
- HTTP polling (short-poll) for events
- No external CDNs or libraries

### Backend
- Python standard library only
- No external frameworks (no Flask, Django, FastAPI)
- Threading only (no asyncio)
- Pure TCP sockets for P2P
- In-memory state (no database)

### Infrastructure
- Fixed ports: 8080 (proxy), 9001 (backend), 9100-9199 (P2P)
- Static files served by Python HTTP stack
- No external web servers

## Bug Fixes Summary

This version includes three critical bug fixes:

### Bug #1: Rejected Connection Not Handled
**Problem**: When User B rejected a connection request, User A would wait indefinitely with "Waiting for response..." message.

**Solution**:
- Backend: Added `connection_responses` storage and `/api/p2p-get-responses` endpoint
- Frontend: Added `pollConnectionResponses()` function (polls every 2s)
- Result: User A now sees rejection message and chat window closes after 2 seconds

**Files Modified**: `start_sampleapp.py`, `static/js/chat.js`

### Bug #2: Chat Input Overlaps with Footer
**Problem**: With many messages, the message input field would scroll below the footer and become invisible.

**Solution**:
- Added `min-height: 0` to `.chat-active` and `.messages-container` in CSS
- Added `overflow: hidden` to `.chat-active`
- Result: Messages scroll independently while input stays fixed at bottom

**Files Modified**: `static/css/chat.css`

### Bug #3: Peer Not Notified When Session Ends
**Problem**: When User A ended the session, User B saw no notification and the UI remained active.

**Solution**:
- Modified P2P daemon to add body field for CLOSE messages
- Forward CLOSE messages to callback before closing connection
- Frontend detects CLOSE message and shows red notification
- Result: User B sees "User A has ended the session" and input is disabled

**Files Modified**: `daemon/p2p_daemon.py`, backend forwards CLOSE to message queue

## Known Limitations

1. **NAT Traversal**: P2P connections work on local networks only. NAT hole punching not implemented.
2. **Long-Poll Latency**: Event updates have 2-3 second delay due to polling intervals.
3. **Scalability**: In-memory state limits concurrent users.
4. **No Persistence**: All data lost on restart.

## Development

### Code Style
- **Python**: PEP8, snake_case, structured logging
- **JavaScript**: 2-space indent, strict mode, BEM-style naming
- **HTML/CSS**: Semantic tags, no inline styles


## License

MIT License - See LICENSE file

## Authors

HCMUT - CO3094 Network Lab
Date: 2025-11-03
