import socket
import threading
import sys
import re
import os
import bcrypt
import random
import time

# Dictionary to store connected clients
# Key: client socket, Value: {'address': (ip, port), 'username': username}
clients = {}
clients_lock = threading.Lock()

# Dictionary to store password reset tokens
# Key: token, Value: {'username': username, 'expiration': timestamp}
reset_tokens = {}
reset_tokens_lock = threading.Lock()

HOST = 'localhost'
PORT = 5000
USER_DB_FILE = 'this_is_safe.txt'

# Password validation rules
MIN_PASSWORD_LENGTH = 8

# Bcrypt configuration
BCRYPT_ROUNDS = 12

# Reset token configuration
TOKEN_EXPIRATION = 600  # 10 minutes in seconds
TOKEN_LENGTH = 6


def hash_password(password):
    """Hash password using bcrypt (secure alternative to MD5)"""
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
    """Validate password meets requirements"""
    if len(password) < MIN_PASSWORD_LENGTH:
        return False
    
    # Check for at least 1 number
    if not re.search(r'\d', password):
        return False
    
    # Check for at least 1 special character
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
    """Save user to database"""
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
        
        # Read current file
        with open(USER_DB_FILE, 'r') as f:
            lines = f.readlines()
        
        # Rewrite file with updated password
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
    """Generate a random numeric token"""
    return ''.join([str(random.randint(0, 9)) for _ in range(TOKEN_LENGTH)])


def create_reset_token(username):
    """Create a password reset token for user"""
    token = generate_reset_token()
    expiration = time.time() + TOKEN_EXPIRATION
    
    with reset_tokens_lock:
        reset_tokens[token] = {
            'username': username,
            'expiration': expiration
        }
    
    return token


def verify_reset_token(token):
    """Verify if token is valid and not expired"""
    with reset_tokens_lock:
        if token not in reset_tokens:
            return None
        
        token_data = reset_tokens[token]
        
        if time.time() > token_data['expiration']:
            # Token expired, remove it
            del reset_tokens[token]
            return None
        
        return token_data['username']


def consume_reset_token(token):
    """Remove token after use (one-time use)"""
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
    """Authenticate user or create new account if doesn't exist"""
    users = load_user_database()
    username_lower = username.lower()
    
    if username_lower in users:
        # User exists, verify password
        stored_username, stored_hash = users[username_lower]
        if verify_password(password, stored_hash):
            return 'AUTH_SUCCESS', stored_username
        else:
            return 'AUTH_FAIL', None
    else:
        # User doesn't exist, create new account
        if not is_valid_password(password):
            return 'INVALID_PASSWORD', None
        
        password_hash = hash_password(password)
        if save_user(username, password_hash):
            return 'ACCOUNT_CREATED', username
        else:
            return 'SAVE_FAIL', None


def handle_forgot_password(username):
    """Handle forgot password request"""
    users = load_user_database()
    username_lower = username.lower()
    
    if username_lower not in users:
        return 'USER_NOT_FOUND', None
    
    # Generate reset token
    token = create_reset_token(users[username_lower][0])
    return 'TOKEN_GENERATED', token


def handle_reset_password(token, new_password):
    """Handle password reset with token"""
    if not is_valid_password(new_password):
        return 'INVALID_PASSWORD', None
    
    # Verify token
    username = verify_reset_token(token)
    if not username:
        return 'INVALID_TOKEN', None
    
    # Hash new password
    new_password_hash = hash_password(new_password)
    
    # Update password in database
    if update_user_password(username, new_password_hash):
        consume_reset_token(token)
        return 'RESET_SUCCESS', username
    else:
        return 'UPDATE_FAILED', None


def broadcast(message, sender_socket=None):
    """Send message to all connected clients except sender"""
    with clients_lock:
        for client_socket in list(clients.keys()):
            if client_socket != sender_socket:
                try:
                    client_socket.send(message.encode('utf-8'))
                except:
                    # Client might have disconnected
                    pass


def is_username_taken(username):
    """Check if username is already in use (by active connection)"""
    with clients_lock:
        for client_info in clients.values():
            if client_info['username'].lower() == username.lower():
                return True
    return False


def handle_client_command(client_socket, command, client_info):
    """Handle client commands (forgot, reset, etc.)"""
    parts = command.split()
    
    if not parts:
        return None
    
    cmd = parts[0].lower()
    
    if cmd == '/forgot':
        if len(parts) < 2:
            return 'ERROR_FORGOT_USAGE'
        
        username = parts[1]
        result, token = handle_forgot_password(username)
        
        if result == 'USER_NOT_FOUND':
            return 'ERROR_USER_NOT_FOUND'
        elif result == 'TOKEN_GENERATED':
            minutes = TOKEN_EXPIRATION // 60
            return f'TOKEN_SENT:{token}:{minutes}'
        return 'ERROR_FORGOT'
    
    elif cmd == '/reset':
        if len(parts) < 3:
            return 'ERROR_RESET_USAGE'
        
        token = parts[1]
        new_password = ' '.join(parts[2:])
        result, data = handle_reset_password(token, new_password)
        
        if result == 'INVALID_PASSWORD':
            return 'ERROR_WEAK_PASSWORD'
        elif result == 'INVALID_TOKEN':
            return 'ERROR_INVALID_TOKEN'
        elif result == 'RESET_SUCCESS':
            return 'RESET_SUCCESS'
        return 'ERROR_RESET'
    
    return None


