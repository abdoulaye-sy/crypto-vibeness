# Crypto Vibeness 🚀

A secure multi-user chat application with **user authentication**, **password management**, and **private password-protected rooms**.

## Features

### Stage 1: Core Chat
- ✅ **Username validation** - No duplicate usernames allowed
- ✅ **Public & Private Rooms** - Create rooms, protect them with passwords
- ✅ **Room switching** - Change rooms seamlessly with `/room <name>` command
- ✅ **Real-time messaging** - Send messages to all users in the same room
- ✅ **System notifications** - User joined/left messages

### Stage 2: Authentication & Security
- ✅ **User Authentication** - Create accounts and login with secure passwords
- ✅ **Password Hashing** - MD5 with base64 encoding (not plaintext)
- ✅ **Password Validation** - 5 configurable rules (length, uppercase, lowercase, digit, special char)
- ✅ **Password Strength Scoring** - Entropy-based strength indicator (🔴 Very Weak → 🟢 Strong)
- ✅ **Constant-time Verification** - Resistant to timing attacks
- ✅ **Persistent Accounts** - Accounts survive server restarts
- ✅ **Colored Usernames** - Deterministic colors for easy user identification
- ✅ **Comprehensive Logging** - All events logged to timestamped files in `logs/`

## Quick Start

### Prerequisites
- Python 3.7+
- No external dependencies required

### Running the Server

```bash
python3 server.py
```

Server starts on `127.0.0.1:5001` and creates:
- `logs/log_YYYY-MM-DD_HH-MM-SS.txt` - Session log file
- `this_is_safe.txt` - User credentials (auto-created on first signup, in .gitignore)
- `password_rules.txt` - Password validation rules

### Running a Client

```bash
python3 client.py
```

## Authentication Flow

### Create Account (First Time)
```
Connected to 127.0.0.1:5001
Enter username: alice
Create account? (yes/no): yes
Enter password: ••••••••
💪 🟢 Strong
Confirm password: ••••••••
✅ Authenticated as alice
✅ Account created successfully
Enter room name (default: general): general
✓ Logged in as alice
```

### Login (Returning User)
```
Connected to 127.0.0.1:5001
Enter username: alice
Enter password: ••••••••
✅ Authenticated as alice
Enter room name (default: general): general
✓ Logged in as alice
```

## Password Management

### Validation Rules

Five built-in rules enforced at signup:

| Rule | Example |
|------|---------|
| **Minimum 8 characters** | "Pass" ❌ → "Password1!" ✅ |
| **Uppercase letter** | "password1!" ❌ → "Password1!" ✅ |
| **Lowercase letter** | "PASSWORD1!" ❌ → "Password1!" ✅ |
| **Digit (0-9)** | "Password!" ❌ → "Password1!" ✅ |
| **Special character** | "Password1" ❌ → "Password1!" ✅ |

Special characters accepted: `!@#$%^&*-_+=.`

### Strength Scoring

Strength is calculated as:
```
Score = (Rule Compliance × 0.7) + (Entropy × 0.3)
```

**Strength Levels:**
- 🔴 **Very Weak** (0-40%) - Critical weaknesses
- 🟠 **Weak** (40-60%) - Multiple missing rules
- 🟡 **Fair** (60-80%) - One missing rule or low entropy
- 🟢 **Strong** (80%+) - All rules met + good entropy

**Examples:**
```
"weak"             → 🔴 Very Weak (18%)
"Password123"      → 🟡 Fair (71%)
"Password1!"       → 🟢 Strong (91%)
"VeryLong@Pass123" → 🟢 Strong (100%)
```

### Hashing Algorithm

- **Hash Function**: MD5 (suitable for learning/demo, not production)
- **Encoding**: Base64 (not hex)
- **Output**: 24-character base64 string
- **Verification**: Constant-time comparison (hmac.compare_digest)

**Storage Format** (this_is_safe.txt):
```
username:base64_encoded_hash
alice:dM1cBrh5YWkQOM/Z+et+tw==
bob:RJCIVOWm3rRXwZ6tIlRr2A==
```

## Commands

During chat:
- `/room <name>` - Switch to another room
- `/quit` - Disconnect and exit

## Room Privacy

### Public Room (🔓)
- Anyone can join without password
- Default behavior for "general" room
- Created by default when room doesn't require privacy

### Private Room (🔒)
- Password required to join
- Created when user selects "yes" for private option
- Password validated on each join
- Users can retry if password is incorrect

### Room Selection Flow

**Creating a new room:**
```
Enter room name (default: general): my_room
Do you want this room to be private? (yes/no): yes
Enter room password: secretpass
✓ Logged in as alice
```

**Joining an existing room:**
```
Enter room name (default: general): my_room
Enter room password: secretpass
✓ Logged in as alice
```

**Joining public room:**
```
Enter room name (default: general): general
✓ Logged in as alice
```

## Architecture

### Files

```
crypto-vibeness/
├── server.py                 - Multi-threaded server (500+ lines)
│                              Handles:
│                              - TCP socket management
│                              - User authentication
│                              - Room management
│                              - Message broadcasting
│
├── client.py                 - Interactive chat client (340+ lines)
│                              Handles:
│                              - User signup/login
│                              - Room selection
│                              - Message send/receive
│                              - Color formatting
│
├── password_manager.py       - Security module (280+ lines)
│                              Provides:
│                              - PasswordRulesEngine (load/validate rules)
│                              - PasswordManager (hashing, creation)
│                              - PasswordValidator (strength checking)
│
├── password_rules.txt        - Configurable validation rules
│                              5 rules in format: name:description:expression
│
├── .gitignore                - Git exclusions (this_is_safe.txt, __pycache__)
│
├── password_manager_test.py  - Unit tests for security module
│
└── logs/                     - Server logs directory
                              Files: log_YYYY-MM-DD_HH-MM-SS.txt
```

