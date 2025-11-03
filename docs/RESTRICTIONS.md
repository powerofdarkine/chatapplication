# Course Restrictions Compliance Checklist

This document verifies compliance with CO3094 course requirements.

## Frontend Restrictions

### Allowed
- [x] Vanilla HTML5
- [x] Vanilla CSS3
- [x] Vanilla JavaScript (ES6+)
- [x] Fetch API for HTTP requests
- [x] DOM manipulation (getElementById, querySelector, etc.)
- [x] Local browser APIs (localStorage, Audio API, etc.)

### Prohibited
- [ ] NO React, Vue, Angular, Svelte, or any framework
- [ ] NO jQuery or other DOM libraries
- [ ] NO Webpack, Vite, Rollup, or bundlers
- [ ] NO Babel, TypeScript transpilation
- [ ] NO SASS, LESS, or CSS preprocessors
- [ ] NO External CDNs (Google Fonts, Font Awesome, etc.)
- [ ] NO WebSocket API
- [ ] NO WebRTC API
- [ ] NO Socket.IO client
- [ ] NO Axios, Superagent, or HTTP libraries (use fetch)
- [ ] NO Third-party JavaScript libraries

### Verification Commands

Check for prohibited imports in HTML:
```bash
grep -r "cdn\|unpkg\|jsdelivr\|react\|vue\|angular\|jquery" www/*.html static/**/*.html
```

Check for prohibited imports in JS:
```bash
grep -r "import.*from.*node_modules\|require(" static/js/*.js
```

Check for WebSocket usage:
```bash
grep -r "WebSocket\|Socket\|WebRTC\|RTCPeerConnection" static/js/*.js
```

## Backend Restrictions

### Allowed (Python Standard Library Only)
- [x] socket - TCP/UDP sockets
- [x] threading - Thread management
- [x] time - Timestamps and sleep
- [x] json - JSON serialization
- [x] os - File system operations
- [x] sys - System parameters
- [x] base64 - Base64 encoding
- [x] urllib.parse - URL parsing
- [x] mimetypes - MIME type detection
- [x] collections - defaultdict, deque
- [x] uuid - UUID generation
- [x] argparse - CLI argument parsing

### Prohibited
- [ ] NO Flask, Django, FastAPI, Tornado, or web frameworks
- [ ] NO asyncio, aiohttp (must use threading)
- [ ] NO requests, httpx, urllib3 (must use socket)
- [ ] NO websockets, socket.io libraries
- [ ] NO SQLite, PostgreSQL, MySQL drivers (must use in-memory)
- [ ] NO Redis, Memcached
- [ ] NO Celery, RabbitMQ, Kafka
- [ ] NO External authentication libraries (OAuth, JWT)
- [ ] NO Cryptography libraries (use base64 for simple encoding)

### Verification Commands

Check for prohibited imports:
```bash
grep -rE "^import (flask|django|fastapi|tornado|aiohttp|asyncio|requests|websockets|sqlalchemy|redis|jwt)" *.py daemon/*.py
```

Check for async/await usage:
```bash
grep -r "async def\|await " *.py daemon/*.py
```

## Infrastructure Restrictions

### Allowed
- [x] Pure Python HTTP server (custom WeApRous framework)
- [x] Pure Python TCP sockets for P2P
- [x] In-memory data structures (dict, list, deque)
- [x] Threading for concurrency
- [x] Port binding (8080, 9001, 9100-9199)

### Prohibited
- [ ] NO nginx, Apache, or external web servers
- [ ] NO Docker containers (development only)
- [ ] NO External databases (PostgreSQL, MySQL, MongoDB)
- [ ] NO External message queues (RabbitMQ, Kafka, Redis)
- [ ] NO Cloud services (AWS, Azure, GCP APIs)
- [ ] NO VSCode Live Server for production (use Python server)

### Port Configuration Verification

```bash
# Check proxy port
grep -n "PORT.*8080" start_proxy.py

# Check backend port
grep -n "PORT.*9001" start_sampleapp.py

# Check P2P base port
grep -n "P2P_PORT_BASE.*9100" start_sampleapp.py
```

## Protocol Restrictions

### Allowed
- [x] HTTP/1.1 for client-server communication
- [x] TCP sockets for peer-to-peer
- [x] JSON for data serialization
- [x] Cookie-based authentication
- [x] Long-polling for real-time updates

### Prohibited
- [ ] NO WebSocket protocol
- [ ] NO WebRTC (STUN/TURN/ICE)
- [ ] NO Server-Sent Events (SSE)
- [ ] NO QUIC or HTTP/3
- [ ] NO gRPC or Protocol Buffers

### Verification Commands

Check for WebSocket in backend:
```bash
grep -r "websocket\|ws://\|wss://" *.py daemon/*.py
```

