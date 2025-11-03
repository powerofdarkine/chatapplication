# Protocol Specification

## HTTP REST API

### Authentication

#### POST /api/login

Authenticate user and establish session.

**Request:**
```http
POST /api/login HTTP/1.1
Content-Type: application/x-www-form-urlencoded

username=user1&password=pass123
```

**Response (Success):**
```http
HTTP/1.1 302 Found
Set-Cookie: session=dXNlcjE6MTczMDY3ODQwMA==; Path=/
Location: /

Successfully logged in
```

**Response (Failure):**
```http
HTTP/1.1 302 Found
Location: /login_error.html
```

### Peer Management

#### POST /api/submit-info

Register peer and spawn P2P daemon.

**Request:**
```json
{
  "display_name": "User One",
  "channels": ["general"]
}
```

**Response:**
```json
{
  "status": "registered",
  "peer_id": "user1",
  "port": 9100,
  "ip": "127.0.0.1"
}
```

#### GET /api/get-list

Get list of all online peers.

**Response:**
```json
{
  "peers": [
    {
      "peer_id": "user2",
      "ip": "127.0.0.1",
      "port": 9101,
      "display_name": "User Two",
      "status": "ONLINE",
      "last_seen": 1730678400.0
    }
  ]
}
```

#### POST /api/broadcast-peer

Long-poll for peer events (join, leave, update).

**Request:**
```json
{
  "since": 1730678000
}
```

**Response (with events):**
```json
{
  "events": [
    {
      "type": "peer-joined",
      "timestamp": 1730678100,
      "data": {
        "peer_id": "user3",
        "display_name": "User Three",
        "ip": "127.0.0.1",
        "port": 9102
      }
    },
    {
      "type": "peer-left",
      "timestamp": 1730678200,
      "data": {
        "peer_id": "user2"
      }
    }
  ]
}
```

**Response (timeout, no events):**
```json
{
  "events": []
}
```

#### POST /api/heartbeat

Update last_seen timestamp.

**Response:**
```json
{
  "status": "ok",
  "expired_peers": ["user4"]
}
```

### P2P Connection Management

#### POST /api/p2p-request

Send connection request to peer.

**Request:**
```json
{
  "to_peer": "user2"
}
```

**Response:**
```json
{
  "status": "request_sent",
  "message": "Connection request sent to user2"
}
```

#### GET /api/p2p-get-requests

Poll for pending connection requests.

**Response:**
```json
{
  "requests": [
    {
      "from": "user1",
      "timestamp": 1730678400.0
    }
  ]
}
```

#### POST /api/p2p-accept

Accept connection request and establish P2P.

**Request:**
```json
{
  "from_peer": "user1"
}
```

**Response:**
```json
{
  "status": "connected",
  "peer": "user1",
  "message": "Connection accepted, P2P established with user1"
}
```

#### POST /api/p2p-reject

Reject connection request.

**Request:**
```json
{
  "from_peer": "user1"
}
```

**Response:**
```json
{
  "status": "rejected",
  "message": "Connection request from user1 rejected"
}
```

#### GET /api/p2p-get-responses

Poll for accept/reject responses.

**Response:**
```json
{
  "responses": [
    {
      "from": "user2",
      "status": "accepted",
      "timestamp": 1730678500.0
    }
  ]
}
```

### P2P Messaging

#### POST /api/p2p-send

Send message via P2P daemon.

**Request:**
```json
{
  "to_peer": "user2",
  "message": "Hello World",
  "type": "CHAT"
}
```

**Response:**
```json
{
  "status": "sent",
  "timestamp": 1730678600000
}
```

#### POST /api/p2p-receive

Poll for incoming P2P messages.

**Request:**
```json
{
  "since": 1730678500000
}
```

**Response:**
```json
{
  "messages": [
    {
      "type": "CHAT",
      "from": "user1",
      "to": "user2",
      "msg_id": "550e8400-e29b-41d4-a716-446655440000",
      "body": "Hello World",
      "timestamp": 1730678600000
    }
  ]
}
```

#### POST /api/p2p-disconnect

Close P2P connection.

**Request:**
```json
{
  "peer": "user2"
}
```

**Response:**
```json
{
  "status": "disconnected"
}
```

#### GET /api/p2p-status

Get P2P daemon status.

**Response:**
```json
{
  "daemon_running": true,
  "port": 9100,
  "active_connections": ["user2", "user3"]
}
```

## P2P TCP Protocol

### Handshake Protocol

All handshake messages are newline-terminated strings.

#### Client Initiates Connection

```
CLIENT → SERVER: CONNECT <to_peer_id> <from_peer_id> <nonce>\n
```

Example:
```
CONNECT user2 user1 a1b2c3d4\n
```

#### Server Accepts Connection

```
SERVER → CLIENT: ACCEPT <to_peer_id> <from_peer_id> <nonce>\n
```

Example:
```
ACCEPT user1 user2 a1b2c3d4\n
```

#### Server Rejects Connection

```
SERVER → CLIENT: REJECT <to_peer_id> <from_peer_id> <nonce>\n
```

Example:
```
REJECT user1 user2 a1b2c3d4\n
```

### Message Protocol

After successful handshake, all messages are JSON objects, one per line.

