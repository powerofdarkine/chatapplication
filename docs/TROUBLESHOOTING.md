# Troubleshooting Guide

This document provides solutions to common issues in CO3094-weaprous.

## Startup Issues

### Issue: "Address already in use" Error

**Symptoms:**
```
OSError: [WinError 10048] Only one usage of each socket address is normally permitted
```

**Cause:** Port already bound by another process or previous instance.

**Solution:**

Windows PowerShell:
```powershell
# Find process using port 8080
netstat -ano | findstr :8080

# Kill process by PID
taskkill /PID <PID> /F

# Or kill all Python processes
taskkill /IM python.exe /F
```

Alternative: Change port in config file.

### Issue: Backend Fails to Start

**Symptoms:**
```
ModuleNotFoundError: No module named 'daemon'
```

**Cause:** Working directory incorrect or Python path not set.

**Solution:**
```bash
# Ensure you're in project root
cd d:\school\HK251\network\lab\Assignment\CO3094-weaprous

# Run with explicit path
python start_sampleapp.py
```

### Issue: Proxy Can't Connect to Backend

**Symptoms:**
```
[PROXY] Error connecting to backend at localhost:9001: Connection refused
```

**Cause:** Backend not running or port mismatch.

**Solution:**
1. Check backend is running: `netstat -ano | findstr :9001`
2. Verify port in `config/proxy.conf` matches `start_sampleapp.py`
3. Start backend first, then proxy

### Issue: P2P Daemon Fails to Bind Port

**Symptoms:**
```
[P2P] Failed to bind on port 9100: Address already in use
```

**Cause:** Too many users logged in or port conflict.

**Solution:**
```bash
# Check ports 9100-9199
netstat -ano | findstr :910

# Kill all P2P daemons
taskkill /FI "WINDOWTITLE eq P2P*" /F

# Or reduce max users in start_sampleapp.py
```

## Login Issues

### Issue: Login Always Redirected to Error Page

**Symptoms:**
- Valid credentials redirect to `/login_error.html`

**Cause:** Session validation failing or user DB not initialized.

**Diagnosis:**
```bash
# Check logs in terminal running start_sampleapp.py
# Look for authentication errors
```

**Solution:**
1. Verify credentials in `start_sampleapp.py` (hardcoded users)
2. Clear browser cookies
3. Restart backend to reset in-memory state

### Issue: "Invalid Session" After Login

**Symptoms:**
- Login succeeds but immediate logout or 401 errors

**Cause:** Cookie not being sent or session token invalid.

**Solution:**
1. Enable cookies in browser
2. Check `SameSite` cookie attribute
3. Verify proxy forwards `Cookie` header:
   ```python
   # In start_proxy.py
   if 'Cookie' in self.headers:
       backend_headers['Cookie'] = self.headers['Cookie']
   ```

### Issue: Multiple Logins with Same User

**Symptoms:**
- First session kicks second session out

**Cause:** Session ID collision or tracker not handling multiple sessions.

**Solution:** By design - one session per user. Logout from first browser before logging in again.

## Peer Discovery Issues

### Issue: Peer List Always Empty

**Symptoms:**
- `/api/get-online-peers` returns `{"peers": []}`

**Cause:** Heartbeat not working or tracker timeout too aggressive.

**Diagnosis:**
```javascript
// In browser console (F12)
console.log(window.heartbeatInterval);  // Should be defined
```

**Solution:**
1. Verify heartbeat sends every 15 seconds:
   ```javascript
   // In chat.js
   setInterval(sendHeartbeat, 15000);
   ```
2. Check tracker timeout (should be 45s):
   ```python
   # In daemon/tracker.py
   TIMEOUT_SECONDS = 45
   ```
3. Open browser console and check for heartbeat errors

### Issue: "peer-joined" Event Not Firing

**Symptoms:**
- New peer logs in but existing users don't see notification

**Cause:** Event polling not running or event not being queued.

**Diagnosis:**
```bash
# In backend logs, check for:
[TRACKER] User user2 registered with port 9101
```

**Solution:**
1. Verify `pollPeerEvents()` runs every 3 seconds
2. Check event queue in backend:
   ```python
   # In start_sampleapp.py
   print(f"Events for {peer_id}: {peer_events[peer_id]}")
   ```

## P2P Connection Issues

### Issue: Connection Request Never Arrives

**Symptoms:**
- User A clicks peer, User B sees nothing

**Cause:** P2P daemon not running or port mismatch.

**Diagnosis:**
```bash
# Check if P2P daemon is listening
netstat -ano | findstr :9100
netstat -ano | findstr :9101
```

**Solution:**
1. Verify daemon started in backend logs
2. Check port mapping: `tracker.get_peer_port(peer_id)`
3. Ensure `pollPeerRequests()` runs on receiver side

### Issue: ACCEPT Message Not Reaching Requester

**Symptoms:**
- User B clicks "Accept", User A stays on "Waiting for response..."

**Cause:** TCP handshake failing or backend not forwarding response.

**Diagnosis:**
```bash
# In P2P daemon logs (backend terminal):
[P2P] ACCEPT sent to user1
```

