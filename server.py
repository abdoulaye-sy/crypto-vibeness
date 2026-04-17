import socket
import threading
import sys
import re
import os
import bcrypt
import random
import time
import json

# Dictionary to store connected clients
# Key: client socket, Value: {'address': (ip, port), 'username': username, 'room': room_name}
clients = {}
clients_lock = threading.Lock()

# Dictionary to store rooms
# Key: room_name, Value: [client_socket1, client_socket2, ...]
rooms = {'general': []}
rooms_lock = threading.Lock()

# Dictionary to store password reset tokens
reset_tokens = {}
reset_tokens_lock = threading.Lock()

# Dictionary to track typing users
# Key: (socket, room), Value: username
typing_users = {}
typing_lock = threading.Lock()

# Dictionary to track messages with read receipts
# Key: message_id, Value: {'sender': username, 'room': room_name, 'text': message, 'delivered_to': [], 'read_by': []}
messages = {}
message_id_counter = 0
messages_lock = threading.Lock()

# Dictionary to store DM sessions
# Key: "user1:user2" (alphabetically ordered to prevent duplication)
# Value: [{'sender': username, 'text': message, 'timestamp': time}]
dm_sessions = {}
dm_lock = threading.Lock()

# Direct username → socket mapping for DM delivery
# Key: username (lowercase), Value: socket object
dm_clients = {}
dm_clients_lock = threading.Lock()

# Message history storage
# Structure: {"rooms": {"room_name": [...]}, "dm": {"user1:user2": [...]}}
message_history = {"rooms": {}, "dm": {}}
history_lock = threading.Lock()
HISTORY_FILE = 'chat_history.json'
MAX_HISTORY_PER_ROOM = 100
LOAD_HISTORY_COUNT = 10


HOST = 'localhost'
PORT = 5000
USER_DB_FILE = 'this_is_safe.txt'

MIN_PASSWORD_LENGTH = 8
BCRYPT_ROUNDS = 12
TOKEN_EXPIRATION = 600
TOKEN_LENGTH = 6
DEFAULT_ROOM = 'general'

ENCRYPTION_KEY = 'chatkey123'


