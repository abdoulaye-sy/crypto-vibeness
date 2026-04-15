# Secure Chat Project (Educational)

## Goal
We are building a terminal-based secure chat system in Python step by step using an AI agent.

The system evolves progressively:
1. Basic TCP multi-client chat DONE
2. Usernames for clients DONE
3. Authentication system DONE
4. Password hashing and security improvements
5. Symmetric encryption of messages
6. Asymmetric cryptography for key exchange
7. End-to-end encryption
8. Message signatures and integrity checks

---

## Current Implementation Status

### Step 1 - Basic Multi-Client TCP Chat (DONE)
- Multi-client TCP server that accepts simultaneous connections
- Broadcast messaging: messages from any client are sent to all connected clients
- Server logs all connections and messages
- Clean connection/disconnection handling
- Uses threading for concurrent client handling

### Step 2 - Usernames (DONE)
- Each client enters a username when connecting
- Usernames are unique: duplicate active connections are rejected
- All messages broadcast with format: [username] message
- Server displays join/leave messages with username

### Step 3 - Authentication (DONE)

**What works:**
- Users can create new accounts or login to existing ones
- Authentication flow: username -> password -> create or verify -> allowed to chat

**Password validation rules:**
- Minimum 8 characters
- At least 1 number
- At least 1 special character (!@#$%^&*)
- Weak passwords rejected at creation time

**Security:**
- Passwords hashed with MD5
- Plain text passwords never stored
- Database file: this_is_safe.txt
- Format: username:md5_hash

**How it works:**
- authenticate_user() checks if user exists
- If exists: verify MD5 hash matches
- If doesn't exist: validate password, create account
- Server sends response codes

**Response codes:**
- ACCEPT: Authentication successful or account created
- REJECT_PASSWORD: Wrong password
- REJECT_WEAK_PASSWORD: New password too weak
- REJECT_EMPTY_PASSWORD: Empty password
- REJECT_EMPTY: Empty username
- REJECT_TAKEN: Username has active connection

**Client:**
- Uses getpass for hidden password input
- Shows user-friendly error messages
- Displays password requirements on rejection

---

## Technical constraints
- Python only
- Terminal-based (no GUI)
- Uses sockets for networking
- Uses threading
- Code must be modular and clean
- Two main files: server.py and client.py

---

## Communication rules
- Prompts in French, code in English
- Work step-by-step (one feature per prompt)
- Always test before moving next

---

## Project philosophy
Educational cryptography project - NOT production-ready.
We start with basic system and progressively add security.
