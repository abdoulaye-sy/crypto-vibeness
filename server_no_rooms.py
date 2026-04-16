import socket
import threading
import sys
import re
import os
import bcrypt
import random
import time

# Dictionary to store connected clients
clients = {}
clients_lock = threading.Lock()

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


def broadcast(message, sender_socket=None):
    """Send message to all connected clients except sender"""
    with clients_lock:
        for client_socket in list(clients.keys()):
            if client_socket != sender_socket:
                try:
                    client_socket.send(message.encode('utf-8'))
                except:
                    pass


def is_username_taken(username):
    """Check if username is already in use (active connection)"""
    with clients_lock:
        for client_info in clients.values():
            if client_info['username'].lower() == username.lower():
                return True
    return False


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
        if is_username_taken(username):
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
        # Request username
        client_socket.send("ENTER_USERNAME\n".encode('utf-8'))
        username = client_socket.recv(1024).decode('utf-8').strip()
        
        if not username:
            client_socket.send("REJECT_EMPTY\n".encode('utf-8'))
            return False
        
        # Check if user exists
        users = load_user_database()
        if username.lower() not in users:
            client_socket.send("[ERROR] User not found\n".encode('utf-8'))
            return False
        
        # Generate and send token
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
        # Request token
        client_socket.send("ENTER_TOKEN\n".encode('utf-8'))
        token = client_socket.recv(1024).decode('utf-8').strip()
        
        if not token:
            client_socket.send("REJECT_EMPTY\n".encode('utf-8'))
            return False
        
        # Verify token
        username = verify_reset_token(token)
        if not username:
            client_socket.send("[ERROR] Invalid or expired token\n".encode('utf-8'))
            return False
        
        # Request new password
        client_socket.send("ENTER_PASSWORD\n".encode('utf-8'))
        new_password = client_socket.recv(1024).decode('utf-8').strip()
        
        if not new_password:
            client_socket.send("REJECT_EMPTY_PASSWORD\n".encode('utf-8'))
            return False
        
        # Validate password strength
        if not is_valid_password(new_password):
            client_socket.send("[ERROR] Password does not meet requirements\n".encode('utf-8'))
            return False
        
        # Hash and update password
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
    
    try:
        # Request mode selection
        client_socket.send("SELECT_MODE\n".encode('utf-8'))
        mode = client_socket.recv(1024).decode('utf-8').strip().upper()
        
        if mode == "LOGIN":
            username, status = handle_login_flow(client_socket, client_address)
            
            if username:
                # Store client info
                with clients_lock:
                    clients[client_socket] = {'address': client_address, 'username': username}
                
                # Notify others
                join_message = f"[SERVER] {username} joined the chat.\n"
                print(f"[CONNECTED] {username} ({client_address[0]}:{client_address[1]})")
                broadcast(join_message)
                
                # Main chat loop
                while True:
                    message = client_socket.recv(1024).decode('utf-8')
                    if not message:
                        break
                    print(f"[{username}] {message.strip()}")
                    broadcast(f"[{username}] {message}")
        
        elif mode == "FORGOT":
            handle_forgot_flow(client_socket, client_address)
        
        elif mode == "RESET":
            handle_reset_flow(client_socket, client_address)
        
        else:
            client_socket.send("[ERROR] Invalid mode. Use: LOGIN, FORGOT, or RESET\n".encode('utf-8'))
    
    except Exception as e:
        print(f"[ERROR] {client_address}: {e}")
    
    finally:
        # Remove client
        with clients_lock:
            if client_socket in clients:
                del clients[client_socket]
        
        client_socket.close()
        
        # Notify others
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
