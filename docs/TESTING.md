# Testing Guide

This document provides comprehensive testing procedures for CO3094-weaprous.

## Quick Test

Start the system and run basic smoke test:

```bash
# Windows
start_all.bat

# Manual start
python start_proxy.py
python start_sampleapp.py
python start_backend.py  # If separate backend
```

Wait 5 seconds, then open:
- Browser A: http://localhost:8080/ → Login as `user1` / `pass123`
- Browser B: http://localhost:8080/ → Login as `user2` / `pass456`

Send message from A to B, verify delivery. Test complete if message appears.

## Test Scenarios

### Scenario 1: User Authentication

**Test 1.1 - Valid Login**

```bash
curl -X POST http://localhost:8080/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user1&password=pass123" \
  -c cookies.txt -v
```

Expected: 302 redirect to `/`, Set-Cookie header with session token.

**Test 1.2 - Invalid Login**

```bash
curl -X POST http://localhost:8080/login \
  -d "username=wrong&password=wrong" \
  -v
```

Expected: 302 redirect to `/login_error.html`.

**Test 1.3 - Protected Resource Without Auth**

```bash
curl http://localhost:8080/api/get-online-peers -v
```

Expected: 401 Unauthorized or 302 redirect to login.

### Scenario 2: Peer Discovery

**Test 2.1 - Get Online Peers**

```bash
# After logging in as user1
curl http://localhost:8080/api/get-online-peers \
  -b cookies.txt
```

Expected response:
```json
{
  "status": "success",
  "peers": [
    {"peer_id": "user2", "p2p_port": 9101}
  ]
}
```

**Test 2.2 - Poll Events**

```bash
curl http://localhost:8080/api/poll-events \
  -b cookies.txt
```

Expected response:
```json
{
  "status": "success",
  "events": [
    {"type": "peer-joined", "peer_id": "user2", "timestamp": 1234567890}
  ]
}
```

### Scenario 3: P2P Connection Setup

**Test 3.1 - Initiate Connection**

```bash
# user1 requests connection to user2
curl -X POST http://localhost:8080/api/p2p-connect \
  -H "Content-Type: application/json" \
  -d '{"target_peer_id": "user2"}' \
  -b cookies.txt
```

Expected response:
```json
{
  "status": "success",
  "message": "Connection request sent to user2"
}
```

**Test 3.2 - Poll Connection Requests (as user2)**

```bash
curl http://localhost:8080/api/p2p-get-requests \
  -b cookies_user2.txt
```

Expected response:
```json
{
  "status": "success",
  "requests": [
    {"from": "user1", "timestamp": 1234567890}
  ]
}
```

**Test 3.3 - Accept Connection**

```bash
curl -X POST http://localhost:8080/api/p2p-accept \
  -H "Content-Type: application/json" \
  -d '{"from_peer_id": "user1"}' \
  -b cookies_user2.txt
```

Expected response:
```json
{
  "status": "success",
  "message": "Connection accepted"
}
```

**Test 3.4 - Reject Connection**

```bash
curl -X POST http://localhost:8080/api/p2p-reject \
  -H "Content-Type: application/json" \
  -d '{"from_peer_id": "user1"}' \
  -b cookies_user2.txt
```

Expected response:
```json
{
  "status": "success",
  "message": "Connection rejected"
}
```

### Scenario 4: P2P Messaging

**Test 4.1 - Send Message**

```bash
curl -X POST http://localhost:8080/api/p2p-send-message \
  -H "Content-Type: application/json" \
  -d '{"to": "user2", "body": "Hello from curl"}' \
  -b cookies.txt
```

Expected response:
```json
{
  "status": "success",
  "message": "Message queued for user2"
}
```

**Test 4.2 - Poll Messages (as user2)**

```bash
curl http://localhost:8080/api/p2p-get-messages \
  -b cookies_user2.txt
```

Expected response:
```json
{
  "status": "success",
  "messages": [
    {
      "type": "CHAT",
      "from": "user1",
      "to": "user2",
      "body": "Hello from curl",
      "msg_id": "uuid-here",
      "timestamp": 1234567890
    }
  ]
}
```

### Scenario 5: Session Termination

**Test 5.1 - End Session**

```bash
curl -X POST http://localhost:8080/api/p2p-close \
  -H "Content-Type: application/json" \
  -d '{"to": "user2"}' \
  -b cookies.txt
```

Expected response:
```json
{
  "status": "success",
  "message": "Session closed with user2"
}
```

**Test 5.2 - Verify CLOSE Notification**

```bash
# As user2, poll messages
curl http://localhost:8080/api/p2p-get-messages \
  -b cookies_user2.txt
```

Expected response includes:
```json
{
  "messages": [
    {
      "type": "CLOSE",
      "from": "user1",
      "to": "user2",
      "body": "user1 has ended the session",
      "timestamp": 1234567890
    }
  ]
}
```

**Test 5.3 - Logout**

```bash
curl http://localhost:8080/logout -b cookies.txt -v
```

Expected: 302 redirect to `/login.html`, cookie cleared.

### Scenario 6: Heartbeat & Timeout

**Test 6.1 - Send Heartbeat**

```bash
curl -X POST http://localhost:8080/api/heartbeat \
  -b cookies.txt
```

Expected response:
```json
{
  "status": "success"
}
```

**Test 6.2 - Simulate Timeout**

1. Login as user1
2. Stop sending heartbeats for 60 seconds
3. Check peer list as user2

Expected: user1 disappears from online peers list.

### Scenario 7: TCP P2P Direct Testing

**Test 7.1 - Raw TCP Connection**

```bash
# Connect to P2P daemon port (assuming user1 on 9100)
nc localhost 9100
```

