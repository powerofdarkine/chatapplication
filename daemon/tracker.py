#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# WeApRous release
#

"""
daemon.tracker
~~~~~~~~~~~~~~~~~

P2P Tracker for hybrid chat system.
Manages peer discovery, health checks, and event broadcasting.
"""

import time
import threading
import json
import uuid
from collections import deque, defaultdict


class Peer:
    """Represents a peer in the P2P network."""
    
    def __init__(self, peer_id, ip, port, display_name, channels=None):
        self.peer_id = peer_id
        self.ip = ip
        self.port = port
        self.display_name = display_name
        self.channels = channels or []
        self.last_seen = int(time.time() * 1000)  # epoch ms
        self.status = "ONLINE"
    
    def to_dict(self):
        return {
            'peer_id': self.peer_id,
            'ip': self.ip,
            'port': self.port,
            'display_name': self.display_name,
            'status': self.status,
            'last_seen': self.last_seen,
            'channels': self.channels
        }
    
    def update_heartbeat(self):
        self.last_seen = int(time.time() * 1000)
        self.status = "ONLINE"


class PeerTracker:
    """
    Central tracker for peer discovery and health management.
    Thread-safe implementation using locks.
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
        """Start cleanup thread."""
        if not self.running:
            self.running = True
            self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            self.cleanup_thread.start()
            print("[Tracker] Cleanup thread started")
    
    def stop(self):
        """Stop cleanup thread."""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=2)
            print("[Tracker] Cleanup thread stopped")
    
    def register_peer(self, peer_id, ip, port, display_name, channels=None):
        """Register or update a peer."""
        with self.lock:
            if peer_id in self.peers:
                # Update existing peer
                peer = self.peers[peer_id]
                peer.ip = ip
                peer.port = port
                peer.display_name = display_name
                peer.channels = channels or []
                peer.update_heartbeat()
                
                event_type = 'peer-updated'
                print(f"[Tracker] Peer updated: {peer_id}")
            else:
                # New peer
                peer = Peer(peer_id, ip, port, display_name, channels)
                self.peers[peer_id] = peer
                
                event_type = 'peer-joined'
                print(f"[Tracker] Peer joined: {peer_id} ({display_name}) at {ip}:{port}")
            
            # Broadcast event to all OTHER peers
            self._broadcast_event_locked(event_type, peer, exclude=peer_id)
            
            return peer.to_dict()
    
    def unregister_peer(self, peer_id):
        """Manually unregister a peer."""
        with self.lock:
            if peer_id in self.peers:
                peer = self.peers[peer_id]
                peer.status = "OFFLINE"
                
                # Broadcast peer-left
                self._broadcast_event_locked('peer-left', peer)
                
                # Remove from active peers
                del self.peers[peer_id]
                print(f"[Tracker] Peer left: {peer_id}")
                
                return True
            return False
    
    def get_peers(self, exclude_peer=None):
        """Get list of all active peers (optionally exclude one)."""
        with self.lock:
            peers = [
                p.to_dict() 
                for pid, p in self.peers.items() 
                if pid != exclude_peer
            ]
            return peers
    
    def get_peer(self, peer_id):
        """Get single peer info."""
        with self.lock:
            peer = self.peers.get(peer_id)
            return peer.to_dict() if peer else None
    
    def heartbeat(self, peer_id):
        """Update peer heartbeat."""
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id].update_heartbeat()
                return True
            return False
    
    def get_expired_peers(self):
        """Get list of peers that have expired (no heartbeat)."""
        now = int(time.time() * 1000)
        threshold = now - self.HEARTBEAT_TIMEOUT_MS
        
        expired = []
        with self.lock:
            for peer_id, peer in list(self.peers.items()):
                if peer.last_seen < threshold and peer.status == "ONLINE":
                    # Mark as offline
                    peer.status = "OFFLINE"
                    expired.append(peer_id)
                    
                    # Broadcast peer-left event to all OTHER peers
                    self._broadcast_event_locked('peer-left', peer)
                    
                    print(f"[Tracker] Peer expired: {peer_id} (last seen: {peer.last_seen})")
                    
                    # Remove from active peers after broadcasting
                    # (This prevents re-broadcasting in future cleanup cycles)
                    del self.peers[peer_id]
        
        return expired
    
    def get_events(self, peer_id, since_ts=0):
        """Get events for a peer since timestamp."""
        with self.lock:
            events = self.events.get(peer_id, deque())
            # Filter events after since_ts
            filtered = [e for e in events if e['ts'] > since_ts]
            return filtered
    
    def _broadcast_event_locked(self, event_type, peer, exclude=None):
        """
        Broadcast event to all peers (must be called with lock held).
        
        :param event_type: 'peer-joined' | 'peer-left' | 'peer-updated'
        :param peer: Peer object
        :param exclude: peer_id to exclude from broadcast
        """
        event = {
            'type': event_type,
            'peer': peer.to_dict(),
            'ts': int(time.time() * 1000)
        }
        
        for pid in self.peers:
            if pid != exclude:
                self.events[pid].append(event)
    
    def _cleanup_loop(self):
        """Background thread to check for expired peers."""
        print("[Tracker] Cleanup loop started")
        
        while self.running:
            try:
                # Check for expired peers
                expired = self.get_expired_peers()
                
                if expired:
                    print(f"[Tracker] Cleaned up {len(expired)} expired peers")
                
                # Sleep
                time.sleep(self.CLEANUP_INTERVAL_SEC)
                
            except Exception as e:
                print(f"[Tracker] Error in cleanup loop: {e}")
                import traceback
                traceback.print_exc()
    
    def get_peer_address(self, peer_id):
        """Get peer's IP:port for P2P connection."""
        with self.lock:
            peer = self.peers.get(peer_id)
            if peer and peer.status == "ONLINE":
                return {
                    'ip': peer.ip,
                    'port': peer.port
                }
            return None
    
    def generate_nonce(self):
        """Generate random nonce for P2P handshake."""
        return str(uuid.uuid4())[:8]


# Global singleton tracker
_tracker_instance = None

def get_tracker():
    """Get global tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = PeerTracker()
        _tracker_instance.start()
    return _tracker_instance
