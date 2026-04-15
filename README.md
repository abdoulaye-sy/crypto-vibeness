# Secure Chat Project - Step 1: Multi-Client TCP Chat

## Overview
A terminal-based multi-user chat system built progressively with increasing security layers.

**Current Step**: Basic TCP chat without any security.

## Architecture

```
┌─────────────┐
│   Server    │  (server.py)
│ localhost:  │
│    5000     │
└──────┬──────┘
       │
   ┌───┴────┬────────┐
   │        │        │
┌──────┐ ┌──────┐ ┌──────┐
│Client│ │Client│ │Client│ (client.py)
└──────┘ └──────┘ └──────┘
```

## How It Works

### Server (server.py)
- Listens on `localhost:5000`
- Accepts incoming client connections
- Creates a new thread for each client
- Receives messages from clients
- Broadcasts messages to all other connected clients
- Handles client disconnections gracefully

### Client (client.py)
- Connects to the server
- Sends typed messages
- Receives messages from other clients in real-time
- Handles disconnection cleanly

### Key Features
✅ Multi-threaded server (one thread per client)  
✅ Broadcast messaging  
✅ Connection/disconnection notifications  
✅ Thread-safe client storage (using locks)  
✅ Graceful error handling  

## Usage

### 1. Start the server
```bash
python3 server.py
```

Output:
```
[SERVER] Listening on localhost:5000
[SERVER] Waiting for connections...
```

### 2. Start one or more clients
```bash
python3 client.py
```

Output:
```
[CONNECTED] Connected to localhost:5000
Type 'quit' to exit

You: 
```

### 3. Type messages
Just type and hit Enter. Messages appear to all other clients.

Type `quit` to disconnect.

## Example Session

**Terminal 1 (Server)**:
```
[SERVER] Listening on localhost:5000
[SERVER] Waiting for connections...
[CONNECTED] 127.0.0.1:49152
[CONNECTED] 127.0.0.1:49153
[Alice] Hello everyone!
[Bob] Hi Alice!
[DISCONNECTED] 127.0.0.1:49152
```

**Terminal 2 (Alice)**:
```
[CONNECTED] Connected to localhost:5000
You: Hello everyone!
[Bob] Hi Alice!
```

**Terminal 3 (Bob)**:
```
[CONNECTED] Connected to localhost:5000
[Alice] Hello everyone!
You: Hi Alice!
```

## Project Roadmap

| Step | Feature | Code Changes |
|------|---------|---|
| 1 | ✅ Basic TCP chat | server.py, client.py |
| 2 | Authentication | Add login/username system |
| 3 | Password hashing | Add bcrypt password storage |
| 4 | Symmetric encryption | Encrypt messages with key |
| 5 | Asymmetric key exchange | RSA key exchange |
| 6 | End-to-end encryption | Per-pair encryption |
| 7 | Message signatures | Digital signatures for integrity |

## Technical Details

### Threading Model
- **Main server thread**: Accepts connections
- **Per-client threads**: Handle I/O for each connected client
- **Thread safety**: `threading.Lock()` protects shared client dictionary

### Network Protocol
- Plain text messages (no encryption yet)
- Messages end with newline for parsing
- Max buffer size: 1024 bytes per message

### Error Handling
- Graceful socket closure on client disconnect
- Exception handling for network errors
- Server continues running even if a client crashes