Check for SSE:
```bash
grep -r "text/event-stream\|EventSource" *.py daemon/*.py static/js/*.js
```

## Data Storage Restrictions

### Allowed
- [x] In-memory Python dictionaries
- [x] In-memory Python lists
- [x] In-memory deque (for message queues)
- [x] File system for static assets only

### Prohibited
- [ ] NO SQLite or file-based databases
- [ ] NO Pickle persistence
- [ ] NO JSON file storage
- [ ] NO External key-value stores (Redis, Memcached)
- [ ] NO ORM libraries (SQLAlchemy, Django ORM)

### Verification Commands

Check for database imports:
```bash
grep -rE "^import (sqlite3|psycopg2|pymongo|redis|sqlalchemy)" *.py daemon/*.py
```

Check for file I/O on user data:
```bash
grep -r "open.*\.json\|pickle\.dump\|shelve\." *.py daemon/*.py
```

## Authentication Restrictions

### Allowed
- [x] Cookie-based sessions
- [x] Base64 encoded session tokens
- [x] Hardcoded user credentials (for testing)
- [x] Session validation on each request

### Prohibited
- [ ] NO JWT libraries
- [ ] NO OAuth providers
- [ ] NO bcrypt/scrypt/argon2 (use plain text for demo)
- [ ] NO External auth services

### Verification Commands

Check for auth libraries:
```bash
grep -rE "^import (jwt|bcrypt|passlib|oauth)" *.py daemon/*.py
```

## Concurrency Restrictions

### Allowed
- [x] threading.Thread
- [x] threading.Lock
- [x] threading.RLock
- [x] threading.Event
- [x] queue.Queue (if needed)

### Prohibited
- [ ] NO asyncio.create_task
- [ ] NO async/await syntax
- [ ] NO multiprocessing (must use threading)
- [ ] NO gevent or greenlets

### Verification Commands

```bash
grep -rE "^import (asyncio|multiprocessing|gevent)" *.py daemon/*.py
grep -r "async def\|await " *.py daemon/*.py
```

## UI Content Restrictions

### Allowed
- [x] English technical messages
- [x] Plain text status indicators
- [x] CSS-based visual feedback
- [x] System message timestamps

### Prohibited (Removed in Cleanup)
- [ ] NO Emojis in UI text
- [ ] NO Emojis in code comments
- [ ] NO Emojis in system messages
- [ ] NO Unicode decorative characters

### Verification Commands

```bash
# Check for emoji Unicode ranges
grep -rP "[\x{1F600}-\x{1F64F}\x{1F300}-\x{1F5FF}\x{1F680}-\x{1F6FF}\x{2600}-\x{26FF}\x{2700}-\x{27BF}]" www/*.html static/**/*.js static/**/*.css *.py daemon/*.py
```

## Static Asset Restrictions

### Allowed
- [x] Local CSS files in static/css/
- [x] Local JavaScript files in static/js/
- [x] Local images in static/images/
- [x] Local fonts in static/fonts/ (if any)

### Prohibited
- [ ] NO CDN links (cdnjs, unpkg, jsdelivr)
- [ ] NO Google Fonts
- [ ] NO Font Awesome icons
- [ ] NO Bootstrap CSS/JS
- [ ] NO External image hosting

### Verification Commands

```bash
grep -r "https://\|http://" www/*.html | grep -v "localhost"
```

## Testing Restrictions

### Allowed
- [x] Manual testing with browsers
- [x] curl for HTTP endpoint testing
- [x] netcat for TCP socket testing
- [x] Python unittest (if needed)

### Prohibited
- [ ] NO Selenium or browser automation (for assignment)
- [ ] NO Puppeteer/Playwright
- [ ] NO Load testing tools (Apache Bench, wrk)
- [ ] NO External CI/CD (for assignment)

## Compliance Summary

Run all verification commands:

```bash
# Full compliance check
./scripts/check_compliance.sh
```

Expected output:
```
[PASS] No forbidden frontend libraries
[PASS] No forbidden backend libraries
[PASS] No WebSocket/WebRTC usage
[PASS] No async/await syntax
[PASS] No external databases
[PASS] No CDN links
[PASS] No emojis in code
[PASS] Port configuration correct (8080/9001/9100-9199)

Compliance: 8/8 checks passed
```

## Exceptions & Clarifications

1. **Base64 for Sessions**: Using base64 encoding for session tokens (not encryption, just encoding).
2. **Threading**: Allowed and required for concurrent connections.
3. **Socket Timeouts**: Using socket.settimeout() for non-blocking I/O.
4. **JSON**: Standard library json module is allowed and required.
5. **No NAT Traversal**: P2P works on local network only (acceptable limitation).

## Audit Trail

- **Date**: 2025-11-03
- **Auditor**: Development Team
- **Status**: COMPLIANT
- **Version**: 1.1-clean
- **Next Review**: Before submission