def hash_password(password):
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password, hashed_password):
    """Verify password against bcrypt hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        print(f"[ERROR] Password verification failed: {e}")
        return False


def is_valid_password(password):
    """Validate password strength"""
    if len(password) < MIN_PASSWORD_LENGTH:
        return False
    if not re.search(r'\d', password):
        return False
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]', password):
        return False
    return True



def encrypt(message):
    """Encrypt message using XOR with shared key"""
    if not message:
        return message
    encrypted = []
    key_len = len(ENCRYPTION_KEY)
    for i, char in enumerate(message):
        key_char = ENCRYPTION_KEY[i % key_len]
        encrypted_char = chr(ord(char) ^ ord(key_char))
        encrypted.append(encrypted_char)
    return ''.join(encrypted)


def decrypt(message):
    """Decrypt message using XOR with shared key"""
    if not message:
        return message
    # XOR is symmetric - decryption is same as encryption
    return encrypt(message)


def should_encrypt_message(message):
    """Determine if message should be encrypted"""
    # Don't encrypt commands
    if message.startswith('/'):
        return False
    # Don't encrypt server messages
    if message.startswith('[SERVER]'):
        return False
    return True


def load_user_database():
    """Load user database from file"""
    users = {}
    if os.path.exists(USER_DB_FILE):
        try:
            with open(USER_DB_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and ':' in line:
                        username, hashed_password = line.split(':', 1)
                        users[username.lower()] = (username, hashed_password)
        except Exception as e:
            print(f"[ERROR] Failed to load user database: {e}")
    return users


def save_user(username, password_hash):
    """Save new user to database"""
    try:
        with open(USER_DB_FILE, 'a') as f:
            f.write(f"{username}:{password_hash}\n")
    except Exception as e:
        print(f"[ERROR] Failed to save user: {e}")
        return False
    return True


def update_user_password(username, new_password_hash):
    """Update existing user password"""
    try:
        users = load_user_database()
        username_lower = username.lower()
        
        if username_lower not in users:
            return False
        
        with open(USER_DB_FILE, 'r') as f:
            lines = f.readlines()
        
        with open(USER_DB_FILE, 'w') as f:
            for line in lines:
                stored_username = line.split(':', 1)[0]
                if stored_username.lower() == username_lower:
                    f.write(f"{stored_username}:{new_password_hash}\n")
                else:
                    f.write(line)
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to update user password: {e}")
        return False


def generate_reset_token():
    """Generate random 6-digit token"""
    return ''.join([str(random.randint(0, 9)) for _ in range(TOKEN_LENGTH)])


def create_reset_token(username):
    """Create password reset token"""
    token = generate_reset_token()
    expiration = time.time() + TOKEN_EXPIRATION
    
    with reset_tokens_lock:
        reset_tokens[token] = {'username': username, 'expiration': expiration}
    
    return token


def verify_reset_token(token):
    """Verify token is valid and not expired"""
    with reset_tokens_lock:
        if token not in reset_tokens:
            return None
        
        token_data = reset_tokens[token]
        if time.time() > token_data['expiration']:
            del reset_tokens[token]
            return None
        
        return token_data['username']


def consume_reset_token(token):
    """Remove token after use (one-time only)"""
    with reset_tokens_lock:
        if token in reset_tokens:
            del reset_tokens[token]


def clean_expired_tokens():
    """Remove expired tokens"""
    with reset_tokens_lock:
        current_time = time.time()
        expired_tokens = [
            token for token, data in reset_tokens.items()
            if current_time > data['expiration']
        ]
        for token in expired_tokens:
            del reset_tokens[token]


def authenticate_user(username, password):
    """Authenticate user or create account if doesn't exist"""
    users = load_user_database()
    username_lower = username.lower()
    
    if username_lower in users:
        stored_username, stored_hash = users[username_lower]
        if verify_password(password, stored_hash):
            return 'AUTH_SUCCESS', stored_username
        else:
            return 'AUTH_FAIL', None
    else:
        if not is_valid_password(password):
            return 'INVALID_PASSWORD', None
        
        password_hash = hash_password(password)
        if save_user(username, password_hash):
            return 'ACCOUNT_CREATED', username
        else:
            return 'SAVE_FAIL', None


def get_all_rooms():
    """Get list of all room names"""
    with rooms_lock:
        return list(rooms.keys())


def join_room(client_socket, room_name, username):
    """Add client to a room"""
    with rooms_lock:
        # Create room if doesn't exist
        if room_name not in rooms:
            rooms[room_name] = []
        
        # Add client to room
        if client_socket not in rooms[room_name]:
            rooms[room_name].append(client_socket)
    
    # Update client info
    with clients_lock:
        if client_socket in clients:
            clients[client_socket]['room'] = room_name
    
    # Send room history to client
    send_room_history_to_client(client_socket, room_name, username)


def leave_room(client_socket, room_name):
    """Remove client from a room"""
    with rooms_lock:
        if room_name in rooms and client_socket in rooms[room_name]:
            rooms[room_name].remove(client_socket)
            
            # Delete room if empty (except general)
            if len(rooms[room_name]) == 0 and room_name != DEFAULT_ROOM:
                del rooms[room_name]


def broadcast_to_room(message, room_name, sender_socket=None):
    """Send message to all clients in a specific room except sender"""
    with rooms_lock:
        if room_name not in rooms:
            return
        
        room_clients = list(rooms[room_name])
    
    for client_socket in room_clients:
        if client_socket != sender_socket:
            try:
                client_socket.send(message.encode('utf-8'))
            except:
                pass