def handle_client(client_socket, client_address):
    """Handle communication with a single client"""
    username = None
    
    try:
        # Request username from client
        client_socket.send("ENTER_USERNAME\n".encode('utf-8'))
        
        # Receive username
        username = client_socket.recv(1024).decode('utf-8').strip()
        
        if not username:
            client_socket.send("REJECT_EMPTY\n".encode('utf-8'))
            return
        
        # Check for commands before authentication
        if username.startswith('/'):
            result = handle_client_command(client_socket, username, None)
            if result:
                if result.startswith('TOKEN_SENT:'):
                    parts = result.split(':')
                    token = parts[1]
                    minutes = parts[2]
                    msg = f"[SERVER] Reset token: {token} (valid {minutes} minutes)\n"
                    client_socket.send(msg.encode('utf-8'))
                elif result == 'ERROR_USER_NOT_FOUND':
                    client_socket.send("[ERROR] User not found\n".encode('utf-8'))
                elif result == 'ERROR_FORGOT_USAGE':
                    client_socket.send("[ERROR] Usage: /forgot <username>\n".encode('utf-8'))
                else:
                    client_socket.send(f"[ERROR] {result}\n".encode('utf-8'))
            return
        
        # Check for duplicate active connection
        if is_username_taken(username):
            client_socket.send("REJECT_TAKEN\n".encode('utf-8'))
            return
        
        # Accept username and request password
        client_socket.send("ENTER_PASSWORD\n".encode('utf-8'))
        
        # Receive password
        password = client_socket.recv(1024).decode('utf-8').strip()
        
        if not password:
            client_socket.send("REJECT_EMPTY_PASSWORD\n".encode('utf-8'))
            return
        
        # Check for reset command during password entry
        if password.startswith('/reset'):
            result = handle_client_command(client_socket, password, None)
            if result:
                if result == 'RESET_SUCCESS':
                    msg = "[SUCCESS] Password reset successfully. Please reconnect.\n"
                    client_socket.send(msg.encode('utf-8'))
                elif result == 'ERROR_WEAK_PASSWORD':
                    client_socket.send("[ERROR] Password does not meet requirements\n".encode('utf-8'))
                elif result == 'ERROR_INVALID_TOKEN':
                    client_socket.send("[ERROR] Invalid or expired token\n".encode('utf-8'))
                else:
                    client_socket.send(f"[ERROR] {result}\n".encode('utf-8'))
            return
        
        # Authenticate or create account
        auth_result, authenticated_username = authenticate_user(username, password)
        
        if auth_result == 'AUTH_SUCCESS':
            client_socket.send("ACCEPT\n".encode('utf-8'))
            print(f"[AUTHENTICATED] {authenticated_username} ({client_address[0]}:{client_address[1]})")
        elif auth_result == 'AUTH_FAIL':
            client_socket.send("REJECT_PASSWORD\n".encode('utf-8'))
            return
        elif auth_result == 'ACCOUNT_CREATED':
            client_socket.send("ACCEPT\n".encode('utf-8'))
            print(f"[ACCOUNT_CREATED] {authenticated_username} ({client_address[0]}:{client_address[1]})")
        elif auth_result == 'INVALID_PASSWORD':
            client_socket.send("REJECT_WEAK_PASSWORD\n".encode('utf-8'))
            return
        else:
            client_socket.send("REJECT_SERVER_ERROR\n".encode('utf-8'))
            return
        
        # Store client info
        with clients_lock:
            clients[client_socket] = {
                'address': client_address,
                'username': authenticated_username
            }
        
        # Notify all clients that user joined
        join_message = f"[SERVER] {authenticated_username} joined the chat.\n"
        print(f"[CONNECTED] {authenticated_username} ({client_address[0]}:{client_address[1]})")
        broadcast(join_message)
        
        # Periodic cleanup of expired tokens
        clean_expired_tokens()
        
        # Main message loop
        while True:
            message = client_socket.recv(1024).decode('utf-8')
            
            if not message:
                # Client disconnected
                break
            
            # Display message on server
            print(f"[{authenticated_username}] {message.strip()}")
            
            # Broadcast to other clients with username
            broadcast(f"[{authenticated_username}] {message}")
    
    except Exception as e:
        print(f"[ERROR] {client_address}: {e}")
    
    finally:
        # Remove client from dictionary
        with clients_lock:
            if client_socket in clients:
                del clients[client_socket]
        
        client_socket.close()
        
        # Notify other clients that user left
        if username:
            leave_message = f"[SERVER] {username} left the chat.\n"
            broadcast(leave_message)
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
            # Accept incoming connection
            client_socket, client_address = server_socket.accept()
            
            # Create a thread to handle this client
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
