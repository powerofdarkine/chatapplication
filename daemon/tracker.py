"""daemon.tracker
==================

Tracker component used by the backend to record active peers, detect
peer timeouts and deliver peer-related events to connected clients.

This module provides a lightweight, thread-safe in-memory tracker
implementation intended for educational / lab use. It is *not* a
production-ready membership service — state is kept in-process and
lost on restart.

Key responsibilities
- register/unregister peers (with associated metadata)
- maintain last-seen timestamps and mark peers offline after a
    configurable heartbeat timeout
- queue peer events (peer-joined, peer-left, peer-updated) per peer
- provide a simple background cleanup thread to remove expired peers

Thread-safety
: The tracker uses a reentrant lock (``threading.RLock``) to protect
    access to internal maps. Public methods acquire the lock where
    necessary.

Typical usage::

        tracker = get_tracker()
        tracker.register_peer('user1', '192.168.1.5', 9100, 'Alice')
        peers = tracker.get_peers()
        events = tracker.get_events('user2', since_ts=0)

"""

import time
import threading
import json
import uuid
from collections import deque, defaultdict


class Peer:
    """Light-weight data holder for a tracked peer.

    Attributes
    - peer_id (str): Unique identifier for the peer (application-level)
    - ip (str): IP address where peer's daemon is reachable
    - port (int): TCP port for the peer's daemon
    - display_name (str): Human-friendly name shown in the UI
    - last_seen (int): Last heartbeat timestamp in milliseconds since epoch
    - status (str): ``ONLINE`` or ``OFFLINE``
    """

    def __init__(self, peer_id, ip, port, display_name):
        self.peer_id = peer_id
        self.ip = ip
        self.port = port
        self.display_name = display_name
        # last_seen recorded in epoch milliseconds
        self.last_seen = int(time.time() * 1000)
        self.status = "ONLINE"
    
    def to_dict(self):
        """Return a JSON-serializable representation of this peer."""
        return {
            'peer_id': self.peer_id,
            'ip': self.ip,
            'port': self.port,
            'display_name': self.display_name,
            'status': self.status,
            'last_seen': self.last_seen,
        }
    
    def update_heartbeat(self):
        """Mark the peer as seen now and set status to ONLINE.

        This should be called when a heartbeat or other activity is
        observed from the peer.
        """
        self.last_seen = int(time.time() * 1000)
        self.status = "ONLINE"


