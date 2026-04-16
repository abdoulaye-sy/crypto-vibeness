import socket
import threading
import sys
import re
import os
import bcrypt
import random
import time

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

HOST = 'localhost'
PORT = 5000
USER_DB_FILE = 'this_is_safe.txt'

MIN_PASSWORD_LENGTH = 8
BCRYPT_ROUNDS = 12
TOKEN_EXPIRATION = 600
TOKEN_LENGTH = 6
DEFAULT_ROOM = 'general'


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
            '- /help    -> show this help message\n'
            '\n'
            'Current room: general\n')


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
                
                # Store client info
                with clients_lock:
                    clients[client_socket] = {
                        'address': client_address,
                        'username': username,
                        'room': current_room
                    }
                
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
                        # Regular message - broadcast to room only
                        print(f"[{current_room}] {username}: {message}")
                        broadcast_to_room(f"{username}: {message}\n", current_room)
        
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
        
        # Remove client
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
