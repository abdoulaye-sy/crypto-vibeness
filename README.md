# Crypto Vibeness 🚀

A secure multi-user chat application with private password-protected rooms.

## Features

- **Username validation** - No duplicate usernames allowed
- **Public & Private Rooms** - Create rooms, protect them with passwords
- **Real-time messaging** - Send messages to all users in the same room
- **Room switching** - Change rooms seamlessly with password validation
- **Comprehensive logging** - All events logged to timestamped files

## Quick Start

### Prerequisites
- Python 3.7+
- No external dependencies

### Running the Server

```bash
python3 server.py
```

Server starts on `127.0.0.1:5001` and creates a log file in `logs/`

### Running a Client

```bash
python3 client.py
```

Follow the prompts to:
1. Enter a unique username
2. Choose a room (or create new)
3. Set privacy/password if creating new room
4. Start chatting!

## Commands

- `/room <name>` - Switch to another room
- `/quit` - Disconnect and exit

## Room Privacy

- 🔓 Public room - anyone can join
- 🔒 Private room - requires password to join

## Architecture

- **server.py** - Multi-threaded chat server with room management
- **client.py** - Interactive chat client with threading for concurrent send/receive
- **logs/** - Timestamped server logs for debugging

## Data Persistence

- ✅ Logs are persisted (archived in `logs/` folder)
- ❌ Room state is NOT persisted (resets on server restart)
- ❌ User connections are NOT persisted (fresh start on server restart)
