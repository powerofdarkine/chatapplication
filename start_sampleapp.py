#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
start_sampleapp
~~~~~~~~~~~~~~~~~

This module provides a sample RESTful web application using the WeApRous framework.

It defines basic route handlers and launches a TCP-based backend server to serve
HTTP requests. The application includes a login endpoint and a greeting endpoint,
and can be configured via command-line arguments.
"""

import json
import base64
import os
import time
import threading
from collections import defaultdict, deque
import argparse

from daemon.weaprous import WeApRous
from daemon.tracker import get_tracker
from daemon.p2p_daemon import P2PDaemon
from daemon.cookies import Cookie
from daemon.http_consts import HEADER_CONTENT_TYPE, HEADER_LOCATION, HEADER_WWW_AUTHENTICATE, DEFAULT_IP, DEFAULT_SERVER_PORT, P2P_PORT_BASE

app = WeApRous()

# Get global tracker instance
tracker = get_tracker()

# P2P daemon instances per user
p2p_daemons = {}  # username -> P2PDaemon
p2p_daemon_lock = threading.RLock()

# Connection requests storage
connection_requests = defaultdict(list)  # target_peer -> [{'from': requester, 'timestamp': ...}]
connection_requests_lock = threading.RLock()

# Connection responses storage (accept/reject notifications)
connection_responses = defaultdict(list)  # requester_peer -> [{'from': acceptor, 'status': 'accepted'/'rejected', 'timestamp': ...}]
connection_responses_lock = threading.RLock()

# Message queues for each user (for browser polling)
message_queues = defaultdict(lambda: deque(maxlen=100))  # username -> deque<msg>
message_lock = threading.RLock()

USERS = {
    'admin' : 'password',
    'user1' : 'pass123',
    'user2' : 'pass456'
}

@app.route('/login', methods=['POST'])
def handle_login(headers, body, username=None):
    """
    Handle user login via POST request.

    This route simulates a login process and prints the provided headers and body
    to the console.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or login payload.
    """
    print("[SampleApp] Logging in {} to {}".format(headers, body))

    params = {}
    if body:
        for pair in body.split('&'):
            try:
                key, value = pair.split('=', 1)
                from urllib.parse import unquote
                params[unquote(key)] = unquote(value)
            except ValueError:
                pass

    username = params.get('username', '').strip()
    password = params.get('password', '').strip()

    print(f"[SampleApp] Login attemp - username: '{username}'")

    if username in USERS and USERS[username] == password:
        print(f"[SampleApp] Login Success for '{username}'")

        auth_token = base64.b64encode(f"{username}:{password}".encode()).decode()

        return {
            'status': 302,
            'headers' : {
                HEADER_LOCATION: '/',
                HEADER_CONTENT_TYPE: 'text/html; charset=utf-8'
            },
            'cookies': {
                'auth': Cookie('auth', auth_token, '/', 3600, True, False),
                'username': Cookie('username', username, '/', 3600, False, False)
            },
            'body': '<html><body>Redirecting...</body></html>'
        }
    else:
        print(f"[SampleApp] Login Failed for '{username}'")

        error_html = load_html('login_error.html')

        return {
            'status': 401,
            'headers': {
                HEADER_CONTENT_TYPE: 'text/html; charset=utf-8',
                HEADER_WWW_AUTHENTICATE: 'Form realm="Login Required"'
            },
            'body': error_html
        }

@app.route('/logout', methods=['GET', 'POST'])
def handle_logout(headers, body, username=None):
    """
    Handle logout - clear cookies, cleanup P2P, and redirect to login.
    """
    print(f"[SampleApp] Logout for user '{username}'")
    
    try:
        # Unregister peer from tracker (this broadcasts peer-left event)
        tracker.unregister_peer(username)
        
        # Stop P2P daemon if exists
        with p2p_daemon_lock:
            if username in p2p_daemons:
                daemon = p2p_daemons[username]
                daemon.stop()
                del p2p_daemons[username]
                print(f"[SampleApp] P2P daemon stopped for '{username}'")
        
        # Clear message queue
        with message_lock:
            if username in message_queues:
                del message_queues[username]
    
    except Exception as e:
        print(f"[SampleApp] Error during logout cleanup: {e}")
    
    return {
        'status': 302,
        'headers': {
            HEADER_LOCATION: '/login.html',
            HEADER_CONTENT_TYPE: 'text/html; charset=utf-8'
        },
        'cookies': {
            'auth': 'deleted; Max-Age=0',
            'username': 'deleted; Max-Age=0'
        },
        'body': '<html><body>Logging out...</body></html>'
    }

@app.route('/api/user', methods=['GET'])
def get_user_info(headers, body, username=None):
    """
    API endpoint - return current user info (for Task 2 P2P chat).
    Requires authentication.
    """
    return {
        'status': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'username': username,
            'authenticated': True,
            'timestamp': __import__('datetime').datetime.utcnow().isoformat()
        })
    }

def get_or_create_p2p_daemon(username):
    """Return a per-user P2PDaemon, creating and starting it if needed.

    Each user is assigned a deterministic P2P port calculated from
    ``P2P_PORT_BASE`` plus the user's index in the sorted user list. The
    created daemon is started and callbacks are wired to enqueue messages
    into the application's browser-polling queues.

    Args:
        username (str): Application username for which to obtain the daemon.

    Returns:
        P2PDaemon: Running daemon instance associated with ``username``.
    """
    global p2p_daemons
    
    with p2p_daemon_lock:
        if username in p2p_daemons:
            return p2p_daemons[username]
        
        # Assign port based on user index
        user_list = sorted(USERS.keys())
        try:
            user_index = user_list.index(username)
        except ValueError:
            user_index = len(user_list)
        
        p2p_port = P2P_PORT_BASE + user_index
        
        # Create daemon
        daemon = P2PDaemon('0.0.0.0', p2p_port, username)
        
        # Set callbacks
        def on_message(from_peer, to_peer, msg):
            # Queue message for browser polling
            with message_lock:
                message_queues[username].append(msg)
            print(f"[P2P-Queue] Message from '{from_peer}' queued for '{username}'")
        
        def on_peer_connected(peer_id):
            print(f"[P2P] '{username}' connected to '{peer_id}'")
        
        def on_peer_disconnected(peer_id):
            print(f"[P2P] '{username}' disconnected from '{peer_id}'")
        
        daemon.on_message = on_message
        daemon.on_peer_connected = on_peer_connected
        daemon.on_peer_disconnected = on_peer_disconnected
        
        # Start daemon
        daemon.start()
        
        p2p_daemons[username] = daemon
        
        print(f"[SampleApp] P2P daemon created for '{username}' on port {p2p_port}")
        
        return daemon


@app.route('/api/submit-info', methods=['POST'])
def submit_peer_info(headers, body, username=None):
    """
    Register peer information after login (Task 2 P2P).
    POST /api/submit-info with JSON: {port, display_name}
    
    Now automatically starts P2P daemon for this user.
    """
    print(f"[Debug] Body received: {repr(body)}")
    print(f"[Debug] Body type: {type(body)}")
    try:
        data = json.loads(body) if body else {}
        
        # Get or create P2P daemon for this user
        daemon = get_or_create_p2p_daemon(username)
        
        # Use daemon's port
        p2p_port = daemon.port
        
        # Extract client IP from headers (added by proxy/adapter)
        client_ip = headers.get('X-Forwarded-For', '127.0.0.1')
        if ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Register peer with tracker (returns dict)
        peer_dict = tracker.register_peer(
            peer_id=username,
            ip=client_ip,
            port=p2p_port,
            display_name=data.get('display_name', username)
        )
        
        # Event already broadcasted internally by register_peer
        
        print(f"[SampleApp] Peer registered: {username} at {client_ip}:{p2p_port}")
        
        return {
            'status': 200,
            'headers': {HEADER_CONTENT_TYPE: 'application/json'},
            'body': json.dumps({
                'status': 'success',
                'peer_id': peer_dict['peer_id'],
                'p2p_port': p2p_port,
                'message': 'Peer registered and P2P daemon started'
            })
        }
    except Exception as e:
        print(f"[SampleApp] submit-info error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

@app.route('/api/get-list', methods=['GET'])
def get_peer_list(headers, body, username=None):
    """
    Get list of online peers (Task 2 P2P).
    GET /api/get-list returns: {peers: [{peer_id, display_name, ip, port, status}, ...]}
    """
    try:
        # get_peers returns list of dicts (not Peer objects)
        peer_list = tracker.get_peers(exclude_peer=username)
        
        print(f"[SampleApp] get-list for {username}: {len(peer_list)} peers")
        
        return {
            'status': 200,
            'headers': {HEADER_CONTENT_TYPE: 'application/json'},
            'body': json.dumps({
                'peers': peer_list,
                'server_time': int(time.time() * 1000)
            })
        }
    except Exception as e:
        print(f"[SampleApp] get-list error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

@app.route('/api/connect-peer', methods=['POST'])
def connect_peer(headers, body, username=None):
    """
    Get connection info for specific peer (Task 2 P2P).
    POST /api/connect-peer with JSON: {from_peer, to_peer}
    Returns: {to_peer_addr: {ip, port}, nonce}
    """
    try:
        data = json.loads(body) if body else {}
        to_peer = data.get('to_peer')
        from_peer = data.get('from_peer', username)
        
        if not to_peer:
            return {
                'status': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'to_peer required'})
            }
        
        # Get peer address from tracker
        peer_addr = tracker.get_peer_address(to_peer)
        
        if not peer_addr:
            return {
                'status': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Peer not found or offline'})
            }
        
        # Generate connection nonce
        nonce = tracker.generate_nonce()
        
        print(f"[SampleApp] connect-peer: {from_peer} → {to_peer}")
        
        return {
            'status': 200,
            'headers': {HEADER_CONTENT_TYPE: 'application/json'},
            'body': json.dumps({
                'to_peer_addr': peer_addr,
                'nonce': nonce
            })
        }
    except Exception as e:
        print(f"[SampleApp] connect-peer error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

@app.route('/api/broadcast-peer', methods=['POST'])
def broadcast_peer_events(headers, body, username=None):
    """
    Long-poll for peer events (Task 2 P2P).
    POST /api/broadcast-peer with JSON: {peer_id, since}
    Returns: {events: [{type, peer, ts}, ...]}
    """
    try:
        data = json.loads(body) if body else {}
        since_ts = data.get('since', 0)
        
        # Get events since timestamp (non-blocking for now)
        events = tracker.get_events(username, since_ts)
        
        print(f"[SampleApp] broadcast-peer for {username}: {len(events)} events since {since_ts}")
        
        return {
            'status': 200,
            'headers': {HEADER_CONTENT_TYPE: 'application/json'},
            'body': json.dumps({'events': events})
        }
    except Exception as e:
        print(f"[SampleApp] broadcast-peer error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat(headers, body, username=None):
    """
    Update peer heartbeat (Task 2 P2P).
    POST /api/heartbeat with JSON: {peer_id, ts}
    Returns: {expired_peers, server_time}
    """
    try:
        # Update heartbeat timestamp
        success = tracker.heartbeat(username)
        
        if not success:
            return {
                'status': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Peer not registered'})
            }
        
        # Get list of expired peers
        expired = tracker.get_expired_peers()
        
        print(f"[SampleApp] heartbeat from {username}, expired: {expired}")
        
        return {
            'status': 200,
            'headers': {HEADER_CONTENT_TYPE: 'application/json'},
            'body': json.dumps({
                'expired_peers': expired,
                'server_time': int(time.time() * 1000)
            })
        }
    except Exception as e:
        print(f"[SampleApp] heartbeat error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

# Legacy endpoint aliases for compatibility
@app.route('/api/peers', methods=['GET'])
def get_peers(headers, body, username=None):
    """Alias for /api/get-list"""
    return get_peer_list(headers, body, username)

@app.route('/api/p2p-request', methods=['POST'])
def p2p_request(headers, body, username=None):
    """
    Send connection request to a peer.
    POST /api/p2p-request with JSON: {to_peer}
    Returns: {status, message}
    """
    try:
        data = json.loads(body) if body else {}
        to_peer = data.get('to_peer')
        
        if not to_peer:
            return {
                'status': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'to_peer required'})
            }
        
        # Get peer info from tracker
        peer_info = tracker.get_peer(to_peer)
        if not peer_info or peer_info['status'] != 'ONLINE':
            return {
                'status': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Peer not found or offline'})
            }
        
        # Add connection request
        with connection_requests_lock:
            connection_requests[to_peer].append({
                'from': username,
                'timestamp': time.time()
            })
        
        print(f"[SampleApp] '{username}' sent connection request to '{to_peer}'")
        
        return {
            'status': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'request_sent',
                'message': f'Connection request sent to {to_peer}'
            })
        }
    
    except Exception as e:
        print(f"[SampleApp] p2p-request error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

@app.route('/api/p2p-get-requests', methods=['GET'])
def p2p_get_requests(headers, body, username=None):
    """
    Get pending connection requests for current user.
    Returns: {requests: [{from, timestamp}]}
    """
    try:
        with connection_requests_lock:
            requests = connection_requests.get(username, [])
            # Clean old requests (older than 5 minutes)
            current_time = time.time()
            valid_requests = [r for r in requests if current_time - r['timestamp'] < 300]
            connection_requests[username] = valid_requests
            
            return {
                'status': 200,
                'headers': {HEADER_CONTENT_TYPE: 'application/json'},
                'body': json.dumps({'requests': valid_requests})
                }
    
    except Exception as e:
        print(f"[SampleApp] p2p-get-requests error: {e}")
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

@app.route('/api/p2p-accept', methods=['POST'])
def p2p_accept(headers, body, username=None):
    """
    Accept connection request and establish P2P connection.
    POST /api/p2p-accept with JSON: {from_peer}
    Returns: {status, message}
    """
    try:
        data = json.loads(body) if body else {}
        from_peer = data.get('from_peer')
        
        if not from_peer:
            return {
                'status': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'from_peer required'})
            }
        
        # Remove the request
        with connection_requests_lock:
            if username in connection_requests:
                connection_requests[username] = [
                    r for r in connection_requests[username] 
                    if r['from'] != from_peer
                ]
        
        # Get peer info from tracker
        peer_info = tracker.get_peer(from_peer)
        if not peer_info or peer_info['status'] != 'ONLINE':
            return {
                'status': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Peer not found or offline'})
            }
        
        # Get P2P daemon for this user (acceptor)
        daemon = get_or_create_p2p_daemon(username)
        
        # Generate nonce
        nonce = tracker.generate_nonce()
        
        # Connect to peer (acceptor initiates the socket connection)
        success = daemon.connect_to_peer(
            remote_ip=peer_info['ip'],
            remote_port=peer_info['port'],
            remote_peer_id=from_peer,
            nonce=nonce
        )
        
        if success:
            # Notify the requester about acceptance
            with connection_responses_lock:
                connection_responses[from_peer].append({
                    'from': username,
                    'status': 'accepted',
                    'timestamp': time.time()
                })
            
            print(f"[SampleApp] '{username}' accepted connection from '{from_peer}'")
            return {
                'status': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'connected',
                    'peer': from_peer,
                    'message': f'Connection accepted, P2P established with {from_peer}'
                })
            }
        else:
            return {
                'status': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to establish P2P connection'})
            }
    
    except Exception as e:
        print(f"[SampleApp] p2p-accept error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

@app.route('/api/p2p-get-responses', methods=['GET'])
def p2p_get_responses(headers, body, username=None):
    """
    Get connection responses (accept/reject notifications) for current user.
    Returns: {responses: [{from, status, timestamp}]}
    """
    try:
        with connection_responses_lock:
            responses = connection_responses.get(username, [])
            # Clean old responses (older than 5 minutes)
            current_time = time.time()
            valid_responses = [r for r in responses if current_time - r['timestamp'] < 300]
            
            # Clear after reading
            connection_responses[username] = []
            
            return {
                'status': 200,
                'headers': {HEADER_CONTENT_TYPE: 'application/json'},
                'body': json.dumps({'responses': valid_responses})
            }
    
    except Exception as e:
        print(f"[SampleApp] p2p-get-responses error: {e}")
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

@app.route('/api/p2p-reject', methods=['POST'])
def p2p_reject(headers, body, username=None):
    """
    Reject connection request.
    POST /api/p2p-reject with JSON: {from_peer}
    Returns: {status, message}
    """
    try:
        data = json.loads(body) if body else {}
        from_peer = data.get('from_peer')
        
        if not from_peer:
            return {
                'status': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'from_peer required'})
            }
        
        # Remove the request
        with connection_requests_lock:
            if username in connection_requests:
                connection_requests[username] = [
                    r for r in connection_requests[username] 
                    if r['from'] != from_peer
                ]
        
        # Notify the requester about rejection
        with connection_responses_lock:
            connection_responses[from_peer].append({
                'from': username,
                'status': 'rejected',
                'timestamp': time.time()
            })
        
        print(f"[SampleApp] '{username}' rejected connection from '{from_peer}'")
        
        return {
            'status': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'rejected',
                'message': f'Connection request from {from_peer} rejected'
            })
        }
    
    except Exception as e:
        print(f"[SampleApp] p2p-reject error: {e}")
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

@app.route('/api/p2p-connect', methods=['POST'])
def p2p_connect(headers, body, username=None):
    """
    Initiate P2P connection to a peer.
    POST /api/p2p-connect with JSON: {to_peer}
    
    Returns:
        {status, message}
    """
    try:
        data = json.loads(body) if body else {}
        to_peer = data.get('to_peer')
        
        if not to_peer:
            return {
                'status': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'to_peer required'})
            }
        
        # Get peer info from tracker
        peer_info = tracker.get_peer(to_peer)
        if not peer_info or peer_info['status'] != 'ONLINE':
            return {
                'status': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Peer not found or offline'})
            }
        
        # Get P2P daemon for this user
        daemon = get_or_create_p2p_daemon(username)
        
        # Generate nonce
        nonce = tracker.generate_nonce()
        
        # Connect to peer
        success = daemon.connect_to_peer(
            remote_ip=peer_info['ip'],
            remote_port=peer_info['port'],
            remote_peer_id=to_peer,
            nonce=nonce
        )
        
        if success:
            print(f"[SampleApp] '{username}' connected to '{to_peer}'")
            return {
                'status': 200,
                'headers': {HEADER_CONTENT_TYPE: 'application/json'},
                'body': json.dumps({
                    'status': 'connected',
                    'peer': to_peer,
                    'message': f'P2P connection established to {to_peer}'
                })
            }
        else:
            return {
            'status': 200,
            'headers': {HEADER_CONTENT_TYPE: 'application/json'},
            'body': json.dumps({'error': str(e)})
        }
    
    except Exception as e:
        print(f"[SampleApp] p2p-connect error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 200,
            'headers': {HEADER_CONTENT_TYPE: 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


@app.route('/api/p2p-send', methods=['POST'])
def p2p_send(headers, body, username=None):
    """
    Send P2P message to a peer.
    POST /api/p2p-send with 
    
    Args:
        body ({to_peer, message, type})

    Returns:
        {status, message}
    """
    try:
        data = json.loads(body) if body else {}
        to_peer = data.get('to_peer')
        message = data.get('message', '')
        msg_type = data.get('type', 'CHAT')
        
        if not to_peer:
            return {
                'status': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'to_peer required'})
            }
        
        # Get P2P daemon for this user
        with p2p_daemon_lock:
            daemon = p2p_daemons.get(username)
        
        if not daemon:
            return {
                'status': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'P2P daemon not initialized. Call /api/submit-info first.'})
            }
        
        # Send message via P2P (support both CHAT and CLOSE types)
        success = daemon.send_message(to_peer, message, msg_type)
        
        if success:
            print(f"[SampleApp] '{username}' sent {msg_type} to '{to_peer}'")
            return {
                'status': 200,
                'headers': {HEADER_CONTENT_TYPE: 'application/json'},
                'body': json.dumps({
                    'status': 'sent',
                    'timestamp': int(time.time() * 1000)
                })
            }
        else:
            return {
                'status': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to send message (not connected to peer?)'})
            }
    
    except Exception as e:
        print(f"[SampleApp] p2p-send error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


@app.route('/api/p2p-receive', methods=['POST'])
def p2p_receive(headers, body, username=None):
    """
    Poll for incoming P2P messages.
    POST /api/p2p-receive (optional JSON: {since: timestamp})
    Returns: {messages: [{from, to, body, timestamp, msg_id}, ...]}
    """
    try:
        data = json.loads(body) if body else {}
        since_ts = data.get('since', 0)
        
        # Get messages from queue
        with message_lock:
            queue = message_queues[username]
            messages = [msg for msg in queue if msg.get('timestamp', 0) > since_ts]
        
        print(f"[SampleApp] '{username}' polled {len(messages)} messages")
        
        return {
            'status': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'messages': messages,
                'server_time': int(time.time() * 1000)
            })
        }
    
    except Exception as e:
        print(f"[SampleApp] p2p-receive error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


@app.route('/api/p2p-disconnect', methods=['POST'])
def p2p_disconnect(headers, body, username=None):
    """
    Disconnect from a peer.
    POST /api/p2p-disconnect with JSON: {peer}
    """
    try:
        data = json.loads(body) if body else {}
        peer = data.get('peer')
        
        if not peer:
            return {
                'status': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'peer required'})
            }
        
        # Get P2P daemon
        with p2p_daemon_lock:
            daemon = p2p_daemons.get(username)
        
        if daemon:
            daemon.disconnect_peer(peer)
            print(f"[SampleApp] '{username}' disconnected from '{peer}'")
        
        return {
            'status': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'disconnected'})
        }
    
    except Exception as e:
        print(f"[SampleApp] p2p-disconnect error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


@app.route('/api/p2p-status', methods=['GET'])
def p2p_status(headers, body, username=None):
    """
    Get P2P daemon status and active connections.
    GET /api/p2p-status
    Returns: {daemon_running, port, active_connections: [peer_ids]}
    """
    try:
        with p2p_daemon_lock:
            daemon = p2p_daemons.get(username)
        
        if daemon:
            return {
                'status': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'daemon_running': daemon.running,
                    'port': daemon.port,
                    'peer_id': daemon.peer_id,
                    'active_connections': daemon.get_active_connections()
                })
            }
        else:
            return {
                'status': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'daemon_running': False,
                    'message': 'P2P daemon not initialized'
                })
            }
    
    except Exception as e:
        print(f"[SampleApp] p2p-status error: {e}")
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

def load_html(filename):
    """
    Helper function to load HTML files.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    filename = filename.replace('./', '').replace('www/', '')
    
    # Build full path
    filepath = os.path.join(base_dir, 'www', filename)
    
    print(f"[SampleApp] Loading HTML from: {filepath}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"[SampleApp] Loaded {len(content)} bytes from {filename}")
            return content
    except FileNotFoundError:
        print(f"[SampleApp] File not found: {filepath}")
        return f'<html><body><h1>Error</h1><p>File {filename} not found at {filepath}</p></body></html>'
    except Exception as e:
        print(f"[SampleApp] Error loading {filename}: {e}")
        return f'<html><body><h1>Error</h1><p>Error loading {filename}: {e}</p></body></html>'


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='SampleApp',
        description='WeApRous sample application with authentication',
        epilog='Task 1 & 2 implementation'
    )
    parser.add_argument('--server-ip', default=DEFAULT_IP)
    parser.add_argument('--server-port', type=int, default=DEFAULT_SERVER_PORT)
 
    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port

    print(f"[SampleApp] Starting on {ip}:{port}")
    print(f"[SampleApp] Available users: {list(USERS.keys())}")
    
    app.prepare_address(ip, port)
    app.run()