#### Message Schema

```json
{
  "type": "CHAT|PING|PONG|CLOSE",
  "from": "sender_peer_id",
  "to": "receiver_peer_id",
  "timestamp": 1730678600000
}
```

#### CHAT Message

```json
{
  "type": "CHAT",
  "from": "user1",
  "to": "user2",
  "msg_id": "550e8400-e29b-41d4-a716-446655440000",
  "body": "Hello World",
  "timestamp": 1730678600000
}
```

#### PING Message

```json
{
  "type": "PING",
  "from": "user1",
  "to": "user2",
  "timestamp": 1730678610000
}
```

#### PONG Message

```json
{
  "type": "PONG",
  "from": "user2",
  "to": "user1",
  "timestamp": 1730678610100
}
```

#### CLOSE Message

```json
{
  "type": "CLOSE",
  "from": "user1",
  "to": "user2",
  "body": "__SESSION_ENDED__",
  "timestamp": 1730678620000
}
```

Note: `body` in CLOSE message is optional. `__SESSION_ENDED__` is a special marker for user-initiated session end.

## Connection Lifecycle

```
1. Requester sends HTTP: POST /api/p2p-request {to_peer: "user2"}
   - Backend stores request

2. Target polls HTTP: GET /api/p2p-get-requests
   - Receives pending requests
   - Shows UI modal

3. Target accepts HTTP: POST /api/p2p-accept {from_peer: "user1"}
   - Backend B initiates TCP to peer A

4. P2P TCP Handshake:
   Daemon B → Daemon A: "CONNECT user1 user2 nonce\n"
   Daemon A → Daemon B: "ACCEPT user2 user1 nonce\n"

5. P2P Connected: Both daemons mark connection active

6. Requester polls HTTP: GET /api/p2p-get-responses
   - Receives {status: "accepted"}

7. Frontend enables chat input on both sides

8. Messaging via HTTP bridge:
   Browser A → HTTP POST /api/p2p-send → Daemon A → TCP → Daemon B → Queue
   Browser B ← HTTP POST /api/p2p-receive ← Queue

9. Keepalive (background):
   Every 10s: Daemon → Daemon: {"type":"PING",...}\n
   Response: Daemon → Daemon: {"type":"PONG",...}\n
   Idle timeout: 30s without activity → close

10. Session end (user-initiated):
    Browser A → HTTP POST /api/p2p-send {type: "CLOSE", message: "__SESSION_ENDED__"}
    Daemon A → Daemon B: {"type":"CLOSE","body":"__SESSION_ENDED__",...}\n
    Browser A → HTTP POST /api/p2p-disconnect
    Daemon A closes socket

11. Target receives CLOSE:
    Daemon B queues CLOSE message
    Browser B polls /api/p2p-receive
    Shows "user1 has ended the session"
    Disables input

12. Crash/logout (peer timeout):
    Peer stops sending heartbeat
    After 45s: Tracker marks offline
    Broadcasts peer-left event
    Other browsers receive event, disconnect P2P
```

## Error Handling

### HTTP Errors

- `400 Bad Request`: Missing required parameter
- `401 Unauthorized`: Invalid or missing session cookie
- `404 Not Found`: Peer not found or offline
- `500 Internal Server Error`: Server-side exception

### P2P Errors

- **Connection Refused**: Target daemon not running (peer offline)
- **REJECT Response**: Target peer rejected connection
- **Timeout**: Handshake or message timeout (1s socket timeout)
- **Idle Timeout**: No activity for 30s (connection closed)
- **Send Failure**: Socket send error (peer disconnected)

## Timing Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| HTTP long-poll timeout | 30s | Max wait for events |
| Frontend poll interval (events) | 3s | Peer join/leave updates |
| Frontend poll interval (messages) | 2s | Chat message updates |
| Frontend poll interval (requests) | 2s | Connection request updates |
| Frontend poll interval (responses) | 2s | Accept/reject updates |
| Frontend heartbeat interval | 15s | Keep session alive |
| Backend peer timeout | 45s | Mark peer offline |
| Backend tracker cleanup interval | 5s | Check for expired peers |
| P2P PING interval | 10s | Keepalive |
| P2P idle timeout | 30s | Close inactive connections |
| P2P socket timeout | 1s | Non-blocking receive |
| P2P send retry | None | Fail immediately |
| CLOSE message delay | 800ms | Ensure delivery before disconnect |

## Message Size Limits

- HTTP request body: Unlimited (no enforced limit)
- HTTP response body: Unlimited (no enforced limit)
- P2P message line: 4096 bytes buffer
- CHAT body: Practical limit ~3KB (fits in one line)

## Concurrency & Thread Safety

### HTTP Layer
- One thread per request (blocking I/O)
- No shared mutable state between requests
- Cookie session validated on each request

### Tracker
- RLock on all peer dictionary operations
- RLock on event queues
- Background cleanup thread (5s interval)

### P2P Daemon
- RLock on connections dictionary
- One server thread per daemon (accept loop)
- One message loop thread per connection
- One keepalive thread per daemon
- Socket timeout 1s (prevents blocking)

### Message Queues
- Lock on deque operations (append/popleft)
- Per-user queues (no cross-user contention)
