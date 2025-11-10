"""
daemon.p2p_daemon
~~~~~~~~~~~~~~~~~

P2P TCP daemon for direct peer-to-peer messaging.
Handles incoming P2P connections, handshake protocol, and message routing.

Protocol:
---------
1. Handshake:
   - Client: CONNECT <to_peer_id> <from_peer_id> <nonce>\\n
   - Server: ACCEPT <to_peer_id> <from_peer_id> <nonce>\\n
   - Or: REJECT <reason>\\n

2. Message format (JSON per line):
   {
     "type": "CHAT|PING|PONG|CLOSE",
     "msg_id": "uuid",
     "from": "peer_id",
     "to": "peer_id",
     "timestamp": epoch_ms,
     "body": "message text"
   }

3. Keepalive: PING/PONG every 10s, timeout after 30s idle
"""

import socket
import threading
import json
import time
import uuid

class P2PConnection:
    """Represents an active P2P connection."""
    
    def __init__(self, conn, addr, peer_id, remote_peer_id):
        """Create a connection wrapper for an active P2P socket.

        Args:
            conn: the socket object for this connection.
            addr: remote address tuple (ip, port).
            peer_id: local peer id (owner of this daemon).
            remote_peer_id: remote peer id for the connection.
        """
        self.conn = conn
        self.addr = addr
        self.peer_id = peer_id  # Local peer
        self.remote_peer_id = remote_peer_id  # Remote peer
        self.last_activity = time.time()
        self.closed = False
        self.lock = threading.Lock()
    
    def send_line(self, line):
        """Send a single line (terminated by '\n') to the remote peer.

        Returns True on success, False on failure. Updates last_activity when
        a send succeeds and marks the connection closed on error.
        """
        with self.lock:
            if not self.closed:
                try:
                    self.conn.sendall(line.encode('utf-8'))
                    self.last_activity = time.time()
                    return True
                except Exception as e:
                    print(f"[P2P] Error sending to {self.remote_peer_id}: {e}")
                    self.closed = True
                    return False
            return False
    
    def close(self):
        """Close the underlying socket and mark the connection closed."""
        with self.lock:
            if not self.closed:
                self.closed = True
                try:
                    self.conn.close()
                except:
                    pass


