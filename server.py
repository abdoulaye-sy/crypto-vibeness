#!/usr/bin/env python3
"""
Multi-client chat server with room support and event logging.
Day 1 - Part 1: Basic IRC-like chat without encryption or authentication.

================================================================================
JSON PROTOCOL SPECIFICATION
================================================================================

All client-server communication uses JSON messages with the following structure:

    {
        "type": "MESSAGE_TYPE",
        "data": { /* type-specific data */ },
        "timestamp": "ISO-8601 timestamp"
    }

MESSAGE TYPES:
--------------

1. AUTH (Client → Server)
   Used to authenticate with a username.
   {
       "type": "AUTH",
       "data": {"username": "alice"},
       "timestamp": "2024-04-15T09:40:00"
   }

2. JOIN_ROOM (Client → Server)
   Request to join a specific room.
   {
       "type": "JOIN_ROOM",
       "data": {"room": "general", "password": null},
       "timestamp": "2024-04-15T09:40:00"
   }

3. CREATE_ROOM (Client → Server)
   Request to create a new room (optionally password-protected).
   {
       "type": "CREATE_ROOM",
       "data": {"room": "vip_lounge", "password": "secret123"},
       "timestamp": "2024-04-15T09:40:00"
   }

4. CHAT_MESSAGE (Client → Server / Server → Client)
   User chat message.
   {
       "type": "CHAT_MESSAGE",
       "data": {"username": "alice", "room": "general", "text": "Hello!"},
       "timestamp": "2024-04-15T09:40:00"
   }

5. ROOM_LIST (Server → Client)
   List of available rooms in response to user request.
   {
       "type": "ROOM_LIST",
       "data": {
           "rooms": [
               {"name": "general", "protected": false, "users": 5},
               {"name": "admin", "protected": true, "users": 2}
           ]
       },
       "timestamp": "2024-04-15T09:40:00"
   }

6. USER_LIST (Server → Client)
   List of users in a specific room.
   {
       "type": "USER_LIST",
       "data": {
           "room": "general",
           "users": [
               {"username": "alice", "color": "\033[32m"},
               {"username": "bob", "color": "\033[34m"}
           ]
       },
       "timestamp": "2024-04-15T09:40:00"
   }

7. SERVER_INFO (Server → Client)
   Server sends user info (e.g., assigned color, username confirmation).
   {
       "type": "SERVER_INFO",
       "data": {"username": "alice", "color": "\033[32m", "current_room": "general"},
       "timestamp": "2024-04-15T09:40:00"
   }

8. ERROR (Server → Client)
   Error response for failed operations.
   {
       "type": "ERROR",
       "data": {"message": "Username already taken", "code": "USERNAME_TAKEN"},
       "timestamp": "2024-04-15T09:40:00"
   }

================================================================================
"""

import socket
import threading
import sys
import logging
import json
import hashlib
import base64
import hmac
import os
from datetime import datetime
from typing import Dict, Optional, Set, Tuple
from dataclasses import dataclass
from pathlib import Path
from password_validator import validate_password

# Configuration
CONFIG = {
    'HOST': '0.0.0.0',
    'PORT': 5000,
    'BUFFER_SIZE': 4096,
    'MAX_CONNECTIONS': 50,
}

# Available ANSI colors (16-color palette)
COLORS = [
    '\033[32m',   # Green
    '\033[34m',   # Blue
    '\033[33m',   # Yellow
    '\033[35m',   # Magenta
    '\033[36m',   # Cyan
    '\033[31m',   # Red
    '\033[1;32m', # Bright Green
    '\033[1;34m', # Bright Blue
    '\033[1;33m', # Bright Yellow
    '\033[1;35m', # Bright Magenta
    '\033[1;36m', # Bright Cyan
    '\033[1;31m', # Bright Red
    '\033[37m',   # White
    '\033[30m',   # Black
    '\033[1;37m', # Bright White
]
COLOR_RESET = '\033[0m'

# Room passwords (None = no password)
PROTECTED_ROOMS = {
    'general': None,
    'admin': 'admin123',
    'vip': 'vip_pass',
}


