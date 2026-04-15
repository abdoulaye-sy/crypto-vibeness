# Crypto Vibeness 🚀

A secure multi-user chat application with **user authentication** and private password-protected rooms.

## Features

- **User Authentication** - Create accounts and login with passwords (SHA256 hashed)
- **Persistent Accounts** - Accounts survive server restarts
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

Server starts on `127.0.0.1:5001` and creates:
- `log_YYYY-MM-DD_HH-MM-SS.txt` - Session log file
- `accounts.json` - User accounts (auto-created on first signup)

### Running a Client

```bash
python3 client.py
```

Follow the prompts:

**First time (create account):**
1. Enter new username
2. Select "yes" to create account
3. Set password
4. Confirm password
5. Choose a room
6. Start chatting!

**Returning user (login):**
1. Enter username
2. Enter password
3. Choose a room
4. Start chatting!

## Authentication

### Create Account Flow
```
Enter username: alice
Create account? (yes/no): yes
Enter password: ****
Confirm password: ****
✅ Authenticated as alice
```

### Login Flow
```
Enter username: alice
Enter password: ****
✅ Authenticated as alice
```

### Account Files

**accounts.json** (auto-created)
```json
{
  "alice": {
    "password_hash": "salt$sha256hash",
    "created_at": "2026-04-15T16:07:03.773231"
  }
}
```

- Passwords are **hashed with salt**, never stored in plaintext
- Survives server restarts
- New accounts created on first successful signup

## Commands

- `/room <name>` - Switch to another room
- `/quit` - Disconnect and exit

## Room Privacy

- 🔓 Public room - anyone can join
- 🔒 Private room - requires password to join

## Architecture

- **server.py** - Multi-threaded chat server with authentication + room management
- **client.py** - Interactive chat client with async send/receive
- **logs/** - Timestamped server logs for debugging
- **accounts.json** - Persistent user accounts (encrypted passwords)

## Data Persistence

- ✅ User accounts persisted (encrypted passwords in `accounts.json`)
- ✅ Logs persisted (archived in `logs/` folder)
- ❌ Room state is NOT persisted (resets on server restart)
- ❌ User connections are NOT persisted (fresh start on server restart)
