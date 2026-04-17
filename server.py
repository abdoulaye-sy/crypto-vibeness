"""
Crypto Vibeness - Secure Chat Server
Stage 2: Enhanced authentication with password management
"""

import socket
import threading
import json
import logging
import signal
import os
import secrets
import base64
from datetime import datetime
from pathlib import Path
from password_manager import PasswordManager, PasswordValidator, PasswordRulesEngine, KeyManager
from encryption import MessageEncryption
from asymmetric_crypto import AsymmetricCrypto

# Color mapping for usernames (must match client.py)
COLOR_LIST = ["green", "yellow", "blue", "magenta", "cyan"]

def get_username_color(username):
    """Get color name for username (deterministic based on hash)"""
    color_idx = hash(username) % len(COLOR_LIST)
    return COLOR_LIST[color_idx]

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Create timestamped log file
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_file = os.path.join(logs_dir, f'log_{timestamp}.txt')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"=" * 50)
logger.info(f"Server started - Log file: {log_file}")
logger.info(f"=" * 50)

HOST = '127.0.0.1'
PORT = 5001

class AuthManager:
    """Manages user authentication with password management"""
    
    def __init__(self, credentials_file='this_is_safe.txt', rules_file='password_rules.txt'):
        self.password_manager = PasswordManager(credentials_file)
        self.rules_engine = PasswordRulesEngine(rules_file)
        self.validator = PasswordValidator(self.rules_engine)
        self.lock = threading.Lock()
    
    def account_exists(self, username):
        """Check if account exists"""
        with self.lock:
            return self.password_manager.account_exists(username)
    
    def create_account(self, username, password):
        """Create new account with password validation"""
        with self.lock:
            # Validate password strength first
            is_valid, errors = self.validator.validate(password)
            if not is_valid:
                return False, errors
            
            # Create account
            created = self.password_manager.create_account(username, password)
            if created:
                logger.info(f"Account created: {username}")
            return created, []
    
    def verify_account(self, username, password):
        """Verify username and password"""
        with self.lock:
            if not self.password_manager.account_exists(username):
                return False
            return self.password_manager.verify_account(username, password)
    
    def get_password_strength(self, password):
        """Get password strength indicator"""
        score, strength, details = self.validator.get_strength(password)
        return strength, details
    
    def get_password_rules(self):
        """Get list of password rules"""
        return self.rules_engine.get_rules_summary()

class Room:
    def __init__(self, name, is_private=False, password=None):
        self.name = name
        self.is_private = is_private
        self.password = password
        self.clients = []
        self.lock = threading.Lock()

    def add_client(self, client):
        with self.lock:
            self.clients.append(client)

    def remove_client(self, client):
        with self.lock:
            if client in self.clients:
                self.clients.remove(client)

    def broadcast(self, message, sender=None, include_sender=False):
        with self.lock:
            for client in self.clients:
                if include_sender or client != sender:
                    try:
                        client.send(message)
                    except:
                        pass

class Client:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.username = None
        self.authenticated = False
        self.room = None
        self.public_key = None  # RSA public key from client
        self.symmetric_key = None  # Symmetric key for this session

    def send(self, message):
        try:
            self.conn.sendall(message.encode('utf-8') + b'\n')
        except:
            pass

    def receive(self):
        try:
            data = self.conn.recv(1024)
            if not data:
                return None
            return data.decode('utf-8').strip()
        except:
            return None

class Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.auth_manager = AuthManager()  # Add authentication
        self.rooms = {}
        self.clients = {}
        self.usernames = set()
        self.lock = threading.Lock()
        self.socket = None
        self.running = True

    def signal_handler(self, sig, frame):
        logger.info("Shutdown signal received")
        self.running = False
        if self.socket:
            self.socket.close()

    def start(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        self.socket.settimeout(1.0)
        logger.info(f"Server started on {self.host}:{self.port}")

        try:
            while self.running:
                try:
                    conn, addr = self.socket.accept()
                    if not self.running:
                        conn.close()
                        break
                    logger.info(f"New connection from {addr}")
                    client = Client(conn, addr)
                    thread = threading.Thread(target=self.handle_client, args=(client,))
                    thread.daemon = True
                    thread.start()
                except socket.timeout:
                    continue
                except OSError:
                    if self.running:
                        raise
                    break
        except Exception as e:
            if self.running:
                logger.error(f"Server error: {e}")
        finally:
            logger.info("Server shutting down")
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass

    def get_or_create_room(self, room_name, is_private=False, password=None):
        with self.lock:
            if room_name not in self.rooms:
                self.rooms[room_name] = Room(room_name, is_private, password)
                privacy_str = "PRIVATE" if is_private else "PUBLIC"
                logger.info(f"Room '{room_name}' created ({privacy_str})")
            return self.rooms[room_name]

    def authenticate_client(self, client):
        """Authenticate client: login existing account or create new account with validation"""
        logger.info(f"Authentication started for {client.addr}")
        
        while True:
            # Request username
            client.send("AUTH:")
            username = client.receive()
            if not username:
                return None
            
            username = username.strip()
            if not username or len(username) < 1:
                client.send("ERROR:Invalid username")
                continue
            
            # Check if account exists
            if self.auth_manager.account_exists(username):
                # Existing account - ask for password
                logger.info(f"Login attempt: {username}")
                client.send("PASSWORD:")
                password = client.receive()
                if not password:
                    return None
                
                # Verify password (with retry loop)
                while True:
                    if self.auth_manager.verify_account(username, password):
                        logger.info(f"User authenticated: {username}")
                        client.send("OK:Authenticated")
                        return username
                    else:
                        logger.warning(f"Failed password for {username}")
                        client.send("ERROR:Invalid password\nPASSWORD:")
                        password = client.receive()
                        if not password:
                            return None
            else:
                # New account - ask for creation
                logger.info(f"New account signup: {username}")
                client.send("CREATE_ACCOUNT?")
                response = client.receive()
                if not response or response.strip().lower() != "yes":
                    continue
                
                # Password creation loop with validation
                password_valid = False
                while not password_valid:
                    # Get password
                    client.send("PASSWORD:")
                    password = client.receive()
                    if not password:
                        return None
                    password = password.strip()
                    
                    # Validate password strength
                    strength, details = self.auth_manager.get_password_strength(password)
                    client.send(f"PASSWORD_STRENGTH:{strength}")
                    
                    # Check validation
                    is_valid, errors = self.auth_manager.validator.validate(password)
                    if not is_valid:
                        error_msg = "\n".join(errors)
                        client.send(f"ERROR:Password too weak\n{error_msg}\nRETRY_PASSWORD:")
                        password_valid = False
                    else:
                        # Password is valid, ask for confirmation
                        client.send("CONFIRM_PASSWORD:")
                        confirm = client.receive()
                        if not confirm:
                            return None
                        confirm = confirm.strip()
                        
                        # Check if passwords match
                        if password != confirm:
                            client.send("ERROR:Passwords don't match\nRETRY_PASSWORD:")
                            password_valid = False
                        else:
                            password_valid = True
                
                # Create account
                created, errors = self.auth_manager.create_account(username, password)
                if created:
                    logger.info(f"Account created: {username}")
                    client.send("OK:Account created\nOK:Authenticated")
                    return username
                else:
                    client.send("ERROR:Failed to create account")
                    continue
    
    def exchange_symmetric_key(self, client):
        """Exchange RSA public key and establish symmetric key"""
        try:
            crypto = AsymmetricCrypto()
            
            # Request client's public key
            client.send("PUBKEY:")
            pubkey_b64 = client.receive()
            if not pubkey_b64:
                logger.warning(f"Failed to receive public key from {client.username}")
                return False
            
            # Deserialize public key
            try:
                client.public_key = crypto.deserialize_public_key(pubkey_b64)
            except Exception as e:
                logger.error(f"Failed to deserialize public key: {e}")
                return False
            
            # Generate symmetric key (16 bytes for AES-256-CBC)
            client.symmetric_key = secrets.token_bytes(16)
            
            # Encrypt symmetric key with client's public key
            try:
                encrypted_key = crypto.encrypt_with_public_key(client.symmetric_key, client.public_key)
                encrypted_key_b64 = base64.b64encode(encrypted_key).decode('utf-8')
                client.send(f"SYMKEY:{encrypted_key_b64}")
                logger.info(f"Symmetric key exchanged with {client.username}")
                return True
            except Exception as e:
                logger.error(f"Failed to encrypt symmetric key: {e}")
                return False
        
        except Exception as e:
            logger.error(f"Key exchange error: {e}")
            return False

    def handle_client(self, client):
        try:
            # Phase 1: Authentication
            username = self.authenticate_client(client)
            if not username:
                logger.warning(f"Authentication failed for {client.addr}")
                return
            
            client.username = username
            client.authenticated = True
            
            with self.lock:
                self.usernames.add(username)
                self.clients[client.addr] = client
            
            logger.info(f"User {username} connected and authenticated")
            
            # Phase 1b: Asymmetric key exchange
            if not self.exchange_symmetric_key(client):
                logger.warning(f"Key exchange failed for {username}")
                return
            
            # Phase 2: Room selection (existing flow)
            while True:
                client.send("ROOM:")
                message = client.receive()
                if not message:
                    return

                room_name = message.strip() or "general"
                
                with self.lock:
                    room_exists = room_name in self.rooms
                
                # "general" room is always public
                if room_name == "general" and not room_exists:
                    room = self.get_or_create_room(room_name, is_private=False)
                elif not room_exists:
                    # New room - ask if private
                    client.send("PRIVATE?:yes/no")
                    privacy_response = client.receive()
                    if not privacy_response:
                        return
                    
                    is_private = privacy_response.strip().lower() == "yes"
                    password = None
                    
                    if is_private:
                        client.send("PASSWORD:")
                        password = client.receive()
                        if not password:
                            return
                        password = password.strip()
                    
                    room = self.get_or_create_room(room_name, is_private, password)
                else:
                    # Existing room
                    room = self.rooms[room_name]
                    if room.is_private:
                        while True:
                            client.send("PASSWORD:")
                            provided_password = client.receive()
                            if not provided_password:
                                return
                            
                            if provided_password.strip() == room.password:
                                break
                            else:
                                client.send("ERROR:Incorrect password")
                
                client.room = room
                room.add_client(client)

                logger.info(f"User {username} joined room {room_name}")
                
                # Notify room
                timestamp = datetime.now().strftime("%H:%M:%S")
                notification = json.dumps({
                    "type": "system",
                    "message": f"{username} joined the room",
                    "timestamp": timestamp
                })
                room.broadcast(notification, sender=client)
                privacy_marker = "🔒" if room.is_private else "🔓"
                client.send(f"OK:Connected to {room_name}|{privacy_marker}")
                break

            # Handle messages
            while True:
                message = client.receive()
                if not message:
                    break

                # Check for room change command
                if message.startswith("/room "):
                    new_room_name = message[6:].strip()
                    if not new_room_name:
                        client.send("ERROR:Room name cannot be empty")
                        continue
                    
                    with self.lock:
                        room_exists = new_room_name in self.rooms
                    
                    # Leave current room
                    old_room = client.room
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    notification = json.dumps({
                        "type": "system",
                        "message": f"{username} left the room",
                        "timestamp": timestamp
                    })
                    old_room.broadcast(notification)
                    old_room.remove_client(client)
                    
                    # "general" room is always public
                    if new_room_name == "general" and not room_exists:
                        new_room = self.get_or_create_room(new_room_name, is_private=False)
                    elif not room_exists:
                        # New room - ask if private
                        client.send("PRIVATE?:yes/no")
                        privacy_response = client.receive()
                        if not privacy_response:
                            return
                        
                        is_private = privacy_response.strip().lower() == "yes"
                        password = None
                        
                        if is_private:
                            client.send("PASSWORD:")
                            password = client.receive()
                            if not password:
                                return
                            password = password.strip()
                        
                        new_room = self.get_or_create_room(new_room_name, is_private, password)
                    else:
                        # Existing room
                        new_room = self.rooms[new_room_name]
                        if new_room.is_private:
                            while True:
                                client.send("PASSWORD:")
                                provided_password = client.receive()
                                if not provided_password:
                                    return
                                
                                if provided_password.strip() == new_room.password:
                                    break
                                else:
                                    client.send("ERROR:Incorrect password\nPASSWORD:")
                    
                    # Join new room
                    client.room = new_room
                    new_room.add_client(client)
                    
                    logger.info(f"User {username} switched to room {new_room_name}")
                    
                    notification = json.dumps({
                        "type": "system",
                        "message": f"{username} joined the room",
                        "timestamp": timestamp
                    })
                    new_room.broadcast(notification, sender=client)
                    privacy_marker = "🔒" if new_room.is_private else "🔓"
                    client.send(f"OK:Switched to {new_room_name}|{privacy_marker}")
                elif message.startswith("/pubkey "):
                    # Get public key of another user
                    target_username = message[8:].strip()
                    target_client = None
                    
                    # Find the client in all connected clients
                    with self.lock:
                        for room in self.rooms.values():
                            for c in room.clients:
                                if c.username == target_username:
                                    target_client = c
                                    break
                    
                    if target_client and target_client.public_key:
                        from asymmetric_crypto import AsymmetricCrypto
                        crypto = AsymmetricCrypto()
                        pubkey_b64 = crypto.serialize_public_key(target_client.public_key)
                        response = json.dumps({
                            "type": "pubkey",
                            "username": target_username,
                            "public_key": pubkey_b64
                        })
                        client.send(response)
                    else:
                        client.send(json.dumps({
                            "type": "error",
                            "message": f"User {target_username} not found or key unavailable"
                        }))
                elif message.startswith("/dm "):
                    # Direct message to another user (1-to-1)
                    parts = message[4:].split(" ", 1)
                    if len(parts) < 2:
                        client.send(json.dumps({
                            "type": "error",
                            "message": "Usage: /dm <username> <message>"
                        }))
                        continue
                    
                    target_username = parts[0]
                    dm_content = parts[1]
                    target_client = None
                    
                    # Find target user
                    with self.lock:
                        for room in self.rooms.values():
                            for c in room.clients:
                                if c.username == target_username:
                                    target_client = c
                                    break
                    
                    if target_client:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        dm_data = json.dumps({
                            "type": "dm",
                            "from": username,
                            "to": target_username,
                            "message": dm_content,
                            "timestamp": timestamp
                        })
                        target_client.send(dm_data)
                        client.send(json.dumps({
                            "type": "system",
                            "message": f"DM sent to {target_username}"
                        }))
                        logger.info(f"DM from {username} to {target_username}: {dm_content}")
                    else:
                        client.send(json.dumps({
                            "type": "error",
                            "message": f"User {target_username} not found or offline"
                        }))
                else:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    # Decrypt message if symmetric key available
                    sanitized_message = message.strip().replace('\n', ' ').replace('\r', '')
                    if client.symmetric_key:
                        try:
                            sanitized_message = MessageEncryption.decrypt_message(sanitized_message, client.symmetric_key)
                        except Exception as e:
                            logger.error(f"Decryption error for {username}: {e}")
                            client.send("ERROR:Decryption failed")
                            continue
                    
                    msg_data = json.dumps({
                        "type": "message",
                        "username": username,
                        "color": get_username_color(username),
                        "room": client.room.name,
                        "message": sanitized_message,
                        "timestamp": timestamp
                    })

                    logger.info(f"[{client.room.name}] {username}: {sanitized_message}")
                    client.room.broadcast(msg_data, sender=client, include_sender=True)
                    client.send("OK:")

        except Exception as e:
            logger.error(f"Error handling client {client.addr}: {e}")
        finally:
            if client.room:
                client.room.remove_client(client)
                if client.username:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    notification = json.dumps({
                        "type": "system",
                        "message": f"{client.username} left the room",
                        "timestamp": timestamp
                    })
                    client.room.broadcast(notification)
                    logger.info(f"User {client.username} disconnected")

            with self.lock:
                if client.addr in self.clients:
                    del self.clients[client.addr]
                if client.username:
                    self.usernames.discard(client.username)
            
            try:
                client.conn.close()
            except:
                pass

if __name__ == "__main__":
    server = Server(HOST, PORT)
    server.start()
