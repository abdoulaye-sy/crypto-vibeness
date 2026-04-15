import socket
import threading
import sys
import hashlib
import re
import os

# Dictionary to store connected clients
# Key: client socket, Value: {'address': (ip, port), 'username': username}
clients = {}
clients_lock = threading.Lock()

HOST = 'localhost'
PORT = 5000
USER_DB_FILE = 'this_is_safe.txt'

# Password validation rules
MIN_PASSWORD_LENGTH = 8


def hash_password(password):
    """Hash password using MD5"""
    return hashlib.md5(password.encode()).hexdigest()


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


def authenticate_user(username, password):
    """Authenticate user or create new account if doesn't exist"""
    users = load_user_database()
    username_lower = username.lower()
    
    if username_lower in users:
        # User exists, verify password
        stored_username, stored_hash = users[username_lower]
        password_hash = hash_password(password)
        if password_hash == stored_hash:
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