class PeerTracker:
    """
    Central tracker for peer discovery and health management.

    The tracker maintains peers, per-peer event queues and a background
    cleanup loop to expire stale peers.
    """
    # Configuration
    HEARTBEAT_TIMEOUT_MS = 45000  # 45 seconds
    CLEANUP_INTERVAL_SEC = 5      # Check every 5 seconds
    EVENT_QUEUE_MAX = 100         # Max events per peer
    
    def __init__(self):
        self.peers = {}  # peer_id -> Peer
        self.events = defaultdict(lambda: deque(maxlen=self.EVENT_QUEUE_MAX))  # peer_id -> deque<event>
        self.lock = threading.RLock()
        self.cleanup_thread = None
        self.running = False
        print("[Tracker] Initialized")
    
    def start(self):
        """Start the tracker's background cleanup thread.

        The cleanup thread runs as a daemon and periodically scans for peers
        that have not sent heartbeats within ``HEARTBEAT_TIMEOUT_MS`` and
        expires them. This method is idempotent: calling it when the
        tracker is already running has no effect.

        Side effects:
            Starts a daemon :class:`threading.Thread` that executes
            :meth:`_cleanup_loop`.
        """
        if not self.running:
            self.running = True
            self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            self.cleanup_thread.start()
            print("[Tracker] Cleanup thread started")
    
    def stop(self):
        """Stop the background cleanup thread.

        Requests the cleanup loop to stop and joins the thread briefly.
        Safe to call even if the tracker is not running.
        """
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=2)
            print("[Tracker] Cleanup thread stopped")
    
    def register_peer(self, peer_id, ip, port, display_name):
        """Register a new peer or update an existing peer.

        If ``peer_id`` already exists the method updates the peer's address
        and display name and refreshes its heartbeat timestamp. Otherwise a
        new :class:`Peer` is created and marked as ``ONLINE``.

        Args:
            peer_id (str): application-level peer identifier
            ip (str): IP address where the peer's P2P daemon is reachable
            port (int): TCP port for the peer's daemon
            display_name (str): human-friendly display name

        Returns:
            dict: JSON-serializable representation of the registered peer
                  (result of :meth:`Peer.to_dict`).
        """
        with self.lock:
            if peer_id in self.peers:
                # Update existing record in-place
                peer = self.peers[peer_id]
                peer.ip = ip
                peer.port = port
                peer.display_name = display_name
                peer.update_heartbeat()

                event_type = 'peer-updated'
                print(f"[Tracker] Peer updated: {peer_id}")
            else:
                # Create a new tracked peer
                peer = Peer(peer_id, ip, port, display_name)
                self.peers[peer_id] = peer

                event_type = 'peer-joined'
                print(f"[Tracker] Peer joined: {peer_id} ({display_name}) at {ip}:{port}")

            # Broadcast event to all other peers (exclude the actor)
            self._broadcast_event_locked(event_type, peer, exclude=peer_id)

            return peer.to_dict()
    
    def unregister_peer(self, peer_id):
        """Unregister a peer and broadcast a ``peer-left`` event.

        The peer is marked ``OFFLINE``, a ``peer-left`` event is appended to
        all other peers' event queues, and the peer is removed from the
        active map.

        Args:
            peer_id (str): identifier of the peer to remove

        Returns:
            bool: True if the peer was present and removed, False otherwise
        """

        with self.lock:
            if peer_id in self.peers:
                peer = self.peers[peer_id]
                peer.status = "OFFLINE"

                # Notify other peers
                self._broadcast_event_locked('peer-left', peer)

                # Remove the peer from the active map
                del self.peers[peer_id]
                print(f"[Tracker] Peer left: {peer_id}")

                return True
            return False
    
    def get_peers(self, exclude_peer=None):
        """Return a list of active peers as dictionaries.

        Args:
            exclude_peer (str, optional): peer id to omit from results.

        Returns:
            list[dict]: list of peer dicts (as produced by :meth:`Peer.to_dict`).
        """
        with self.lock:
            peers = [p.to_dict() for pid, p in self.peers.items() if pid != exclude_peer]
            return peers
    
    def get_peer(self, peer_id):
        """Return a single peer's dict or ``None`` if not found.

        Args:
            peer_id (str): identifier of the peer

        Returns:
            dict|None: peer representation or ``None`` if no such peer exists
        """
        with self.lock:
            peer = self.peers.get(peer_id)
            return peer.to_dict() if peer else None
    
    def heartbeat(self, peer_id):
        """Update the peer's last-seen timestamp (heartbeat).

        Args:
            peer_id (str): identifier of the peer sending the heartbeat

        Returns:
            bool: True if the peer exists and the heartbeat was applied,
                  False if the peer is unknown.
        """
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id].update_heartbeat()
                return True
            return False
    
    def get_expired_peers(self):
        """Find peers that have expired and remove them.

        A peer is considered expired when its ``last_seen`` timestamp is
        older than the configured ``HEARTBEAT_TIMEOUT_MS``. Expired peers
        are marked ``OFFLINE``, removed from the active map and a
        ``peer-left`` event is broadcast to remaining peers.

        Returns:
            list[str]: list of peer_ids that were expired and removed.
        """
        now = int(time.time() * 1000)
        threshold = now - self.HEARTBEAT_TIMEOUT_MS

        expired = []
        with self.lock:
            for peer_id, peer in list(self.peers.items()):
                if peer.last_seen < threshold and peer.status == "ONLINE":
                    # Mark offline
                    peer.status = "OFFLINE"
                    expired.append(peer_id)
                    # Notify others
                    self._broadcast_event_locked('peer-left', peer)

                    print(f"[Tracker] Peer expired: {peer_id} (last seen: {peer.last_seen})")
                    # Remove the peer from the active map
                    del self.peers[peer_id]

        return expired
    
    def get_events(self, peer_id, since_ts=0):
        """Return peer events queued since ``since_ts``.

        Args:
            peer_id (str): the peer whose event queue to read
            since_ts (int): timestamp (ms) to filter events (exclusive)

        Returns:
            list[dict]: events where each event has keys ``type``,
                        ``peer`` (dict) and ``ts`` (timestamp ms)
        """
        with self.lock:
            events = self.events.get(peer_id, deque())
            filtered = [e for e in events if e['ts'] > since_ts]
            return filtered
    
    def _broadcast_event_locked(self, event_type, peer, exclude=None):
        """Append an event to every peer's event queue.

        This helper must be called while holding ``self.lock``. The created
        event uses :meth:`Peer.to_dict` for the ``peer`` value. The
        ``exclude`` argument (if provided) is used to skip delivering the
        event to a specific peer (commonly the actor of the event).
        """
        event = {'type': event_type, 'peer': peer.to_dict(), 'ts': int(time.time() * 1000)}

        for pid in self.peers:
            if pid != exclude:
                self.events[pid].append(event)
    
    def _cleanup_loop(self):
        """Background loop executed by the cleanup daemon thread.

        The loop periodically invokes :meth:`get_expired_peers` and sleeps
        for ``CLEANUP_INTERVAL_SEC`` between iterations. Any exceptions are
        logged and the loop continues so the tracker remains resilient.
        """
        print("[Tracker] Cleanup loop started")

        while self.running:
            try:
                expired = self.get_expired_peers()

                if expired:
                    print(f"[Tracker] Cleaned up {len(expired)} expired peers")

                time.sleep(self.CLEANUP_INTERVAL_SEC)

            except Exception as e:
                # Keep the cleanup loop alive on unexpected errors and
                # surface the stack trace for debugging during development.
                print(f"[Tracker] Error in cleanup loop: {e}")
                import traceback
                traceback.print_exc()
    
    def get_peer_address(self, peer_id):
        """Return the contact address (ip/port) for an online peer.

        Args:
            peer_id (str): identifier of the peer to look up

        Returns:
            dict|None: ``{'ip': ip, 'port': port}`` if peer is ONLINE,
                       otherwise ``None``.
        """
        with self.lock:
            peer = self.peers.get(peer_id)
            if peer and peer.status == "ONLINE":
                return {'ip': peer.ip, 'port': peer.port}
            return None
    
    def generate_nonce(self):
        """Generate a short, non-cryptographic nonce used in handshakes.

        Returns:
            str: an 8-character string derived from a UUID4.
        """
        return str(uuid.uuid4())[:8]


# Global singleton tracker
_tracker_instance = None

def get_tracker():
    """Return the global PeerTracker singleton.

    Creates and starts the tracker on first invocation. Subsequent calls
    return the same running instance.

    Returns:
        PeerTracker: the global tracker instance.
    """
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = PeerTracker()
        _tracker_instance.start()
    return _tracker_instance
