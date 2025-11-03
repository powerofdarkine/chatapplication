# 🚀 Hybrid P2P Chat System - Technical Documentation

**Course**: CO3094 - Computer Networks Lab  
**Institution**: HCMUT - VNU-HCM  
**Date**: November 2025

---

## 📋 Table of Contents

1. [System Architecture](#system-architecture)
2. [Protocol Specification](#protocol-specification)
3. [Setup & Installation](#setup--installation)
4. [Running the Demo](#running-the-demo)
5. [Testing Scenarios](#testing-scenarios)
6. [Troubleshooting](#troubleshooting)
7. [Technical Details](#technical-details)

---

## 🏗️ System Architecture

### High-Level Overview

```
┌─────────────┐         HTTP/Cookie         ┌─────────────┐
│  Browser A  │◄──────────────────────────►│   Proxy     │
│  (User A)   │         (8080)              │  (8080)     │
└─────────────┘                             └─────────────┘
      │                                            │
      │ Long-poll                                  │ Forward
      │ /api/broadcast-peer                        │
      │ /api/heartbeat                             ▼
      │                                     ┌─────────────┐
      └────────────────────────────────────►│   Backend   │
                                            │   Server    │
                                            │  (9001)     │
                                            └─────────────┘
                                                   │
                                                   │ Manages
                                                   ▼
                                            ┌─────────────┐
                                            │  Tracker    │
                                            │  (Memory)   │
                                            │  + Events   │
                                            └─────────────┘
                                                   │
                                                   │ Controls
                                                   ▼
                                            ┌─────────────┐
                                            │ P2P Daemon  │
                                            │ (User A)    │
                                            │  Port 9100  │
                                            └─────────────┘
                                                   │
                                                   │ TCP P2P
                                                   │ Direct Socket
                                                   ▼
                                            ┌─────────────┐
                                            │ P2P Daemon  │
                                            │ (User B)    │
                                            │  Port 9101  │
                                            └─────────────┘
```

### Component Breakdown

#### 1. **Proxy Server** (`daemon/proxy.py`)
- **Port**: 8080
- **Function**: Routes HTTP requests based on `proxy.conf`
- **Technology**: Pure Python socket + threading

#### 2. **Backend Server** (`start_sampleapp.py`)
- **Port**: 9001
- **Function**: 
  - Handles authentication (cookie-based)
  - Manages peer tracker
  - Controls P2P daemons
  - Exposes REST API endpoints
- **Technology**: WeApRous framework (custom HTTP server)

#### 3. **Tracker** (`daemon/tracker.py`)
- **Storage**: In-memory dictionary
- **Function**:
  - Maintains active peer list
  - Broadcasts peer events (joined/left/updated)
  - Monitors peer health (45s timeout)
  - Manages event queues for long-polling

#### 4. **P2P Daemon** (`daemon/p2p_daemon.py`)
- **Port Range**: 9100-9199 (one per user)
- **Function**:
  - Listens for incoming P2P TCP connections
  - Initiates outgoing P2P connections
  - Handles handshake protocol
  - Routes messages between peers
  - Maintains keepalive (PING/PONG)
- **Technology**: Pure TCP socket + threading

#### 5. **Frontend** (`www/index.html`, `static/js/chat.js`)
- **Technology**: Vanilla HTML + CSS + JavaScript
- **Function**:
  - Login via HTTP POST → cookie auth
  - Register peer on login (`/api/submit-info`)
  - Long-poll for peer events (`/api/broadcast-peer`)
  - Heartbeat every 15s (`/api/heartbeat`)
  - Send/receive messages via HTTP bridge to P2P daemon

---

## 📡 Protocol Specification

### HTTP REST API

All endpoints (except `/login`) require cookie authentication.

#### Authentication
```http
POST /login
Content-Type: application/x-www-form-urlencoded

username=user1&password=pass123
```

**Response**: Sets `auth` cookie (Base64 encoded credentials)

---

#### Peer Registration
```http
POST /api/submit-info
Content-Type: application/json
Cookie: auth=<token>

{
  "display_name": "Alice",
  "channels": ["general"]
}
```

**Response**:
```json
{
  "status": "success",
  "peer_id": "user1",
  "p2p_port": 9100,
  "message": "Peer registered and P2P daemon started"
}
```

---

#### Get Peer List
```http
GET /api/get-list
Cookie: auth=<token>
```

**Response**:
```json
{
  "peers": [
    {
      "peer_id": "user2",
      "display_name": "Bob",
      "ip": "127.0.0.1",
      "port": 9101,
      "status": "ONLINE",
      "last_seen": 1730611200000,
      "channels": ["general"]
    }
  ],
  "server_time": 1730611200500
}
```

---

#### Connect to Peer (Initiate P2P)
```http
POST /api/p2p-connect
Content-Type: application/json
Cookie: auth=<token>

{
  "to_peer": "user2"
}
```

**Response**:
```json
{
  "status": "connected",
  "peer": "user2",
  "message": "P2P connection established to user2"
}
```

---

#### Send P2P Message
```http
POST /api/p2p-send
Content-Type: application/json
Cookie: auth=<token>

{
  "to_peer": "user2",
  "message": "Hello from P2P!"
}
```

**Response**:
```json
{
  "status": "sent",
  "timestamp": 1730611200000
}
```

---

#### Poll Incoming Messages
```http
POST /api/p2p-receive
Content-Type: application/json
Cookie: auth=<token>

{
  "since": 1730611000000
}
```

**Response**:
```json
{
  "messages": [
    {
      "type": "CHAT",
      "msg_id": "a1b2c3d4",
      "from": "user2",
      "to": "user1",
      "timestamp": 1730611200000,
      "body": "Hi there!"
    }
  ],
  "server_time": 1730611200500
}
```

---

#### Long-poll for Peer Events
```http
POST /api/broadcast-peer
Content-Type: application/json
Cookie: auth=<token>

{
  "peer_id": "user1",
  "since": 1730611000000
}
```

**Response**:
```json
{
  "events": [
    {
      "type": "peer-joined",
      "peer": {
        "peer_id": "user2",
        "display_name": "Bob",
        "ip": "127.0.0.1",
        "port": 9101,
        "status": "ONLINE"
      },
      "ts": 1730611100000
    }
  ]
}
```

---

#### Heartbeat
```http
POST /api/heartbeat
Content-Type: application/json
Cookie: auth=<token>

{
  "peer_id": "user1",
  "ts": 1730611200000
}
```

**Response**:
```json
{
  "expired_peers": ["user3"],
  "server_time": 1730611200000
}
```

**Note**: If `expired_peers` contains peers you're connected to, you MUST close those P2P sessions.

---

#### Disconnect from Peer
```http
POST /api/p2p-disconnect
Content-Type: application/json
Cookie: auth=<token>

{
  "peer": "user2"
}
```

---

### P2P TCP Protocol

#### Handshake (Client → Server)

```
CONNECT <to_peer_id> <from_peer_id> <nonce>\n
```

Example:
```
CONNECT user2 user1 ab12cd34\n
```

#### Handshake Response (Server → Client)

**Success**:
```
ACCEPT <to_peer_id> <from_peer_id> <nonce>\n
```

**Failure**:
```
REJECT <reason>\n
```

---

#### Message Format (JSON per line)

All messages are JSON objects terminated by `\n`.

**Chat Message**:
```json
{
  "type": "CHAT",
  "msg_id": "uuid-here",
  "from": "user1",
  "to": "user2",
  "timestamp": 1730611200000,
  "body": "Hello P2P!"
}
```

**Keepalive Ping**:
```json
{
  "type": "PING",
  "from": "user1",
  "to": "user2",
  "timestamp": 1730611200000
}
```

**Keepalive Pong**:
```json
{
  "type": "PONG",
  "from": "user2",
  "to": "user1",
  "timestamp": 1730611200100
}
```

**Graceful Close**:
```json
{
  "type": "CLOSE",
  "from": "user1",
  "to": "user2",
  "timestamp": 1730611300000
}
```

---

### Keepalive & Timeout

- **PING interval**: 10 seconds
- **Idle timeout**: 30 seconds (no activity)
- **Heartbeat interval (HTTP)**: 15 seconds
- **Server timeout**: 45 seconds (marks peer offline)

---

## 🛠️ Setup & Installation

### Prerequisites

- **Python**: 3.8+ (no external libraries required)
- **Operating System**: Windows/Linux/macOS
- **Ports**: 8080, 9000, 9001, 9100-9199 (ensure not in use)

### File Structure

```
CO3094-weaprous/
├── daemon/
│   ├── __init__.py
│   ├── backend.py          # Backend server core
│   ├── proxy.py            # Proxy server
│   ├── tracker.py          # Peer tracker
│   ├── p2p_daemon.py       # P2P daemon (NEW)
│   ├── httpadapter.py      # HTTP request handler
│   ├── request.py
│   ├── response.py
│   ├── dictionary.py
│   ├── utils.py
│   └── weaprous.py         # Framework
├── www/
│   ├── index.html          # Chat UI (UPDATED)
│   ├── login.html
│   └── login_error.html
├── static/
│   ├── css/
│   │   └── chat.css        # Chat styles (UPDATED)
│   └── js/
│       └── chat.js         # Chat logic (UPDATED)
├── config/
│   └── proxy.conf          # Proxy routing config
├── start_proxy.py          # Launch proxy
├── start_backend.py        # Launch backend
├── start_sampleapp.py      # Launch webapp (UPDATED)
├── start_all.bat           # Windows batch script
└── README_P2P.md           # This file
```

---

## 🚀 Running the Demo

### Method 1: Windows Batch Script

```cmd
start_all.bat
```

This will start 3 processes:
1. Proxy (port 8080)
2. Backend (port 9000) - *not used in current setup*
3. WebApp (port 9001)

---

### Method 2: Manual Start (3 Terminals)

#### Terminal 1: Proxy
```bash
python start_proxy.py --server-ip 127.0.0.1 --server-port 8080
```

#### Terminal 2: Backend (Optional)
```bash
python start_backend.py --server-ip 127.0.0.1 --server-port 9000
```

#### Terminal 3: WebApp
```bash
python start_sampleapp.py --server-ip 127.0.0.1 --server-port 9001
```

---

### Access the Application

Open browser and navigate to:
```
http://127.0.0.1:8080
```

Or if using `proxy.conf` hostname mapping:
```
http://app1.local:8080
```

*(Add `127.0.0.1 app1.local` to your `hosts` file)*

---

## 🧪 Testing Scenarios

### Scenario 1: Basic Login & Peer Discovery

1. **User A** opens browser, navigates to `http://127.0.0.1:8080`
2. Login with `username=user1`, `password=pass123`
3. After login:
   - Cookie `auth` is set
   - Peer registered automatically via `/api/submit-info`
   - P2P daemon starts on port 9100
   - Peer list shows empty (no other peers)

4. **User B** opens second browser (or incognito), logs in with `username=user2`, `password=pass456`
5. After User B login:
   - User B's P2P daemon starts on port 9101
   - **User A receives peer-joined event** via `/api/broadcast-peer`
   - User A's UI updates to show User B in peer list

**Expected**:
- ✅ User A sees "user2 joined" notification
- ✅ Peer list shows "user2" with status "ONLINE"

---

### Scenario 2: P2P Connection & Messaging

**Prerequisites**: User A and User B are logged in (from Scenario 1)

1. **User A** clicks on "user2" in peer list
2. Frontend calls `/api/p2p-connect` → Backend initiates TCP P2P connection
3. P2P handshake:
   ```
   User A (9100) → User B (9101): CONNECT user2 user1 <nonce>
   User B (9101) → User A (9100): ACCEPT user2 user1 <nonce>
   ```
4. UI shows "✅ P2P connection established with user2"
5. Message input is enabled

6. **User A** types "Hello from A" and presses Send
7. Message sent via `/api/p2p-send` → P2P daemon → TCP socket → User B's daemon
8. User B's daemon queues message for polling
9. User B's frontend polls `/api/p2p-receive` every 2s, receives message
10. Message appears in User B's chat window

11. **User B** clicks on "user1" to open chat
12. P2P connection already exists (bidirectional)
13. User B sends "Hi from B!"
14. User A receives and displays message

**Expected**:
- ✅ Messages appear instantly (within 2s polling interval)
- ✅ Messages show correct sender
- ✅ Timestamps are displayed
- ✅ Both directions work

---

### Scenario 3: Keepalive & Timeout

**Prerequisites**: User A and User B are connected via P2P (from Scenario 2)

1. Observe console logs - every 10s, P2P daemons send PING/PONG
2. Both users continue chatting - connection stays alive

3. **Simulate failure**: Close User B's browser tab (or kill the process)
4. User B stops sending heartbeats to `/api/heartbeat`
5. After 45 seconds:
   - Tracker marks User B as OFFLINE
   - Tracker broadcasts `peer-left` event
6. User A receives event via `/api/broadcast-peer` polling
7. User A's frontend:
   - Calls `/api/p2p-disconnect` to close P2P socket
   - Updates UI: "❌ user2 disconnected (offline)"
   - Disables message input

**Expected**:
- ✅ User A sees "user2 disconnected" after ~45s
- ✅ Message input is disabled
- ✅ Peer list shows "user2" as OFFLINE or removed

---

### Scenario 4: Multiple Peers

1. Login User A (`user1`)
2. Login User B (`user2`)
3. Login User C (`admin`)

4. All users see each other in peer list
5. User A connects to User B (P2P)
6. User A connects to User C (P2P) - opens new chat window
7. User A can switch between chats by clicking peer names

**Expected**:
- ✅ User A has 2 active P2P connections (9100 ↔ 9101, 9100 ↔ 9102)
- ✅ Messages are routed correctly to intended peer
- ✅ Switching chats preserves message history in UI

---

### Scenario 5: Heartbeat from Frontend

1. Login as User A
2. Open browser console (F12)
3. Observe logs every 15 seconds: `[Chat] Server reported expired peers: []`
4. This confirms heartbeat is working

**Expected**:
- ✅ `/api/heartbeat` called every 15s
- ✅ Response contains `expired_peers` array (usually empty)

---

## 🐛 Troubleshooting

### Issue: Login fails

**Symptoms**: 401 Unauthorized or redirect to login page

**Solutions**:
- Check credentials: `user1/pass123`, `user2/pass456`, `admin/password`
- Clear browser cookies
- Check console for errors
- Verify proxy is forwarding to correct backend port (9001)

---

### Issue: Peer list empty

**Symptoms**: After login, peer list shows "No peers online"

**Solutions**:
- Check if multiple users are logged in (use different browsers/incognito)
- Open browser console and check for errors in `/api/get-list`
- Verify tracker is running (check backend console logs)
- Refresh peer list manually (click 🔄 button)

---

### Issue: Cannot connect to peer

**Symptoms**: Click peer name, shows "Connection failed"

**Solutions**:
- Check if peer is actually ONLINE (status in peer list)
- Check backend console for P2P daemon errors
- Verify ports 9100-9199 are not blocked by firewall
- Try disconnecting and reconnecting

---

### Issue: Messages not received

**Symptoms**: Send message but recipient doesn't see it

**Solutions**:
- Verify P2P connection established (status shows "🟢 P2P Connected")
- Check browser console for `/api/p2p-receive` polling errors
- Check backend console for P2P daemon logs
- Try reconnecting to peer

---

### Issue: Peer doesn't go offline after disconnect

**Symptoms**: Close browser but peer still shows ONLINE

**Solutions**:
- Wait 45 seconds for heartbeat timeout
- Check if heartbeat is being sent (browser console logs)
- Verify tracker cleanup thread is running (backend console)

---

### Issue: Port already in use

**Symptoms**: `OSError: [WinError 10048] Only one usage of each socket address`

**Solutions**:
```cmd
# Windows - Find process using port
netstat -ano | findstr :8080
taskkill /PID <process_id> /F

# Linux/Mac
lsof -ti:8080 | xargs kill -9
```

---

### Issue: P2P daemon not starting

**Symptoms**: `/api/submit-info` fails or no P2P port assigned

**Solutions**:
- Check backend console for errors
- Verify `p2p_daemon.py` exists and has no syntax errors
- Check if ports 9100+ are available
- Restart backend server

---

## 🔧 Technical Details

### Thread Safety

- **Tracker**: Uses `threading.RLock()` for all peer/event operations
- **P2P Daemon**: Each connection has its own lock
- **Message Queues**: Protected by `message_lock`

### Memory Management

- **Event queues**: `deque(maxlen=100)` per peer (automatic cleanup)
- **Message queues**: `deque(maxlen=100)` per user
- **Peer list**: Auto-removed after 45s timeout

### Security Considerations

- **Authentication**: Cookie-based (Base64 encoded credentials)
- **XSS Protection**: `escapeHtml()` function in frontend
- **Input Validation**: Check peer exists before connecting
- **No SQL Injection**: No database used
- **CSRF**: Not implemented (could add token in production)

### Performance

- **Concurrent connections**: Limited by Python threading (typically 100-1000)
- **Message latency**: 2-3s (polling interval)
- **Memory usage**: ~1MB per active peer (including message history)
- **CPU usage**: Minimal (~1% per active P2P connection)

---

## 📚 Protocol Compliance Checklist

| Requirement | Status | Implementation |
|------------|--------|----------------|
| ✅ Login via HTTP with cookie | | `POST /login` → sets `auth` cookie |
| ✅ Peer registration | | `POST /api/submit-info` on login |
| ✅ Peer discovery | | `GET /api/get-list` + long-poll `/api/broadcast-peer` |
| ✅ P2P TCP connection | | Pure socket, handshake CONNECT/ACCEPT |
| ✅ P2P messaging | | JSON per line, type: CHAT |
| ✅ Keepalive PING/PONG | | Every 10s, 30s idle timeout |
| ✅ Heartbeat 15s | | Frontend calls `/api/heartbeat` |
| ✅ Timeout 45s | | Tracker marks OFFLINE, broadcasts peer-left |
| ✅ Auto-close on timeout | | Frontend handles expired_peers + peer-left events |
| ✅ No external libraries | | Only Python stdlib (socket, threading, json, time) |
| ✅ No frameworks | | Custom WeApRous framework (provided by assignment) |
| ✅ Vanilla frontend | | Pure HTML + CSS + JS, no React/Vue/jQuery |

---

## 🎓 Educational Notes

### Why Hybrid Architecture?

**Browser limitations**:
- JavaScript cannot create raw TCP sockets
- WebSocket is not "pure socket" as required
- WebRTC has signaling overhead

**Solution**:
- Backend maintains TCP P2P connections
- Frontend communicates via HTTP polling bridge
- Still demonstrates P2P concepts (handshake, keepalive, direct routing)

### Why Not WebSocket?

Assignment explicitly forbids:
> "no_websocket_webrtc": "Không dùng WebSocket/WebRTC"

We use long-polling instead.

### Thread vs Async

Assignment requires:
> "threading_only": "Dùng Python threading/timer; không dùng asyncio"

All concurrency uses `threading.Thread` with daemon threads.

---

## 📞 Support

For issues or questions, please contact:
- **Course Forum**: [Link to forum]
- **TA Email**: [TA email]
- **Lab Hours**: [Lab schedule]

---

## 📄 License

Copyright (C) 2025 HCMUT VNU-HCM. All rights reserved.  
This code is for educational purposes only as part of CO3094 course.

---

**End of Documentation** 🎉