**Solution:**
1. Check `/api/p2p-get-responses` endpoint exists
2. Verify `pollConnectionResponses()` runs every 2s
3. Check `connection_responses` storage in backend

### Issue: "Connection Rejected" Shown Immediately

**Symptoms:**
- Chat window closes instantly after request

**Cause:** Rejection handling bug or P2P daemon crashed.

**Solution:**
1. Check P2P daemon logs for crashes
2. Verify reject button in UI works:
   ```javascript
   // In chat.js
   rejectBtn.addEventListener('click', async () => {
       await rejectConnection(remotePeerId);
   });
   ```

## Messaging Issues

### Issue: Messages Not Appearing

**Symptoms:**
- User A sends message, User B sees nothing

**Cause:** Polling stopped or message queue issue.

**Diagnosis:**
```javascript
// In browser console
console.log(window.messagePollingActive);  // Should be true
```

**Solution:**
1. Verify `pollMessages()` runs every 2 seconds
2. Check message queue in backend:
   ```python
   print(f"Messages for {peer_id}: {peer_messages[peer_id]}")
   ```
3. Check P2P daemon `on_message` callback is registered

### Issue: Messages Appear Out of Order

**Symptoms:**
- Messages not in chronological order

**Cause:** Race condition in polling or timestamp issues.

**Solution:**
1. Add client-side sorting by timestamp:
   ```javascript
   messages.sort((a, b) => a.timestamp - b.timestamp);
   ```
2. Use monotonic timestamps: `time.monotonic()` in Python

### Issue: Duplicate Messages

**Symptoms:**
- Same message appears multiple times

**Cause:** Polling retrieves same message twice.

**Solution:**
1. Implement message deduplication by `msg_id`:
   ```javascript
   const seenMsgIds = new Set();
   messages.forEach(msg => {
       if (!seenMsgIds.has(msg.msg_id)) {
           appendMessage(msg);
           seenMsgIds.add(msg.msg_id);
       }
   });
   ```
2. Clear message queue after retrieval in backend

## Session End Issues

### Issue: "End Session" Button Not Working

**Symptoms:**
- Button clicked, nothing happens

**Cause:** `/api/p2p-close` endpoint failing or event handler not attached.

**Diagnosis:**
```javascript
// In browser console
document.getElementById('end-session-btn').onclick
// Should return function
```

**Solution:**
1. Verify event listener attached:
   ```javascript
   const endBtn = document.getElementById('end-session-btn');
   console.log(endBtn);  // Should not be null
   ```
2. Check network tab for `/api/p2p-close` request
3. Verify backend forwards CLOSE message

### Issue: Peer Not Notified When Session Ends

**Symptoms:**
- User A clicks "End Session", User B sees no notification

**Cause:** CLOSE message not forwarded to callback or body field missing.

**Solution (ALREADY FIXED IN BUG 3):**
```python
# In daemon/p2p_daemon.py
def send_message(self, to_peer_id, msg_type, body=None):
    msg = {"type": msg_type, "from": self.my_peer_id, "to": to_peer_id}
    if msg_type == 'CHAT':
        msg['msg_id'] = str(uuid.uuid4())
        msg['body'] = body
    elif msg_type == 'CLOSE':
        if body:
            msg['body'] = body  # <- CRITICAL FIX
```

## UI Issues

### Issue: Chat Input Overlaps Footer

**Symptoms:**
- Input field not visible when many messages

**Cause:** Flexbox without `min-height: 0`.

**Solution (ALREADY FIXED IN BUG 2):**
```css
/* In static/css/chat.css */
.chat-active {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;  /* <- CRITICAL FIX */
    overflow: hidden;
}

.messages-container {
    flex: 1;
    overflow-y: auto;
    min-height: 0;  /* <- CRITICAL FIX */
}
```

### Issue: Scroll Not Working in Messages

**Symptoms:**
- Can't scroll to see old messages

**Cause:** Missing `overflow-y: auto` or height constraint.

**Solution:**
```css
.messages-container {
    overflow-y: auto;
    max-height: 100%;
}
```

### Issue: New Messages Not Auto-Scrolling

**Symptoms:**
- New message arrives but view stays at top

**Cause:** Missing auto-scroll logic.

**Solution:**
```javascript
function appendMessage(from, body, isSystem = false) {
    // ... append message ...
    const container = document.querySelector('.messages-container');
    container.scrollTop = container.scrollHeight;  // Auto-scroll to bottom
}
```

## Performance Issues

### Issue: High CPU Usage

**Symptoms:**
- Python process using 50%+ CPU

**Cause:** Tight polling loops or missing sleep in threads.

**Diagnosis:**
```python
# Add logging to identify hot loop
import time
start = time.time()
# ... loop code ...
print(f"Loop took {time.time() - start} seconds")
```

**Solution:**
1. Add `time.sleep(0.1)` in receive loops:
   ```python
   while not self.stop_event.is_set():
       # ... receive logic ...
       time.sleep(0.1)  # Prevent busy-wait
   ```