def get_users_in_room(room_name):
    """Get list of users in a specific room"""
    users = []
    with rooms_lock:
        room_clients = list(rooms.get(room_name, []))
    
    with clients_lock:
        for sock in room_clients:
            if sock in clients:
                users.append(clients[sock]['username'])
    
    return sorted(users)


def format_rooms_list():
    """Format rooms with user counts"""
    room_list = get_all_rooms()
    result = '[SERVER] ROOMS AVAILABLE:\n\n'
    for room_name in sorted(room_list):
        users = get_users_in_room(room_name)
        user_count = len(users)
        user_display = 'empty' if user_count == 0 else ', '.join(users)
        result += f'- {room_name} ({user_count} users: {user_display})\n'
    result += '\nInstructions:\n'
    result += 'Use /join <room> to enter a room\n'
    result += 'Example: /join crypto\n'
    return result


def get_welcome_message():
    """Get the full welcome message"""
    return ('[SERVER] WELCOME TO CHAT SYSTEM\n'
            '\n'
            'Rooms are available in this system.\n'
            '\n'
            'Available commands:\n'
            '- /rooms   -> show all available rooms\n'
            '- /join <room> -> join a room (example: /join crypto)\n'
            '- /leave   -> return to general room\n'
            '- /users   -> show users in current room\n'
            '- /msg <username> <message> -> send a private message\n'
            '- /help    -> show this help message\n'
            '\n'
            'Current room: general\n')



def set_typing(socket, room, username, typing):
    """Mark user as typing or not"""
    with typing_lock:
        if typing:
            typing_users[(socket, room)] = username
        else:
            typing_users.pop((socket, room), None)


def get_typing_users(room):
    """Get list of users typing in a room"""
    users = []
    with typing_lock:
        for (sock, r), user in typing_users.items():
            if r == room:
                users.append(user)
    return users


def create_message_with_id(sender, room, text):
    """Create a message with ID for tracking"""
    global message_id_counter
    with messages_lock:
        message_id_counter += 1
        msg_id = message_id_counter
        messages[msg_id] = {
            'sender': sender,
            'room': room,
            'text': text,
            'delivered_to': [],
            'read_by': [],
            'timestamp': time.time()
        }
    return msg_id


def mark_message_delivered(message_id, username):
    """Mark message as delivered to a user"""
    with messages_lock:
        if message_id in messages:
            if username not in messages[message_id]['delivered_to']:
                messages[message_id]['delivered_to'].append(username)


def mark_message_read(message_id, username):
    """Mark message as read by a user"""
    with messages_lock:
        if message_id in messages:
            if username in messages[message_id]['delivered_to']:
                if username not in messages[message_id]['read_by']:
                    messages[message_id]['read_by'].append(username)


def get_message_status(message_id):
    """Get delivery/read status of a message"""
    with messages_lock:
        if message_id in messages:
            msg = messages[message_id]
            return {
                'delivered': msg['delivered_to'],
                'read': msg['read_by'],
                'text': msg['text']
            }
    return None


def cleanup_old_messages():
    """Clean up old messages after 1 hour"""
    current_time = time.time()
    with messages_lock:
        old_ids = [msg_id for msg_id, msg in messages.items() 
                   if current_time - msg['timestamp'] > 3600]
        for msg_id in old_ids:
            del messages[msg_id]


def get_dm_session_key(user1, user2):
    """Create a consistent session key for DM (alphabetically ordered)"""
    users = sorted([user1.lower(), user2.lower()])
    return f"{users[0]}:{users[1]}"


def send_dm(sender, recipient, message):
    """Send a DM message"""
    key = get_dm_session_key(sender, recipient)
    with dm_lock:
        if key not in dm_sessions:
            dm_sessions[key] = []
        dm_sessions[key].append({
            'sender': sender,
            'text': message,
            'timestamp': time.time()
        })