### Communication Protocol

**Text-based protocol over TCP:**

```
Connection Phase:
CLIENT → SERVER: (connect on port 5001)
SERVER → CLIENT: AUTH:
CLIENT → SERVER: <username>
SERVER → CLIENT: CREATE_ACCOUNT? (if new user)
                 PASSWORD: (if existing user)
CLIENT → SERVER: <response>

Room Selection Phase:
SERVER → CLIENT: ROOM:
CLIENT → SERVER: <room_name>
SERVER → CLIENT: PRIVATE?:yes/no (if new room, not "general")
CLIENT → SERVER: yes/no
SERVER → CLIENT: PASSWORD: (if private)
                 OK:Connected to <room>|🔓/🔒

Chat Phase:
CLIENT → SERVER: <message>
SERVER → ALL_IN_ROOM: {"type": "message", "username": "...", "color": "...", "message": "...", "timestamp": "..."}
```

### Message Format (JSON)

```json
{
  "type": "message",
  "username": "alice",
  "color": "cyan",
  "message": "Hello everyone!",
  "timestamp": "14:23:45",
  "room": "general"
}
```

### Colored Usernames

- **Deterministic assignment**: Color based on hash(username)
- **Color palette**: green, yellow, blue, magenta, cyan
- **ANSI codes**: Applied only to username, not message content
- **Display**: `alice: Hello everyone!` (username in color, message in white)

## Data Persistence

- ✅ **User accounts** - Persisted in `this_is_safe.txt` (encrypted passwords)
- ✅ **Server logs** - Archived in `logs/` folder with timestamps
- ❌ **Room state** - NOT persisted (resets on server restart)
- ❌ **User connections** - NOT persisted (fresh start on server restart)

## Security Notes

### Current Implementation
- Passwords hashed with MD5 + base64 (suitable for learning)
- Constant-time comparison (HMAC-based, resistant to timing attacks)
- Configurable validation rules
- No plaintext password storage

### Limitations
- MD5 not production-grade (use bcrypt/Argon2 for production)
- No message encryption (plain TCP, use TLS for production)
- No authentication between server sessions (login per connection)
- Simple password-based room access (no ACLs or permissions)

### Future Enhancements
1. Database integration (SQLite, PostgreSQL)
2. TLS/SSL encryption
3. Better hashing (bcrypt, Argon2)
4. Persistent session tokens
5. Role-based access control (admin, moderator)
6. Rate limiting & spam prevention
7. Message history
8. Async I/O (asyncio) for better concurrency

## Development

### Running Tests

```bash
python3 password_manager_test.py
```

All tests should pass (password hashing, validation, strength scoring).

### Creating a Fresh Environment

```bash
# Clean up old data
rm -f this_is_safe.txt
rm -f logs/*.txt

# Start server (new credentials file created automatically)
python3 server.py

# In another terminal, start client
python3 client.py
```

## Example Session

```
# Terminal 1: Server
$ python3 server.py
2026-04-16 10:11:02 - INFO - Server started on 127.0.0.1:5001
2026-04-16 10:11:09 - INFO - New connection from ('127.0.0.1', 45286)
2026-04-16 10:11:09 - INFO - New account signup: alice
2026-04-16 10:11:09 - INFO - User alice connected and authenticated
2026-04-16 10:11:09 - INFO - Room 'general' created (PUBLIC)
2026-04-16 10:11:09 - INFO - User alice joined room general
2026-04-16 10:11:09 - INFO - [general] alice: Hello world!

# Terminal 2: Client 1 (Alice)
$ python3 client.py
Connected to 127.0.0.1:5001
Enter username: alice
Create account? (yes/no): yes
Enter password: Password1!
💪 🟢 Strong
Confirm password: Password1!
✅ Authenticated as alice
Enter room name (default: general): general
✓ Logged in as alice

alice [general 🔓]: Hello world!

# Terminal 3: Client 2 (Bob)
$ python3 client.py
Connected to 127.0.0.1:5001
Enter username: bob
Create account? (yes/no): yes
Enter password: SecurePass123!
💪 🟢 Strong
Confirm password: SecurePass123!
✅ Authenticated as bob
Enter room name (default: general): general
✓ Logged in as bob

bob [general 🔓]: alice: Hello world!
bob [general 🔓]: Hi Alice!

# Back to Terminal 2 (Alice sees Bob's message)
alice [general 🔓]: bob: Hi Alice!
```

## Tech Stack

- **Language**: Python 3.7+
- **Libraries**: socket, threading, json, logging, hashlib, hmac, base64
- **Platform**: Cross-platform (Windows, Linux, macOS)
- **Architecture**: Multi-threaded server, synchronous client
- **Protocol**: Custom text-based over TCP

## License

Open source for educational purposes.

## Contributing

This is a learning project for demonstrating secure chat application development.

---

**Last Updated**: 2026-04-16  
**Current Stage**: Stage 2 - Authentication & Security ✅ Complete