@dataclass
class User:
    """Represents a connected user."""
    username: str
    socket: socket.socket
    address: Tuple[str, int]
    room: str = 'general'
    color_code: str = ''  # ANSI color code as string
    
    def get_colored_name(self) -> str:
        """Return username with ANSI color code."""
        return f"{self.color_code}{self.username}{COLOR_RESET}"
    
    def to_dict(self) -> Dict:
        """Serialize user info for sending to clients."""
        return {
            'username': self.username,
            'color_code': self.color_code,
            'room': self.room
        }


class ChatServer:
    """Multi-client chat server with room support and authentication."""
    
    CREDENTIALS_FILE = 'this_is_safe.txt'
    MAX_LOGIN_ATTEMPTS = 3
    
    def __init__(self, port: int = CONFIG['PORT']):
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.users: Dict[str, User] = {}  # username -> User
        self.users_lock = threading.Lock()
        self.rooms: Dict[str, Set[str]] = {
            room: set() for room in PROTECTED_ROOMS.keys()
        }  # room_name -> set of usernames
        self.rooms_lock = threading.Lock()
        
        # Setup logging first (before loading credentials)
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        self.log_file = f'log_{timestamp}.txt'
        self.setup_logging()
        
        # Credentials storage (username -> base64_md5_hash)
        self.credentials: Dict[str, str] = {}
        self.credentials_lock = threading.Lock()
        self._load_credentials()
        
        self.logger.info(f"Server initialized on port {self.port}")
        self.logger.info(f"Protected rooms: {list(PROTECTED_ROOMS.keys())}")
        self.logger.info(f"Loaded {len(self.credentials)} registered users")
    
    def _load_credentials(self) -> None:
        """Load user credentials from this_is_safe.txt."""
        if not os.path.exists(self.CREDENTIALS_FILE):
            self.logger.info(f"Credentials file not found - will be created on first registration")
            return
        
        try:
            with open(self.CREDENTIALS_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and ':' in line:
                        username, pwd_hash = line.split(':', 1)
                        self.credentials[username] = pwd_hash
        except Exception as e:
            self.logger.error(f"Error loading credentials: {e}")
    
    def _save_credentials(self) -> None:
        """Save user credentials to this_is_safe.txt."""
        try:
            with open(self.CREDENTIALS_FILE, 'w') as f:
                for username, pwd_hash in sorted(self.credentials.items()):
                    f.write(f"{username}:{pwd_hash}\n")
            # Note: Removed logging here to debug potential lock issues
        except Exception as e:
            self.logger.error(f"Error saving credentials: {e}")
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """
        Hash password using MD5 and encode as Base64.
        WARNING: MD5 is intentionally weak - for educational purposes only!
        """
        md5_hash = hashlib.md5(password.encode('utf-8')).digest()
        return base64.b64encode(md5_hash).decode('utf-8')
    
    @staticmethod
    def _verify_password_constant_time(password: str, stored_hash: str) -> bool:
        """
        Verify password using constant-time comparison.
        Protects against timing attacks.
        """
        computed_hash = ChatServer._hash_password(password)
        # Use hmac.compare_digest for constant-time comparison
        return hmac.compare_digest(computed_hash, stored_hash)
    
    @staticmethod
    def get_color_for_username(username: str) -> str:
        """
        Generate a deterministic color for a username.
        Same username always gets the same color across all server instances.
        """
        hash_value = hash(username)
        color_index = abs(hash_value) % len(COLORS)
        return COLORS[color_index]
    
    def setup_logging(self) -> None:
        """Configure logging to file."""
        self.logger = logging.getLogger('ChatServer')
        self.logger.setLevel(logging.INFO)
        
        handler = logging.FileHandler(self.log_file)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def start(self) -> None:
        """Start the server and listen for connections."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((CONFIG['HOST'], self.port))
            self.server_socket.listen(CONFIG['MAX_CONNECTIONS'])
            
            print(f"Server started on {CONFIG['HOST']}:{self.port}")
            self.logger.info(f"Server started on {CONFIG['HOST']}:{self.port}")
            
            while True:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    print(f"New connection from {client_address}")
                    self.logger.info(f"New connection from {client_address}")
                    
                    # Handle client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address),
                        daemon=True
                    )
                    client_thread.start()
                
                except Exception as e:
                    self.logger.error(f"Error accepting connection: {e}")
        
        except KeyboardInterrupt:
            print("\nServer shutting down...")
            self.logger.info("Server shutting down (KeyboardInterrupt)")
            self.shutdown()
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            print(f"Server error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
    
    def handle_client(self, client_socket: socket.socket, 
                     client_address: Tuple[str, int]) -> None:
        """
        Handle a single client connection with authentication flow.
        
        Flow:
        1. Prompt for username
        2. If exists: login flow (password validation, max 3 attempts)
        3. If new: registration flow (password creation, validation, confirmation)
        4. Only after auth: allow chat access
        """
        username: Optional[str] = None
        user: Optional[User] = None
        
        try:
            # STEP 1: Get username
            self._send_auth_message(client_socket, "AUTH_REQUEST_USERNAME", 
                                   {"message": "Enter username:"})
            username = client_socket.recv(CONFIG['BUFFER_SIZE']).decode('utf-8').strip()
            
            if not username or len(username) > 20:
                client_socket.send(b"Invalid username (1-20 characters). Disconnecting.\n")
                self.logger.warning(f"{client_address} - Invalid username: {username}")
                client_socket.close()
                return
            
            # STEP 2: Authentication (login or register)
            if username in self.credentials:
                # Existing user: login flow
                if not self._login_user(client_socket, username):
                    self.logger.warning(f"{client_address} - Failed login for '{username}'")
                    client_socket.close()
                    return
            else:
                # New user: registration flow
                if not self._register_user(client_socket, username):
                    self.logger.warning(f"{client_address} - Failed registration for '{username}'")
                    client_socket.close()
                    return
            
            # STEP 3: Check for duplicate active session
            with self.users_lock:
                if username in self.users:
                    client_socket.send(b"Username already connected. Disconnecting.\n")
                    self.logger.warning(f"{client_address} - Username {username} already active")
                    client_socket.close()
                    return
                
                # Create user object
                color_code = self.get_color_for_username(username)
                user = User(
                    username=username,
                    socket=client_socket,
                    address=client_address,
                    color_code=color_code
                )
                self.users[username] = user
            
            self.logger.info(f"USER_AUTHENTICATED: username={username}, ip={client_address[0]}, action=session_started")
            
            # STEP 4: Add user to default room and send welcome
            self._join_room(username, 'general', password=None)
            
            welcome = f"\nWelcome {user.get_colored_name()}!\n"
            welcome += f"Type /help for commands\n"
            welcome += f"Type /rooms to see available rooms\n"
            client_socket.send(welcome.encode('utf-8'))
            
            # Send color info to client
            color_info = f"COLOR:{username}:{user.color_code}\n"
            client_socket.send(color_info.encode('utf-8'))
            
            # Broadcast user join to room
            self._broadcast_to_room(
                'general',
                f"{user.get_colored_name()} has joined the chat!\n",
                exclude_user=username
            )
            
            self._broadcast_to_room(
                'general',
                f"COLOR:{username}:{user.color_code}\n",
                exclude_user=username
            )
            
            # STEP 5: Main message loop (only authenticated users reach here)
            while True:
                message = client_socket.recv(CONFIG['BUFFER_SIZE']).decode('utf-8').strip()
                
                if not message:
                    break
                
                # Handle commands
                if message.startswith('/'):
                    self._handle_command(user, message)
                else:
                    # Broadcast message to room
                    self._broadcast_to_room(
                        user.room,
                        f"{user.get_colored_name()}: {message}\n"
                    )
                    self.logger.info(f"{username} ({user.room}): {message}")
        
        except ConnectionResetError:
            if user:
                self.logger.warning(f"{user.username} - Connection reset")
        except Exception as e:
            if user:
                self.logger.error(f"{user.username} - Error: {e}")
            else:
                self.logger.error(f"{client_address} - Error: {e}")
        finally:
            # Clean up user
            if user:
                with self.users_lock:
                    if user.username in self.users:
                        del self.users[user.username]
                
                with self.rooms_lock:
                    if user.room in self.rooms:
                        self.rooms[user.room].discard(user.username)
                
                self.logger.info(f"{user.username} ({client_address}) disconnected")
                
                # Broadcast disconnect to room
                self._broadcast_to_room(
                    user.room,
                    f"{user.get_colored_name()} has left the chat!\n"
                )
            
            client_socket.close()
    
    def _send_auth_message(self, client_socket: socket.socket, 
                          msg_type: str, data: dict = None) -> None:
        """Send an authentication message with structured type."""
        if data is None:
            data = {}
        
        message = f"[{msg_type}] {data.get('message', '')}\n".strip() + "\n"
        client_socket.send(message.encode('utf-8'))
    
    def _login_user(self, client_socket: socket.socket, username: str) -> bool:
        """
        Handle login flow for existing user.
        Max 3 password attempts.
        """
        client_ip = client_socket.getpeername()[0]
        
        # Log initial login attempt
        self.logger.info(f"AUTH_ATTEMPT: username={username}, ip={client_ip}")
        
        for attempt in range(1, self.MAX_LOGIN_ATTEMPTS + 1):
            try:
                self._send_auth_message(client_socket, "AUTH_REQUEST_PASSWORD", 
                                       {"message": "Enter password:"})
                password = client_socket.recv(CONFIG['BUFFER_SIZE']).decode('utf-8').strip()
                
                # Verify password using constant-time comparison
                with self.credentials_lock:
                    stored_hash = self.credentials.get(username)
                
                if stored_hash is None:
                    self.logger.error(f"AUTH_ERROR: username={username}, ip={client_ip}, error=username_not_found")
                    self._send_auth_message(client_socket, "AUTH_FAILURE", 
                                           {"message": "User not found. Disconnecting."})
                    return False
                
                if self._verify_password_constant_time(password, stored_hash):
                    self._send_auth_message(client_socket, "AUTH_SUCCESS", 
                                           {"message": "Login successful!"})
                    self.logger.info(f"AUTH_SUCCESS: username={username}, ip={client_ip}")
                    return True
                else:
                    remaining = self.MAX_LOGIN_ATTEMPTS - attempt
                    if remaining > 0:
                        error_msg = f"Invalid password. {remaining} attempt{'s' if remaining != 1 else ''} remaining."
                        self._send_auth_message(client_socket, "AUTH_FAILURE", 
                                               {"message": error_msg, "remaining_attempts": remaining})
                        self.logger.warning(f"AUTH_FAILURE: username={username}, ip={client_ip}, reason=wrong_password, attempts_left={remaining}")
                    else:
                        self._send_auth_message(client_socket, "AUTH_FAILURE", 
                                               {"message": "Max login attempts exceeded. Disconnecting."})
                        self.logger.warning(f"AUTH_FAILURE: username={username}, ip={client_ip}, reason=max_attempts_exceeded, attempts_left=0")
                        return False
            except Exception as e:
                self.logger.error(f"AUTH_ERROR: username={username}, ip={client_ip}, error={str(e)}")
                return False
        
        return False
    
    def _register_user(self, client_socket: socket.socket, username: str) -> bool:
        """
        Handle registration flow for new user.
        Validate password, confirm, and save.
        """
        client_ip = client_socket.getpeername()[0]
        
        # Log registration attempt
        self.logger.info(f"REGISTER_ATTEMPT: username={username}, ip={client_ip}")
        
        try:
            while True:
                # Prompt for password
                self._send_auth_message(client_socket, "AUTH_REQUEST_NEW_PASSWORD", 
                                       {"message": "Create password:"})
                password = client_socket.recv(CONFIG['BUFFER_SIZE']).decode('utf-8').strip()
                
                # Validate password
                is_valid, errors, entropy_bits, strength = validate_password(password)
                
                if not is_valid:
                    # Show validation errors
                    error_list = "\n  ".join(errors)
                    self._send_auth_message(client_socket, "AUTH_RULES_ERROR", 
                                           {"message": f"Password does not meet requirements:\n  {error_list}"})
                    continue
                
                # Password valid: ask for confirmation
                self._send_auth_message(client_socket, "AUTH_REQUEST_CONFIRM_PASSWORD", 
                                       {"message": "Confirm password:"})
                password_confirm = client_socket.recv(CONFIG['BUFFER_SIZE']).decode('utf-8').strip()
                
                if password != password_confirm:
                    self._send_auth_message(client_socket, "AUTH_RULES_ERROR", 
                                           {"message": "Passwords do not match."})
                    continue
                
                # Passwords match: save user
                pwd_hash = self._hash_password(password)
                with self.credentials_lock:
                    self.credentials[username] = pwd_hash
                    self._save_credentials()
                
                # Send success with strength info
                strength_msg = f"Registration successful! Password strength: {strength} ({entropy_bits:.1f} bits)"
                self._send_auth_message(client_socket, "AUTH_SUCCESS", 
                                       {"message": strength_msg, "strength": strength, "entropy": entropy_bits})
                
                # Log successful user creation with password strength
                self.logger.info(f"USER_CREATED: username={username}, ip={client_ip}, password_strength={strength}({entropy_bits:.0f}bits)")
                return True
        
        except Exception as e:
            self.logger.error(f"REGISTER_ERROR: username={username}, ip={client_ip}, error={str(e)}")
            self._send_auth_message(client_socket, "AUTH_FAILURE", 
                                   {"message": "Registration failed. Disconnecting."})
            return False
    
    def _join_room(self, username: str, room_name: str, 
                   password: Optional[str] = None) -> bool:
        """Add user to a room (with password check if needed)."""
        # Check if room exists
        if room_name not in PROTECTED_ROOMS:
            return False
        
        # Check password if required
        if PROTECTED_ROOMS[room_name] is not None:
            if password != PROTECTED_ROOMS[room_name]:
                return False
        
        with self.rooms_lock:
            if room_name not in self.rooms:
                self.rooms[room_name] = set()
            self.rooms[room_name].add(username)
        
        # Update user's current room
        with self.users_lock:
            if username in self.users:
                old_room = self.users[username].room
                self.users[username].room = room_name
                
                # Remove from old room
                with self.rooms_lock:
                    self.rooms[old_room].discard(username)
        
        self.logger.info(f"{username} joined room '{room_name}'")
        return True
    
    def _create_room(self, room_name: str, password: Optional[str] = None) -> bool:
        """Create a new room (optionally password-protected)."""
        # Validate room name
        if not room_name or len(room_name) > 30:
            return False
        
        # Check if room already exists
        if room_name in PROTECTED_ROOMS:
            return False
        
        # Create room
        PROTECTED_ROOMS[room_name] = password
        with self.rooms_lock:
            self.rooms[room_name] = set()
        
        self.logger.info(f"New room created: '{room_name}' (password protected: {password is not None})")
        return True
    
    def _broadcast_to_room(self, room_name: str, message: str, 
                          exclude_user: Optional[str] = None) -> None:
        """Broadcast a message to all users in a room."""
        with self.users_lock:
            for username, user in self.users.items():
                if user.room == room_name and username != exclude_user:
                    try:
                        user.socket.send(message.encode('utf-8'))
                    except Exception as e:
                        self.logger.error(f"Failed to send to {username}: {e}")
    
    def _handle_command(self, user: User, command: str) -> None:
        """Process user commands."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        
        try:
            if cmd == '/help':
                help_text = (
                    "\n--- Available Commands ---\n"
                    "/help           - Show this help message\n"
                    "/rooms          - List all available rooms\n"
                    "/users          - List users in current room\n"
                    "/join <room>    - Join a room\n"
                    "/join <room> <password> - Join password-protected room\n"
                    "/leave          - Leave current room\n"
                    "/quit           - Disconnect\n"
                )
                user.socket.send(help_text.encode('utf-8'))
                self.logger.info(f"{user.username} used /help command")
            
            elif cmd == '/rooms':
                rooms_list = "\n--- Available Rooms ---\n"
                with self.rooms_lock:
                    for room_name, users_set in self.rooms.items():
                        password_indicator = " (protected)" if PROTECTED_ROOMS[room_name] else ""
                        rooms_list += f"  {room_name}{password_indicator} - {len(users_set)} users\n"
                user.socket.send(rooms_list.encode('utf-8'))
                self.logger.info(f"{user.username} used /rooms command")
            
            elif cmd == '/users':
                users_list = f"\n--- Users in '{user.room}' ---\n"
                with self.users_lock:
                    for username, other_user in self.users.items():
                        if other_user.room == user.room:
                            users_list += f"  {other_user.get_colored_name()}\n"
                user.socket.send(users_list.encode('utf-8'))
                self.logger.info(f"{user.username} used /users command")
            
            elif cmd == '/join':
                if not arg:
                    user.socket.send(b"Usage: /join <room> [password]\n")
                else:
                    join_parts = arg.split(maxsplit=1)
                    room_name = join_parts[0]
                    password = join_parts[1] if len(join_parts) > 1 else None
                    
                    if self._join_room(user.username, room_name, password):
                        msg = f"Switched to room '{room_name}'\n"
                        user.socket.send(msg.encode('utf-8'))
                        self._broadcast_to_room(
                            room_name,
                            f"{user.get_colored_name()} has joined!\n"
                        )
                    else:
                        user.socket.send(b"Cannot join room (invalid room or wrong password)\n")
                        self.logger.warning(f"{user.username} failed to join '{room_name}'")
            
            elif cmd == '/create':
                if not arg:
                    user.socket.send(b"Usage: /create <room> [password]\n")
                else:
                    create_parts = arg.split(maxsplit=1)
                    room_name = create_parts[0]
                    password = create_parts[1] if len(create_parts) > 1 else None
                    
                    if self._create_room(room_name, password):
                        # Automatically join the newly created room
                        if self._join_room(user.username, room_name, password):
                            msg = f"Room '{room_name}' created and joined!\n"
                            user.socket.send(msg.encode('utf-8'))
                            self._broadcast_to_room(
                                room_name,
                                f"{user.get_colored_name()} created and joined the room!\n"
                            )
                        else:
                            user.socket.send(b"Room created but failed to join\n")
                    else:
                        user.socket.send(b"Cannot create room (invalid name or already exists)\n")
                        self.logger.warning(f"{user.username} failed to create room '{room_name}'")
            
            elif cmd == '/quit':
                user.socket.send(b"Goodbye!\n")
                self.logger.info(f"{user.username} used /quit command")
                user.socket.close()
            
            else:
                user.socket.send(b"Unknown command. Type /help for available commands.\n")
        
        except Exception as e:
            self.logger.error(f"Error handling command '{cmd}' for {user.username}: {e}")
            user.socket.send(b"Error processing command\n")
    
    def shutdown(self) -> None:
        """Gracefully shutdown the server."""
        self.logger.info("Shutting down server...")
        
        with self.users_lock:
            for user in self.users.values():
                try:
                    user.socket.send(b"Server is shutting down. Disconnecting...\n")
                    user.socket.close()
                except Exception:
                    pass
        
        if self.server_socket:
            self.server_socket.close()
        
        self.logger.info("Server shutdown complete")


def main():
    """Entry point for the server."""
    port = CONFIG['PORT']
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
            if port < 1 or port > 65535:
                print(f"Error: Port must be between 1 and 65535")
                sys.exit(1)
        except ValueError:
            print(f"Error: Invalid port number '{sys.argv[1]}'")
            sys.exit(1)
    
    server = ChatServer(port=port)
    server.start()


if __name__ == '__main__':
    main()