def find_recipient_socket(recipient_username):
    """Find the socket of a connected user - direct lookup"""
    with dm_clients_lock:
        socket = dm_clients.get(recipient_username.lower())
        if socket:
            print(f"[DM_LOOKUP] Found {recipient_username} in dm_clients")
            return socket
        else:
            print(f"[DM_LOOKUP] {recipient_username} NOT in dm_clients")
            print(f"[DM_LOOKUP] Available users: {list(dm_clients.keys())}")
    return None


def load_message_history():
    """Load message history from JSON file"""
    global message_history
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                message_history = json.load(f)
                print(f"[HISTORY] Loaded chat history from {HISTORY_FILE}")
                print(f"[HISTORY] Rooms: {list(message_history.get('rooms', {}).keys())}")
                print(f"[HISTORY] DM sessions: {list(message_history.get('dm', {}).keys())}")
        except Exception as e:
            print(f"[ERROR] Failed to load history: {e}")
            message_history = {"rooms": {}, "dm": {}}
    else:
        message_history = {"rooms": {}, "dm": {}}


def save_message_history():
    """Save message history to JSON file (thread-safe)"""
    try:
        with history_lock:
            with open(HISTORY_FILE, 'w') as f:
                json.dump(message_history, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save history: {e}")


def save_room_message(username, room, message):
    """Save a room message to history"""
    with history_lock:
        if room not in message_history["rooms"]:
            message_history["rooms"][room] = []
        
        message_history["rooms"][room].append({
            "user": username,
            "message": message,
            "timestamp": time.time()
        })
        
        # Keep only recent messages to avoid excessive growth
        if len(message_history["rooms"][room]) > MAX_HISTORY_PER_ROOM:
            message_history["rooms"][room] = message_history["rooms"][room][-MAX_HISTORY_PER_ROOM:]
    
    save_message_history()


def save_dm_message(sender, recipient, message):
    """Save a DM to history"""
    key = get_dm_session_key(sender, recipient)
    with history_lock:
        if key not in message_history["dm"]:
            message_history["dm"][key] = []
        
        message_history["dm"][key].append({
            "from": sender,
            "message": message,
            "timestamp": time.time()
        })
    
    save_message_history()


def get_room_history(room, count=LOAD_HISTORY_COUNT):
    """Get last N messages from a room"""
    with history_lock:
        messages = message_history["rooms"].get(room, [])
        return messages[-count:] if messages else []


def get_dm_history(user1, user2, count=LOAD_HISTORY_COUNT):
    """Get last N DM messages between two users"""
    key = get_dm_session_key(user1, user2)
    with history_lock:
        messages = message_history["dm"].get(key, [])
        return messages[-count:] if messages else []


def send_room_history_to_client(client_socket, room, username):
    """Send room history to client when joining"""
    history = get_room_history(room, LOAD_HISTORY_COUNT)
    if history:
        history_msg = "[SERVER] === ROOM HISTORY ===\n"
        for msg in history:
            history_msg += f"{msg['user']}: {msg['message']}\n"
        history_msg += "[SERVER] === END HISTORY ===\n"
        try:
            client_socket.send(history_msg.encode('utf-8'))
        except Exception as e:
            print(f"[ERROR] Failed to send history to {username}: {e}")


def handle_dm_command(client_socket, command, sender_username):
    """Handle /msg <username> <message> command"""
    parts = command.strip().split(maxsplit=2)
    
    if len(parts) < 3:
        msg = "[ERROR] Usage: /msg <username> <message>\n"
        client_socket.send(msg.encode('utf-8'))
        return
    
    cmd = parts[0]  # '/msg'
    recipient_username = parts[1].strip()
    message = parts[2].strip()
    
    print(f"[DM] Attempting message from {sender_username} to {recipient_username}")
    
    if not message:
        msg = "[ERROR] Message cannot be empty\n"
        client_socket.send(msg.encode('utf-8'))
        return
    
    # Check if recipient exists in database
    users = load_user_database()
    if recipient_username.lower() not in users:
        msg = f"[ERROR] User '{recipient_username}' not found\n"
        client_socket.send(msg.encode('utf-8'))
        print(f"[DM] {recipient_username} not in database")
        return
    
    # Use real username for consistency
    real_recipient = users[recipient_username.lower()][0]
    
    # Check if recipient is connected via dm_clients mapping
    recipient_socket = find_recipient_socket(real_recipient)
    
    if recipient_socket is None:
        msg = f"[ERROR] User '{real_recipient}' is not online\n"
        client_socket.send(msg.encode('utf-8'))
        print(f"[DM] {real_recipient} not in dm_clients (offline)")
        return
    
    # Send to recipient
    try:
        # Encrypt DM message
        encrypted_dm = encrypt(message)
        dm_msg = f"[DM from {sender_username}]: {encrypted_dm}\n"
        recipient_socket.send(dm_msg.encode('utf-8'))
        print(f"[DM] Message sent to {real_recipient}")
    except Exception as e:
        msg = f"[ERROR] Failed to send DM to {real_recipient}\n"
        client_socket.send(msg.encode('utf-8'))
        print(f"[DM] Send failed: {e}")
        return
    
    # Confirm to sender
    confirm_msg = f"[DM → {real_recipient}]: {message}\n"
    client_socket.send(confirm_msg.encode('utf-8'))
    
    # Store DM (in-memory)
    send_dm(sender_username, real_recipient, message)
    
    # Store DM (persistent)
    save_dm_message(sender_username, real_recipient, message)
    
    print(f"[DM] SUCCESS: {sender_username} → {real_recipient}: {message}")


def handle_chat_command(client_socket, command, username, current_room):
    """Handle chat commands (/join, /leave, /rooms)"""
    parts = command.strip().split(maxsplit=1)
    
    if not parts:
        return None, current_room
    
    cmd = parts[0].lower()
    
    if cmd == '/join':
        if len(parts) < 2:
            msg = "[ERROR] Usage: /join <room>\n"
            client_socket.send(msg.encode('utf-8'))
            return None, current_room
        
        new_room = parts[1].strip()
        
        # Validate room name (alphanumeric + underscore)
        if not re.match(r'^[a-zA-Z0-9_-]+$', new_room):
            msg = "[ERROR] Invalid room name (use alphanumeric, underscore, or hyphen)\n"
            client_socket.send(msg.encode('utf-8'))
            return None, current_room
        
        # Don't rejoin same room
        if current_room == new_room:
            msg = f"[SERVER] Already in {new_room}\n"
            client_socket.send(msg.encode('utf-8'))
            return None, current_room
        
        # Notify old room that user is leaving
        leave_room(client_socket, current_room)
        leave_msg = f"[SERVER] {username} left {current_room}\n"
        broadcast_to_room(leave_msg, current_room)
        
        # Join new room
        join_room(client_socket, new_room, username)
        
        # Send confirmation to user
        confirm_msg = f"[SERVER] You joined room: {new_room}\n"
        client_socket.send(confirm_msg.encode('utf-8'))
        
        # Notify new room that user joined
        broadcast_msg = f"[SERVER] {username} joined {new_room}\n"
        broadcast_to_room(broadcast_msg, new_room, sender_socket=client_socket)
        
        print(f"[ROOM] {username} moved from {current_room} to {new_room}")
        return None, new_room
    
    elif cmd == '/leave':
        # Leave current room and go to general
        if current_room != DEFAULT_ROOM:
            leave_room(client_socket, current_room)
            join_room(client_socket, DEFAULT_ROOM, username)
            
            # Notify old room
            leave_msg = f"[SERVER] {username} left {current_room}\n"
            broadcast_to_room(leave_msg, current_room)
            
            # Notify new room
            join_msg = f"[SERVER] {username} joined {DEFAULT_ROOM}\n"
            broadcast_to_room(join_msg, DEFAULT_ROOM, sender_socket=client_socket)
            
            confirm_msg = f"[SERVER] You returned to {DEFAULT_ROOM}\n"
            client_socket.send(confirm_msg.encode('utf-8'))
            
            print(f"[ROOM] {username} left {current_room} (returned to {DEFAULT_ROOM})")
            return None, DEFAULT_ROOM
        else:
            msg = f"[SERVER] Already in {DEFAULT_ROOM}\n"
            client_socket.send(msg.encode('utf-8'))
            return None, current_room
    
    elif cmd == '/rooms':
        msg = format_rooms_list()
        client_socket.send(msg.encode('utf-8'))
        return None, current_room
        return None, current_room
    
    elif cmd == '/users':
        users = get_users_in_room(current_room)
        if users:
            user_list = ', '.join(users)
            msg = f'[SERVER] Users in {current_room}: {user_list}\n'
        else:
            msg = f'[SERVER] No users in {current_room}\n'
        client_socket.send(msg.encode('utf-8'))
        return None, current_room
    
    elif cmd == '/help':
        help_msg = get_welcome_message()
        client_socket.send(help_msg.encode('utf-8'))
        return None, current_room
    
    elif cmd == '/typing':
        # Handle typing indicator
        if len(parts) < 2:
            msg = "[ERROR] Usage: /typing on|off\n"
            client_socket.send(msg.encode('utf-8'))
            return None, current_room
        
        typing_state = parts[1].lower().strip()
        if typing_state == 'on':
            set_typing(client_socket, current_room, username, True)
            typing_msg = f"[SERVER] {username} is typing...\n"
            broadcast_to_room(typing_msg, current_room, sender_socket=client_socket)
            print(f"[TYPING] {username} is typing in {current_room}")
        elif typing_state == 'off':
            set_typing(client_socket, current_room, username, False)
            typing_msg = f"[SERVER] {username} stopped typing.\n"
            broadcast_to_room(typing_msg, current_room, sender_socket=client_socket)
            print(f"[TYPING] {username} stopped typing in {current_room}")
        else:
            msg = "[ERROR] Use: /typing on|off\n"
            client_socket.send(msg.encode('utf-8'))
        return None, current_room
    
    elif cmd == '/ack':
        # Handle read receipt acknowledgement
        if len(parts) < 2:
            return None, current_room
        
        try:
            message_id = int(parts[1])
            mark_message_read(message_id, username)
            print(f"[ACK] {username} read message {message_id}")
        except ValueError:
            pass
        return None, current_room
    
    elif cmd == '/msg':
        # Handle DM command
        handle_dm_command(client_socket, command, username)
        return None, current_room
    
    else:
        return None, current_room


def handle_login_flow(client_socket, client_address):
    """Handle LOGIN mode: username + password + auth"""
    try:
        # Request username
        client_socket.send("ENTER_USERNAME\n".encode('utf-8'))
        username = client_socket.recv(1024).decode('utf-8').strip()
        
        if not username:
            client_socket.send("REJECT_EMPTY\n".encode('utf-8'))
            return None, None
        
        # Check duplicate active connection
        with clients_lock:
            for client_info in clients.values():
                if client_info['username'].lower() == username.lower():
                    client_socket.send("REJECT_TAKEN\n".encode('utf-8'))
                    return None, None
        
        # Request password
        client_socket.send("ENTER_PASSWORD\n".encode('utf-8'))
        password = client_socket.recv(1024).decode('utf-8').strip()
        
        if not password:
            client_socket.send("REJECT_EMPTY_PASSWORD\n".encode('utf-8'))
            return None, None
        
        # Authenticate
        auth_result, authenticated_username = authenticate_user(username, password)
        
        if auth_result == 'AUTH_SUCCESS':
            client_socket.send("ACCEPT\n".encode('utf-8'))
            print(f"[AUTHENTICATED] {authenticated_username} ({client_address[0]}:{client_address[1]})")
            return authenticated_username, 'AUTH_SUCCESS'
        elif auth_result == 'AUTH_FAIL':
            client_socket.send("REJECT_PASSWORD\n".encode('utf-8'))
            return None, None
        elif auth_result == 'ACCOUNT_CREATED':
            client_socket.send("ACCEPT\n".encode('utf-8'))
            print(f"[ACCOUNT_CREATED] {authenticated_username} ({client_address[0]}:{client_address[1]})")
            return authenticated_username, 'ACCOUNT_CREATED'
        elif auth_result == 'INVALID_PASSWORD':
            client_socket.send("REJECT_WEAK_PASSWORD\n".encode('utf-8'))
            return None, None
        else:
            client_socket.send("REJECT_SERVER_ERROR\n".encode('utf-8'))
            return None, None
    
    except Exception as e:
        print(f"[ERROR] Login flow: {e}")
        return None, None


def handle_forgot_flow(client_socket, client_address):
    """Handle FORGOT mode: username only, generate token"""
    try:
        client_socket.send("ENTER_USERNAME\n".encode('utf-8'))
        username = client_socket.recv(1024).decode('utf-8').strip()
        
        if not username:
            client_socket.send("REJECT_EMPTY\n".encode('utf-8'))
            return False
        
        users = load_user_database()
        if username.lower() not in users:
            client_socket.send("[ERROR] User not found\n".encode('utf-8'))
            return False
        
        token = create_reset_token(users[username.lower()][0])
        msg = f"[SERVER] Reset token: {token} (valid {TOKEN_EXPIRATION // 60} minutes)\n"
        client_socket.send(msg.encode('utf-8'))
        print(f"[FORGOT] Generated token for {username}")
        return True
    
    except Exception as e:
        print(f"[ERROR] Forgot flow: {e}")
        return False


def handle_reset_flow(client_socket, client_address):
    """Handle RESET mode: token + new password"""
    try:
        client_socket.send("ENTER_TOKEN\n".encode('utf-8'))
        token = client_socket.recv(1024).decode('utf-8').strip()
        
        if not token:
            client_socket.send("REJECT_EMPTY\n".encode('utf-8'))
            return False
        
        username = verify_reset_token(token)
        if not username:
            client_socket.send("[ERROR] Invalid or expired token\n".encode('utf-8'))
            return False
        
        client_socket.send("ENTER_PASSWORD\n".encode('utf-8'))
        new_password = client_socket.recv(1024).decode('utf-8').strip()
        
        if not new_password:
            client_socket.send("REJECT_EMPTY_PASSWORD\n".encode('utf-8'))
            return False
        
        if not is_valid_password(new_password):
            client_socket.send("[ERROR] Password does not meet requirements\n".encode('utf-8'))
            return False
        
        new_password_hash = hash_password(new_password)
        if update_user_password(username, new_password_hash):
            consume_reset_token(token)
            msg = "[SUCCESS] Password reset successfully. Please reconnect.\n"
            client_socket.send(msg.encode('utf-8'))
            print(f"[RESET] Password reset for {username}")
            return True
        else:
            client_socket.send("[ERROR] Failed to update password\n".encode('utf-8'))
            return False
    
    except Exception as e:
        print(f"[ERROR] Reset flow: {e}")
        return False


def handle_client(client_socket, client_address):
    """Main client handler with mode selection"""
    username = None
    current_room = None
    
    try:
        # Request mode selection
        client_socket.send("SELECT_MODE\n".encode('utf-8'))
        mode = client_socket.recv(1024).decode('utf-8').strip().upper()
        
        if mode == "LOGIN":
            username, status = handle_login_flow(client_socket, client_address)
            
            if username:
                # Set default room
                current_room = DEFAULT_ROOM
                
                # Store client info in rooms/chat system
                with clients_lock:
                    clients[client_socket] = {
                        'address': client_address,
                        'username': username,
                        'room': current_room
                    }
                
                # Add to DM clients mapping
                with dm_clients_lock:
                    dm_clients[username.lower()] = client_socket
                    print(f"[DM_REGISTER] {username} added to dm_clients")
                    print(f"[DM_REGISTER] Total DM users: {list(dm_clients.keys())}")
                
                # Add to default room
                join_room(client_socket, current_room, username)
                
                # Notify others
                join_message = f"[SERVER] {username} joined {current_room}.\n"
                print(f"[CONNECTED] {username} ({client_address[0]}:{client_address[1]})")
                broadcast_to_room(join_message, current_room, sender_socket=client_socket)
                
                # Show welcome message
                welcome_msg = get_welcome_message()
                client_socket.send(welcome_msg.encode('utf-8'))
                
                # Main chat loop
                while True:
                    message = client_socket.recv(1024).decode('utf-8')
                    
                    if not message:
                        break
                    
                    message = message.strip()
                    if not message:
                        continue
                    
                    # Check for commands
                    if message.startswith('/'):
                        print(f"[CMD] {message} received from {username}")
                        cmd_result, new_room = handle_chat_command(
                            client_socket, message, username, current_room
                        )
                        # Update room if command changed it
                        if new_room is not None:
                            current_room = new_room
                            print(f"[ROOM_UPDATE] {username} now in {current_room}")
                    else:
                        # Regular message - broadcast to room only with message ID
                        msg_id = create_message_with_id(username, current_room, message)
                        # Encrypt message if not a command
                        encrypted_msg = encrypt(message) if should_encrypt_message(message) else message
                        msg_text = f"{username}: {encrypted_msg}\nMSG_ID:{msg_id}\n"
                        print(f"[{current_room}] {username}: {message} (ID: {msg_id})")
                        broadcast_to_room(msg_text, current_room)
                        
                        # Save message to history
                        save_room_message(username, current_room, message)
                        
                        # Mark as delivered to all users in room
                        with rooms_lock:
                            room_clients = list(rooms.get(current_room, []))
                        
                        with clients_lock:
                            for sock in room_clients:
                                if sock in clients and sock != client_socket:
                                    recv_user = clients[sock]['username']
                                    mark_message_delivered(msg_id, recv_user)
        
        elif mode == "FORGOT":
            handle_forgot_flow(client_socket, client_address)
        
        elif mode == "RESET":
            handle_reset_flow(client_socket, client_address)
        
        else:
            client_socket.send("[ERROR] Invalid mode. Use: LOGIN, FORGOT, or RESET\n".encode('utf-8'))
    
    except Exception as e:
        print(f"[ERROR] {client_address}: {e}")
    
    finally:
        # Remove from room
        if current_room:
            leave_room(client_socket, current_room)
        
        # Remove from DM clients mapping
        if username:
            with dm_clients_lock:
                if username.lower() in dm_clients:
                    del dm_clients[username.lower()]
                    print(f"[DM_UNREGISTER] {username} removed from dm_clients")
        
        # Remove client from main clients dict
        with clients_lock:
            if client_socket in clients:
                del clients[client_socket]
        
        client_socket.close()
        
        # Notify others
        if username and current_room:
            leave_message = f"[SERVER] {username} left {current_room}.\n"
            broadcast_to_room(leave_message, current_room)
            print(f"[DISCONNECTED] {username} ({client_address[0]}:{client_address[1]})")


def start_server():
    """Start the chat server"""
    # Load message history from disk
    load_message_history()
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        print(f"[SERVER] Listening on {HOST}:{PORT}")
        print("[SERVER] Waiting for connections...\n")
        
        while True:
            client_socket, client_address = server_socket.accept()
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address),
                daemon=False
            )
            client_thread.start()
    
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
    except Exception as e:
        print(f"[ERROR] Server error: {e}")
    finally:
        server_socket.close()
        print("[SERVER] Server stopped")


if __name__ == "__main__":
    start_server()