2. Use socket timeouts instead of spinning

### Issue: Memory Leak

**Symptoms:**
- Memory usage grows over time

**Cause:** Message queues not being cleared or threads not joining.

**Diagnosis:**
```python
import tracemalloc
tracemalloc.start()
# ... run for 30 minutes ...
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
for stat in top_stats[:10]:
    print(stat)
```

**Solution:**
1. Clear old messages from queues:
   ```python
   # In start_sampleapp.py
   peer_messages[peer_id] = peer_messages[peer_id][-100:]  # Keep last 100
   ```
2. Stop threads on logout:
   ```python
   daemon.stop()
   ```

### Issue: Slow Response Times

**Symptoms:**
- API requests take 5+ seconds

**Cause:** Blocking I/O or lock contention.

**Solution:**
1. Use socket timeouts:
   ```python
   sock.settimeout(1.0)
   ```
2. Reduce lock scope:
   ```python
   with self.lock:
       data = self.get_data()
   # Process data outside lock
   ```

## Network Issues

### Issue: "Connection Refused" on P2P Port

**Symptoms:**
- P2P handshake fails with connection refused

**Cause:** Firewall blocking ports 9100-9199.

**Solution:**
```powershell
# Add firewall rule (Windows, as Administrator)
New-NetFirewallRule -DisplayName "WeApRous P2P" -Direction Inbound -Protocol TCP -LocalPort 9100-9199 -Action Allow
```

### Issue: Can't Connect from Another Device

**Symptoms:**
- Works on localhost but not from phone/tablet

**Cause:** Only binding to 127.0.0.1 (loopback).

**Solution:**
```python
# In start_sampleapp.py
HOST = '0.0.0.0'  # Bind to all interfaces (instead of 'localhost')
```

**Security Warning:** Only do this on trusted networks!

## Browser-Specific Issues

### Issue: Works in Chrome but Not Firefox

**Symptoms:**
- Feature works in Chrome but fails in Firefox

**Cause:** Browser API differences or cookie handling.

**Solution:**
1. Check browser console (F12) for errors
2. Verify `fetch()` API usage:
   ```javascript
   fetch(url, {
       credentials: 'same-origin'  // Ensures cookies sent
   })
   ```

### Issue: "Fetch Failed" in Browser Console

**Symptoms:**
```
TypeError: Failed to fetch
```

**Cause:** CORS issue, network error, or backend down.

**Solution:**
1. Check backend is running
2. Verify proxy forwards requests correctly
3. Check network tab for actual error code

## Debugging Techniques

### Enable Verbose Logging

```python
# In start_sampleapp.py
DEBUG = True

# In daemon/p2p_daemon.py
def send_message(self, to_peer_id, msg_type, body=None):
    if DEBUG:
        print(f"[DEBUG] Sending {msg_type} to {to_peer_id}: {body}")
```

### Monitor Network Traffic

```powershell
# Use Wireshark or tcpdump
# Filter: tcp.port == 9100 or tcp.port == 9001
```

### Check Thread States

```python
import threading
print(f"Active threads: {threading.active_count()}")
for t in threading.enumerate():
    print(f"  - {t.name}: {t.is_alive()}")
```

### Inspect In-Memory State

```python
# Add admin endpoint in start_sampleapp.py
@app.route('/admin/debug')
def debug():
    return {
        'tracker': tracker.get_all_peers(),
        'messages': {k: len(v) for k, v in peer_messages.items()},
        'daemons': {k: v.is_alive() for k, v in p2p_daemons.items()}
    }
```

## Emergency Recovery

### Complete Reset

```powershell
# Kill all processes
taskkill /IM python.exe /F

# Clear logs
Remove-Item *.log -Force

# Restart system
start_all.bat
```

### Backup Current State

```bash
# No persistent state, so just copy code
xcopy /E /I CO3094-weaprous CO3094-weaprous-backup
```

## Getting Help

If issue persists:

1. Check backend logs (terminal running `start_sampleapp.py`)
2. Check browser console (F12 → Console tab)
3. Check network requests (F12 → Network tab)
4. Try with minimal test case (curl commands from TESTING.md)
5. Compare with known working version

## Common Error Messages

| Error | Meaning | Solution |
|-------|---------|----------|
| `Address already in use` | Port occupied | Kill process on that port |
| `Connection refused` | Service not running | Start backend/proxy |
| `Invalid session` | Cookie missing/invalid | Re-login, clear cookies |
| `Peer not found` | Target offline | Wait for peer to come online |
| `Timeout` | No response in 30s | Check network, firewall |
| `400 Bad Request` | Invalid JSON | Fix request body format |
| `401 Unauthorized` | Not logged in | Login first |
| `500 Internal Server Error` | Backend crash | Check logs, restart backend |

## Prevention Best Practices

1. Always start backend before proxy
2. Wait 5 seconds after startup before testing
3. Use `start_all.bat` for consistent startup order
4. Clear cookies between test runs
5. Monitor CPU/memory usage during long sessions
6. Logout before closing browser (clean shutdown)
7. Check port availability before starting