Send CONNECT handshake:
```json
{"type":"CONNECT","from":"user2","to":"user1"}
```

Expected response (if user1 accepts):
```json
{"type":"ACCEPT","from":"user1","to":"user2"}
```

**Test 7.2 - Send PING**

After connection established:
```json
{"type":"PING","from":"user2","to":"user1"}
```

Expected response:
```json
{"type":"PONG","from":"user1","to":"user2"}
```

**Test 7.3 - Send CHAT**

```json
{"type":"CHAT","from":"user2","to":"user1","body":"Test message"}
```

Expected: No immediate response (CHAT is one-way, backend queues it).

## Browser Testing

### UI Test 1: Basic Chat Flow

1. Open Browser A → http://localhost:8080/
2. Login as `user1` / `pass123`
3. Open Browser B (incognito) → http://localhost:8080/
4. Login as `user2` / `pass456`
5. In Browser A, click "user2" in peer list
6. In Browser B, click "Accept"
7. In Browser A, type "Hello" and press Enter
8. Verify "Hello" appears in Browser B messages

### UI Test 2: Rejection Handling

1. Browser A (user1): Click "user2" to request connection
2. Browser B (user2): Click "Reject"
3. Verify Browser A shows: "user2 rejected your connection request"
4. Verify chat window closes after 2 seconds

### UI Test 3: Session End Notification

1. Establish connection between user1 and user2
2. Browser A (user1): Click "End Session" button
3. Verify Browser B shows: "user1 has ended the session" (in red)
4. Verify Browser B input disabled and button changed to "Close"

### UI Test 4: Footer Overlap Fix

1. Establish chat session
2. Send 50+ messages to fill message area
3. Scroll to bottom
4. Verify input field remains visible above footer
5. Verify message area scrolls independently

### UI Test 5: Heartbeat & Timeout

1. Login as user1 in Browser A
2. Login as user2 in Browser B
3. Close Browser A (simulate crash)
4. Wait 60 seconds
5. Verify Browser B shows: "user1 has left" (peer-left event)

## Load Testing

### Test: Multiple Concurrent Connections

```bash
# Start 5 users
for i in {1..5}; do
  curl -X POST http://localhost:8080/login \
    -d "username=user$i&password=pass123" \
    -c cookies_$i.txt &
done
wait

# Each user requests connection to next user
for i in {1..4}; do
  curl -X POST http://localhost:8080/api/p2p-connect \
    -d "{\"target_peer_id\": \"user$((i+1))\"}" \
    -b cookies_$i.txt &
done
wait
```

Expected: All connections succeed, no race conditions.

## Error Testing

### Test: Invalid JSON

```bash
curl -X POST http://localhost:8080/api/p2p-send-message \
  -H "Content-Type: application/json" \
  -d '{invalid json}' \
  -b cookies.txt
```

Expected: 400 Bad Request or 500 Internal Server Error.

### Test: Missing Required Fields

```bash
curl -X POST http://localhost:8080/api/p2p-connect \
  -H "Content-Type: application/json" \
  -d '{}' \
  -b cookies.txt
```

Expected: 400 Bad Request with error message.

### Test: Connection to Non-Existent Peer

```bash
curl -X POST http://localhost:8080/api/p2p-connect \
  -H "Content-Type: application/json" \
  -d '{"target_peer_id": "nonexistent"}' \
  -b cookies.txt
```

Expected: 404 Not Found or error response.

### Test: Double Connection Request

1. user1 requests connection to user2
2. Before user2 responds, user1 requests again
3. Expected: Second request handled gracefully (no crash)

## Performance Benchmarks

### Benchmark 1: Message Latency

Send 100 messages, measure average delivery time:

```bash
start_time=$(date +%s%N)
for i in {1..100}; do
  curl -X POST http://localhost:8080/api/p2p-send-message \
    -d '{"to":"user2","body":"Test '$i'"}' \
    -b cookies.txt -s > /dev/null
done
end_time=$(date +%s%N)
echo "Average latency: $(( (end_time - start_time) / 100000000 )) ms"
```

Expected: < 50ms average latency on localhost.

### Benchmark 2: Peer Discovery Speed

```bash
time curl http://localhost:8080/api/get-online-peers -b cookies.txt
```

Expected: < 100ms response time.

## Regression Testing

After any code changes, run full test suite:

```bash
# 1. Start system
start_all.bat

# 2. Run automated tests
python tests/run_all_tests.py  # If test suite exists

# 3. Manual browser tests (all 5 UI tests)
# 4. Verify no errors in console logs
# 5. Check for memory leaks (run for 30 minutes)
```

## Known Limitations Testing

### Limitation 1: No NAT Traversal

Test: Connect from external network.
Expected: Fails (P2P only works on local network).

### Limitation 2: No Persistence

Test: Restart backend, check if chat history persists.
Expected: All data lost (in-memory only).

### Limitation 3: No Encryption

Test: Inspect network traffic with Wireshark.
Expected: Messages visible in plain text.

## Test Results Log

Format for documenting test runs:

```
Date: 2025-11-03
Tester: Development Team
Environment: Windows 11, Python 3.11, Chrome 130
Test Suite: Full regression

Scenario 1: PASS (5/5 tests)
Scenario 2: PASS (2/2 tests)
Scenario 3: PASS (4/4 tests)
Scenario 4: PASS (2/2 tests)
Scenario 5: PASS (3/3 tests)
Scenario 6: PASS (2/2 tests)
Scenario 7: PASS (3/3 tests)
UI Tests: PASS (5/5 tests)

Total: 26/26 tests passed
Status: READY FOR SUBMISSION
```