class P2PDaemon:
    """P2P daemon that manages peer-to-peer TCP connections.

    The daemon listens for incoming P2P connections, performs a simple
    CONNECT/ACCEPT handshake, tracks active peer connections, and runs a
    message-processing loop per connection. It also provides methods for
    initiating outbound connections to peers.

    Attributes:
        ip (str): Bind address for the daemon.
        port (int): Listening port for peer connections.
        peer_id (str): Local peer identifier.
        connections (dict): Mapping remote_peer_id -> P2PConnection.
    """
    
    HANDSHAKE_TIMEOUT = 3  # seconds
    KEEPALIVE_INTERVAL = 10  # seconds
    IDLE_TIMEOUT = 30  # seconds
    
    def __init__(self, ip: str, port: int, peer_id: str):
        """
        Initialize P2P daemon.
        
        Args:
            ip (str): IP to bind (usually 0.0.0.0 or 127.0.0.1)
            port (int): Port to listen for P2P connections
            peer_id (str): This peer's ID
        """
        self.ip = ip
        self.port = port
        self.peer_id = peer_id
        
        self.connections = {}  # remote_peer_id -> P2PConnection
        self.lock = threading.RLock()
        
        self.running = False
        self.server_socket = None
        self.accept_thread = None
        self.keepalive_thread = None
        
        # Message handlers
        self.on_message = None  # Callback: on_message(from_peer, to_peer, msg_dict)
        self.on_peer_connected = None  # Callback: on_peer_connected(peer_id)
        self.on_peer_disconnected = None  # Callback: on_peer_disconnected(peer_id)
        
        print(f"[P2P] Daemon initialized for peer '{peer_id}' on {ip}:{port}")
    
    def start(self):
        """Start the daemon: bind socket, start accept and keepalive threads.

        Raises:
            Exception: If socket bind/listen fails.
        """
        if self.running:
            print(f"[P2P] Daemon already running")
            return
        
        self.running = True
        
        # Create server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.ip, self.port))
            self.server_socket.listen(10)
            print(f"[P2P] Listening on {self.ip}:{self.port}")
            
            # Start accept thread
            self.accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
            self.accept_thread.start()
            
            # Start keepalive thread
            self.keepalive_thread = threading.Thread(target=self._keepalive_loop, daemon=True)
            self.keepalive_thread.start()
            
            print(f"[P2P] Daemon started successfully")
            
        except Exception as e:
            print(f"[P2P] Failed to start daemon: {e}")
            self.running = False
            raise
    
    def stop(self):
        """Stop the daemon and clean up all resources.

        This method stops background loops, closes all active peer
        connections and closes the listening socket.
        """
        if not self.running:
            return
        
        print(f"[P2P] Stopping daemon...")
        self.running = False
        
        # Close all connections
        with self.lock:
            for peer_id, conn in list(self.connections.items()):
                conn.close()
            self.connections.clear()
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        print(f"[P2P] Daemon stopped")
    
    def _accept_loop(self):
        """Loop that accepts incoming TCP connections and spawns handlers.

        Runs until ``self.running`` is cleared.
        """
        print(f"[P2P] Accept loop started")
        
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                conn, addr = self.server_socket.accept()
                
                print(f"[P2P] Incoming connection from {addr}")
                
                # Handle in separate thread
                thread = threading.Thread(
                    target=self._handle_incoming_connection,
                    args=(conn, addr),
                    daemon=True
                )
                thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[P2P] Error accepting connection: {e}")
                break
    
    def _handle_incoming_connection(self, conn, addr):
        """Perform handshake and integrate an accepted connection.

        The expected handshake is: ``CONNECT <to_peer> <from_peer> <nonce>``.
        If the handshake is valid and targeted at this daemon, the method
        replies with ``ACCEPT`` and schedules the message loop for the
        new connection.
        """
        try:
            conn.settimeout(self.HANDSHAKE_TIMEOUT)
            
            # Read handshake line
            handshake = self._read_line(conn)
            if not handshake:
                print(f"[P2P] No handshake from {addr}")
                conn.close()
                return
            
            # Parse: CONNECT <to_peer> <from_peer> <nonce>
            parts = handshake.strip().split()
            if len(parts) != 4 or parts[0] != 'CONNECT':
                print(f"[P2P] Invalid handshake from {addr}: {handshake}")
                conn.sendall(b"REJECT Invalid handshake format\n")
                conn.close()
                return
            
            _, to_peer, from_peer, nonce = parts
            
            # Verify this connection is for us
            if to_peer != self.peer_id:
                print(f"[P2P] Connection for '{to_peer}' but I am '{self.peer_id}'")
                conn.sendall(b"REJECT Wrong peer\n")
                conn.close()
                return
            
            # Accept connection
            response = f"ACCEPT {to_peer} {from_peer} {nonce}\n"
            conn.sendall(response.encode('utf-8'))
            
            print(f"[P2P] Accepted connection from '{from_peer}'")
            
            # Create P2P connection object
            p2p_conn = P2PConnection(conn, addr, self.peer_id, from_peer)
            
            with self.lock:
                # Close existing connection if any
                if from_peer in self.connections:
                    print(f"[P2P] Closing old connection with '{from_peer}'")
                    self.connections[from_peer].close()
                
                self.connections[from_peer] = p2p_conn
            
            # Notify callback
            if self.on_peer_connected:
                try:
                    self.on_peer_connected(from_peer)
                except Exception as e:
                    print(f"[P2P] Error in on_peer_connected callback: {e}")
            
            # Start message loop
            self._message_loop(p2p_conn)
            
        except socket.timeout:
            print(f"[P2P] Handshake timeout from {addr}")
        except Exception as e:
            print(f"[P2P] Error handling incoming connection: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                conn.close()
            except:
                pass
    
    def connect_to_peer(self, remote_ip, remote_port, remote_peer_id, nonce):
        """Initiate an outbound connection and perform handshake.

        Args:
            remote_ip (str): Remote peer's IP address.
            remote_port (int): Remote peer's listening port.
            remote_peer_id (str): Remote peer's declared ID.
            nonce (str): Handshake nonce used for validation.

        Returns:
            bool: True on successful connection and handshake, False otherwise.
        """
        print(f"[P2P] Connecting to '{remote_peer_id}' at {remote_ip}:{remote_port}")
        
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.settimeout(self.HANDSHAKE_TIMEOUT)
            
            # Connect
            conn.connect((remote_ip, remote_port))
            
            # Send handshake
            handshake = f"CONNECT {remote_peer_id} {self.peer_id} {nonce}\n"
            conn.sendall(handshake.encode('utf-8'))
            
            # Wait for response
            response = self._read_line(conn)
            if not response:
                print(f"[P2P] No handshake response from '{remote_peer_id}'")
                conn.close()
                return False
            
            # Parse response
            parts = response.strip().split()
            if len(parts) >= 1 and parts[0] == 'ACCEPT':
                print(f"[P2P] Connected to '{remote_peer_id}'")
                
                # Create P2P connection
                p2p_conn = P2PConnection(conn, (remote_ip, remote_port), self.peer_id, remote_peer_id)
                
                with self.lock:
                    # Close old connection if any
                    if remote_peer_id in self.connections:
                        self.connections[remote_peer_id].close()
                    
                    self.connections[remote_peer_id] = p2p_conn
                
                # Notify callback
                if self.on_peer_connected:
                    try:
                        self.on_peer_connected(remote_peer_id)
                    except Exception as e:
                        print(f"[P2P] Error in on_peer_connected callback: {e}")
                
                # Start message loop in separate thread
                thread = threading.Thread(
                    target=self._message_loop,
                    args=(p2p_conn,),
                    daemon=True
                )
                thread.start()
                
                return True
            
            elif parts[0] == 'REJECT':
                reason = ' '.join(parts[1:])
                print(f"[P2P] Connection rejected by '{remote_peer_id}': {reason}")
                conn.close()
                return False
            
            else:
                print(f"[P2P] Invalid handshake response: {response}")
                conn.close()
                return False
        
        except socket.timeout:
            print(f"[P2P] Connection timeout to '{remote_peer_id}'")
            return False
        except Exception as e:
            print(f"[P2P] Error connecting to '{remote_peer_id}': {e}")
            return False
    
    def send_message(self, to_peer, body, msg_type='CHAT'):
        """Send a JSON-line message to a connected peer.

        Args:
            to_peer (str): Target peer ID.
            body (str): Message body (for CHAT) or empty for control messages.
            msg_type (str): One of 'CHAT', 'PING', 'PONG', 'CLOSE'.

        Returns:
            bool: True if the message was queued/sent successfully.
        """
        with self.lock:
            conn = self.connections.get(to_peer)
            
            if not conn:
                print(f"[P2P] No connection to '{to_peer}'")
                return False
            
            # Build message
            msg = {
                'type': msg_type,
                'from': self.peer_id,
                'to': to_peer,
                'timestamp': int(time.time() * 1000)
            }
            
            if msg_type == 'CHAT':
                msg['msg_id'] = str(uuid.uuid4())
                msg['body'] = body
            elif msg_type == 'CLOSE':
                # CLOSE messages can have optional body (e.g., '__SESSION_ENDED__')
                if body:
                    msg['body'] = body
            
            # Send as JSON line
            line = json.dumps(msg) + '\n'
            success = conn.send_line(line)
            
            if success:
                print(f"[P2P] Sent {msg_type} to '{to_peer}'")
            else:
                print(f"[P2P] Failed to send to '{to_peer}'")
            
            return success
    
    def disconnect_peer(self, peer_id):
        """Gracefully disconnect and remove a peer connection.

        Sends a CLOSE message, closes the socket, removes from internal
        map and notifies the on_peer_disconnected callback.
        """
        with self.lock:
            conn = self.connections.get(peer_id)
            
            if conn:
                # Send CLOSE message
                self.send_message(peer_id, '', 'CLOSE')
                
                # Close connection
                conn.close()
                del self.connections[peer_id]
                
                print(f"[P2P] Disconnected from '{peer_id}'")
                
                # Notify callback
                if self.on_peer_disconnected:
                    try:
                        self.on_peer_disconnected(peer_id)
                    except:
                        pass
                
                return True
            
            return False
    
    def _message_loop(self, p2p_conn):
        """Read and process messages from a P2P connection."""
        print(f"[P2P] Message loop started for '{p2p_conn.remote_peer_id}'")
        
        try:
            p2p_conn.conn.settimeout(1.0)
            buffer = ""
            
            while self.running and not p2p_conn.closed:
                try:
                    chunk = p2p_conn.conn.recv(4096)
                    
                    if not chunk:
                        # Connection closed by remote
                        print(f"[P2P] Connection closed by '{p2p_conn.remote_peer_id}'")
                        break
                    
                    buffer += chunk.decode('utf-8')
                    p2p_conn.last_activity = time.time()
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        
                        if line:
                            self._handle_message(p2p_conn, line)
                
                except socket.timeout:
                    # Check idle timeout
                    if time.time() - p2p_conn.last_activity > self.IDLE_TIMEOUT:
                        print(f"[P2P] Idle timeout for '{p2p_conn.remote_peer_id}'")
                        break
                    continue
                
                except Exception as e:
                    print(f"[P2P] Error in message loop for '{p2p_conn.remote_peer_id}': {e}")
                    break
        
        finally:
            # Clean up connection
            with self.lock:
                if p2p_conn.remote_peer_id in self.connections:
                    del self.connections[p2p_conn.remote_peer_id]
            
            p2p_conn.close()
            
            # Notify callback
            if self.on_peer_disconnected:
                try:
                    self.on_peer_disconnected(p2p_conn.remote_peer_id)
                except:
                    pass
            
            print(f"[P2P] Message loop ended for '{p2p_conn.remote_peer_id}'")
    
    def _handle_message(self, p2p_conn, line):
        """Handle incoming message line."""
        try:
            msg = json.loads(line)
            msg_type = msg.get('type', 'UNKNOWN')
            
            print(f"[P2P] ← {msg_type} from '{p2p_conn.remote_peer_id}'")
            
            if msg_type == 'PING':
                # Respond with PONG
                self.send_message(p2p_conn.remote_peer_id, '', 'PONG')
            
            elif msg_type == 'PONG':
                # Keepalive response
                pass
            
            elif msg_type == 'CLOSE':
                # Graceful close requested
                print(f"[P2P] Close requested by '{p2p_conn.remote_peer_id}'")
                
                # Forward CLOSE message to callback so receiver can display notification
                if self.on_message:
                    try:
                        self.on_message(msg.get('from'), msg.get('to'), msg)
                    except Exception as e:
                        print(f"[P2P] Error in on_message callback: {e}")
                
                # Mark connection for closure
                p2p_conn.closed = True
            
            elif msg_type == 'CHAT':
                # Forward to callback
                if self.on_message:
                    try:
                        self.on_message(msg.get('from'), msg.get('to'), msg)
                    except Exception as e:
                        print(f"[P2P] Error in on_message callback: {e}")
            
            else:
                print(f"[P2P] Unknown message type: {msg_type}")
        
        except json.JSONDecodeError as e:
            print(f"[P2P] Invalid JSON from '{p2p_conn.remote_peer_id}': {line}")
        except Exception as e:
            print(f"[P2P] Error handling message: {e}")
    
    def _keepalive_loop(self):
        """Send periodic PING to all connections."""
        print(f"[P2P] Keepalive loop started")
        
        while self.running:
            time.sleep(self.KEEPALIVE_INTERVAL)
            
            with self.lock:
                for peer_id in list(self.connections.keys()):
                    self.send_message(peer_id, '', 'PING')
    
    def _read_line(self, conn):
        """Read a line from socket (blocking, until \\n or timeout)."""
        buffer = ""
        
        while True:
            chunk = conn.recv(1)
            if not chunk:
                return None
            
            char = chunk.decode('utf-8')
            buffer += char
            
            if char == '\n':
                return buffer
    
    def get_active_connections(self):
        """Get list of active peer IDs."""
        with self.lock:
            return list(self.connections.keys())
