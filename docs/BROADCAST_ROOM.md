# Broadcast Room Feature

## Overview

The broadcast room feature allows multiple peers to join a shared chat room where messages are sent to all active members. This provides a group chat functionality in addition to the existing peer-to-peer private messaging.

## Key Features

1. **Join/Leave Broadcast Room**: Users can join or leave the broadcast room at any time
2. **Broadcast Messages**: Messages sent to the room are delivered to all active members
3. **Join Announcements**: When someone joins the room, all members are notified
4. **Message History**: Users can only see messages sent AFTER they joined the room
5. **Auto-cleanup on Logout**: When a user logs out, they are automatically removed from the broadcast room
6. **Session Persistence**: Logging out then logging in again will clear the message history - users only see new messages

## Implementation Details

### Backend Changes

#### 1. Tracker (`daemon/tracker.py`)

Added the following attributes to `PeerTracker`:
- `broadcast_room_members`: Set of peer_ids currently in the room
- `broadcast_messages`: Deque of all broadcast messages (max 500)
- `peer_join_timestamps`: Tracks when each peer joined the room

New methods:
- `join_broadcast_room(peer_id)`: Add a peer to the room and announce their join
- `leave_broadcast_room(peer_id)`: Remove a peer from the room and announce their leave
- `send_broadcast_message(peer_id, message)`: Send a message to all room members
- `get_broadcast_messages(peer_id, since_ts)`: Get messages sent after the peer joined
- `get_broadcast_room_members()`: Get list of current members
- `is_in_broadcast_room(peer_id)`: Check if peer is in the room

Auto-cleanup integration:
- `unregister_peer()`: Now removes peer from broadcast room on logout
- `get_expired_peers()`: Now removes expired peers from broadcast room

#### 2. Backend API (`start_sampleapp.py`)

New endpoints:
- `POST /api/broadcast/join`: Join the broadcast room
- `POST /api/broadcast/leave`: Leave the broadcast room
- `POST /api/broadcast/send`: Send a message to all room members
  - Request: `{message: "text"}`
  - Response: `{status: "success", recipients: [...], recipient_count: N}`
- `POST /api/broadcast/messages`: Poll for new broadcast messages
  - Request: `{since: timestamp}`
  - Response: `{messages: [...], server_time: timestamp}`
- `GET /api/broadcast/members`: Get list of current members
- `GET /api/broadcast/status`: Check if user is in the room

### Frontend Changes

#### 1. Chat Interface (`static/js/chat.js`)

New state variables:
- `inBroadcastRoom`: Boolean tracking if user is in the room
- `broadcastRoomMembers`: Array of member peer_ids
- `lastBroadcastTimestamp`: Timestamp for polling new messages

New functions:
- `selectBroadcastRoom()`: Open the broadcast room chat window
- `joinBroadcastRoom()`: Join the room via API
- `leaveBroadcastRoom()`: Leave the room via API
- `pollBroadcastMessages()`: Poll for new broadcast messages every 2 seconds
- `updateBroadcastRoomStatus()`: Update member count display

Updated functions:
- `renderPeerList()`: Now shows "Broadcast Room" option at the top
- `sendMessage()`: Handles both P2P and broadcast messages
- `loadCurrentUser()`: Added polling for broadcast messages

#### 2. UI Updates

The peer list now shows:
```
📢 Broadcast Room
   [Joined badge if in room]
   X members

[Individual peers below...]
```

When broadcast room is selected:
- Title shows "Broadcast Room"
- Status shows "(X members)"
- Button changes between "Join Room" / "Leave Room"
- Input is disabled until user joins
- Messages show sender name for received messages

## Message Types

### System Messages
```json
{
  "type": "SYSTEM",
  "from": "SYSTEM",
  "body": "user1 joined the broadcast room",
  "timestamp": 1699999999999,
  "msg_id": "uuid"
}
```

### Chat Messages
```json
{
  "type": "CHAT",
  "from": "user1",
  "body": "Hello everyone!",
  "timestamp": 1699999999999,
  "msg_id": "uuid"
}
```

## Security & Privacy

1. **Authentication Required**: All broadcast room endpoints require user authentication
2. **Join-time Filtering**: Users only see messages sent AFTER they joined
3. **Session Isolation**: Logging out clears the join timestamp - re-logging in shows only new messages
4. **No Persistent Storage**: All broadcast messages are stored in-memory only
5. **Message Limit**: Maximum 500 broadcast messages stored (prevents memory overflow)

## Usage Flow

1. User logs in and registers P2P
2. User clicks "Broadcast Room" in the peer list
3. User clicks "Join Room" button
4. System announces "user joined the broadcast room" to all members
5. User can now send messages to all members
6. Messages are broadcast to all current members
7. When user clicks "Leave Room", they are removed and can no longer see new messages
8. If user logs out, they are automatically removed from the room

## Testing

Run the test suite:
```bash
python test_broadcast_room.py
```

The test verifies:
- ✓ Joining the broadcast room
- ✓ Sending broadcast messages
- ✓ Message retrieval and filtering
- ✓ Non-member access restriction
- ✓ Join timestamp filtering (users only see messages after joining)
- ✓ Leaving the broadcast room
- ✓ Auto-removal on logout/timeout

## Future Enhancements

Potential improvements:
- Message persistence (database storage)
- User typing indicators
- Message read receipts
- Room moderator/admin roles
- Private rooms with access control
- File/image sharing in broadcast room
- Message search functionality
