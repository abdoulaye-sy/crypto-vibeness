"""
Crypto Vibeness - Secure Chat Client
Stage 3: Message encryption
"""

import socket
import threading
import json
import queue
import sys
import os
import base64
from datetime import datetime
from password_manager import KeyManager
from encryption import MessageEncryption
from asymmetric_crypto import AsymmetricCrypto

COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
    "white": "\033[97m",
    "gray": "\033[90m",
    "reset": "\033[0m"
}

COLOR_LIST = ["green", "yellow", "blue", "magenta", "cyan"]

class Client:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        self.username = None
        self.room = None
        self.room_is_private = False
        self.color = None
        self.running = True
        self.room_response_queue = queue.Queue()
        self.handling_room = False
        self.encryption_key = None  # User's symmetric encryption key
        self.key_manager = KeyManager()  # Symmetric key manager
        self.print_lock = threading.Lock()  # Prevent stdout race conditions
        # RSA keypair (asymmetric)
        self.private_key = None
        self.public_key = None
        # Public key cache: {username: public_key_object}
        self.public_keys_cache = {}


    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((self.host, self.port))
            print(f"Connected to {self.host}:{self.port}")
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
        return True

    def authenticate(self):
        """Authenticate: login or create account with password validation"""
        prompt = self.socket.recv(1024).decode('utf-8')
        
        while True:
            # AUTH prompt - request username
            if "AUTH:" in prompt:
                username = input("Enter username: ").strip()
                if not username:
                    continue
                self.username = username
                self.socket.sendall(username.encode('utf-8') + b'\n')
                prompt = self.socket.recv(1024).decode('utf-8')
            
            # CREATE_ACCOUNT? prompt - new account
            elif "CREATE_ACCOUNT?" in prompt:
                response = input("Create account? (yes/no): ").strip().lower()
                self.socket.sendall(response.encode('utf-8') + b'\n')
                prompt = self.socket.recv(1024).decode('utf-8')
            
            # PASSWORD_STRENGTH message (informational)
            elif "PASSWORD_STRENGTH:" in prompt:
                strength_msg = prompt.split('PASSWORD_STRENGTH:', 1)[1].split('\n')[0]
                print(f"💪 {strength_msg}")
                # Check what follows the strength message
                if "\n" in prompt:
                    remaining = prompt.split('\n', 1)[1]
                    prompt = remaining if remaining else self.socket.recv(1024).decode('utf-8')
                else:
                    prompt = self.socket.recv(1024).decode('utf-8')
            
            # Error with validation details and retry prompt
            elif "ERROR:" in prompt and "RETRY_PASSWORD:" in prompt:
                # Extract error message
                error_msg = prompt.split('ERROR:', 1)[1].split('\n')[0]
                print(f"❌ {error_msg}")
                # Display all validation error lines
                lines = prompt.split('\n')
                for line in lines:
                    if line.startswith('❌'):
                        print(f"  {line}")
                # Send new password
                password = input("Enter password: ").strip()
                self.socket.sendall(password.encode('utf-8') + b'\n')
                prompt = self.socket.recv(1024).decode('utf-8')
            
            # PASSWORD prompt - verify/set password
            elif "PASSWORD:" in prompt:
                if "CONFIRM" in prompt:
                    # Confirm password prompt
                    password = input("Confirm password: ").strip()
                else:
                    # Regular password prompt
                    password = input("Enter password: ").strip()
                
                self.socket.sendall(password.encode('utf-8') + b'\n')
                prompt = self.socket.recv(1024).decode('utf-8')
            
            # KEY_SECRET prompt - new account needs encryption key
            elif "KEY_SECRET:" in prompt:
                key_secret = input("Enter secret for message encryption: ").strip()
                self.socket.sendall(key_secret.encode('utf-8') + b'\n')
                
                # Generate and store key locally
                salt_b64, key_b64, key = KeyManager.generate_key(key_secret)
                self.encryption_key = key
                
                # Store key locally
                os.makedirs('users', exist_ok=True)
                key_file = f'users/{self.username}_key.txt'
                with open(key_file, 'w') as f:
                    f.write(f"{salt_b64}:{key_b64}")
                print(f"🔑 Key stored in {key_file}")
                
                prompt = self.socket.recv(1024).decode('utf-8')
            
            # RETRY_PASSWORD - password validation failed
            elif "RETRY_PASSWORD:" in prompt:
                password = input("Enter password again: ").strip()
                self.socket.sendall(password.encode('utf-8') + b'\n')
                prompt = self.socket.recv(1024).decode('utf-8')
            
            # OK:Authenticated - success
            elif "OK:" in prompt and "Authenticated" in prompt:
                color_idx = hash(self.username) % len(COLOR_LIST)
                self.color = COLOR_LIST[color_idx]
                print(f"✅ Authenticated as {self.username}")
                # Check for account creation message
                if "Account created" in prompt:
                    print("✅ Account created successfully")
                
                # Generate or load RSA keypair
                self.load_or_generate_keypair()
                
                return True
            
            # Generic error message
            elif "ERROR:" in prompt:
                error_msg = prompt.split('ERROR:', 1)[1].split('\n')[0] if 'ERROR:' in prompt else prompt
                print(f"❌ {error_msg}")
                prompt = self.socket.recv(1024).decode('utf-8')
            
            else:
                # Unknown prompt, wait for next message
                prompt = self.socket.recv(1024).decode('utf-8')
        
        return False

    def get_username(self):
        """This method is now obsolete - use authenticate() instead"""
        return True

    def load_encryption_key(self):
        """Load user's encryption key from local storage (optional)"""
        key_file = f'users/{self.username}_key.txt'
        if os.path.exists(key_file):
            try:
                with open(key_file, 'r') as f:
                    salt_b64, key_b64 = f.read().split(':')
                self.encryption_key = base64.b64decode(key_b64)
                print(f"🔑 Loaded encryption key from {key_file}")
                return True
            except Exception as e:
                print(f"⚠️  Could not load key: {e}")
        return False
    
    def load_or_generate_keypair(self):
        """Load or generate RSA keypair for asymmetric encryption"""
        crypto = AsymmetricCrypto()
        priv_file = f"users/{self.username}.priv"
        pub_file = f"users/{self.username}.pub"
        
        # Ensure users directory exists
        if not os.path.exists("users"):
            os.makedirs("users")
        
        if os.path.exists(priv_file) and os.path.exists(pub_file):
            # Load existing keypair
            try:
                self.private_key, self.public_key = crypto.load_keypair(self.username)
                print(f"🔑 Loaded RSA keypair from users/{self.username}.{{priv,pub}}")
            except Exception as e:
                print(f"⚠️  Failed to load RSA keypair: {e}")
                return False
        else:
            # Generate new keypair and save
            try:
                self.private_key, self.public_key = crypto.generate_keypair()
                crypto.save_keypair(self.username, self.private_key, self.public_key)
                print(f"✅ Generated new RSA keypair")
            except Exception as e:
                print(f"❌ Failed to generate RSA keypair: {e}")
                return False
        
        return True
    
    def exchange_symmetric_key(self):
        """Exchange public key with server and receive encrypted symmetric key"""
        try:
            crypto = AsymmetricCrypto()
            
            # Wait for PUBKEY: prompt from server
            prompt = self.socket.recv(1024).decode('utf-8')
            if "PUBKEY:" not in prompt:
                print(f"⚠️  Unexpected server response: {prompt}")
                return False
            
            # Serialize and send public key
            pubkey_b64 = crypto.serialize_public_key(self.public_key)
            self.socket.sendall(pubkey_b64.encode('utf-8') + b'\n')
            
            # Receive encrypted symmetric key
            response = self.socket.recv(1024).decode('utf-8')
            if "SYMKEY:" not in response:
                print(f"❌ Server failed to send symmetric key: {response}")
                return False
            
            # Extract and decrypt symmetric key
            symkey_b64 = response.split("SYMKEY:", 1)[1].strip()
            try:
                self.encryption_key = crypto.decrypt_with_private_key(
                    base64.b64decode(symkey_b64),
                    self.private_key
                )
                print(f"🔑 Decrypted symmetric key from server")
                return True
            except Exception as e:
                print(f"❌ Failed to decrypt symmetric key: {e}")
                return False
        
        except Exception as e:
            print(f"❌ Key exchange failed: {e}")
            return False
    
    def get_public_key(self, username):
        """Fetch and cache public key for a user"""
        if username in self.public_keys_cache:
            return self.public_keys_cache[username]
        
        try:
            crypto = AsymmetricCrypto()
            # Request public key from server
            self.socket.sendall(f"/pubkey {username}\n".encode('utf-8'))
            
            # Receive response
            response = self.socket.recv(1024).decode('utf-8')
            data = json.loads(response)
            
            if data.get("type") == "pubkey":
                pubkey_b64 = data.get("public_key")
                public_key = crypto.deserialize_public_key(pubkey_b64)
                self.public_keys_cache[username] = public_key
                return public_key
            else:
                self.print_with_lock(f"❌ {data.get('message', 'Failed to get public key')}")
                return None
        except Exception as e:
            self.print_with_lock(f"❌ Error fetching public key: {e}")
            return None

    def get_room(self):
        """Get/Create room selection and handling"""
        # First, exchange symmetric key with server
        if not self.exchange_symmetric_key():
            print("❌ Failed to exchange symmetric key with server")
            return False
        
        attempt = 0
        while attempt < 3:  # Max 3 attempts
            attempt += 1
            try:
                prompt = self.socket.recv(1024).decode('utf-8')
            except socket.timeout:
                print(f"❌ Timeout waiting for room selection prompt (attempt {attempt})")
                continue
            except Exception as e:
                print(f"❌ Error receiving room selection prompt: {e}")
                return False
            
            # Check for valid response
            if not prompt:
                print(f"❌ Server disconnected during room selection (attempt {attempt})")
                return False
            
            if "ROOM" in prompt:
                room = input("Enter room name (default: general): ").strip() or "general"
                self.socket.sendall(room.encode('utf-8') + b'\n')
                
                # Check if server asks about privacy (new room)
                response = self.socket.recv(1024).decode('utf-8')
                if "PRIVATE?" in response:
                    is_private = input("Do you want this room to be private? (yes/no): ").strip().lower()
                    self.socket.sendall(is_private.encode('utf-8') + b'\n')
                    
                    if is_private == "yes":
                        prompt = self.socket.recv(1024).decode('utf-8')
                        if "PASSWORD" in prompt:
                            password = input("Enter room password: ").strip()
                            self.socket.sendall(password.encode('utf-8') + b'\n')
                            response = self.socket.recv(1024).decode('utf-8')
                    else:
                        response = self.socket.recv(1024).decode('utf-8')
                
                # Handle password prompts for existing private rooms (may retry)
                while "PASSWORD" in response:
                    password = input("Enter room password: ").strip()
                    self.socket.sendall(password.encode('utf-8') + b'\n')
                    response = self.socket.recv(1024).decode('utf-8')
                    
                    if "ERROR" in response:
                        print(f"❌ {response.split(':', 1)[1] if ':' in response else response}")
                        # If ERROR is alone (no PASSWORD in same response), wait for PASSWORD
                        if "PASSWORD" not in response:
                            response = self.socket.recv(1024).decode('utf-8')
                
                # Check final response
                if "ERROR" in response:
                    print(f"❌ {response.split(':', 1)[1] if ':' in response else response}")
                    continue
                elif "OK" in response:
                    # Extract room name and privacy info
                    parts = response.split("Connected to ")[-1].split("|")
                    self.room = parts[0]
                    if len(parts) > 1:
                        self.room_is_private = "🔒" in parts[1]
                    return True
                elif "{" in response:
                    # JSON message (notification from server) - keep receiving
                    continue
                else:
                    # Unknown response format, try again
                    continue
            else:
                return False

    def get_prompt(self):
        """Get the current prompt string"""
        privacy_marker = "🔒" if self.room_is_private else "🔓"
        room_display = f"{COLORS['gray']}[{self.room} {privacy_marker}]{COLORS['reset']}" if self.room else ""
        return f"{COLORS[self.color]}{self.username}{COLORS['reset']} {room_display}: "
    
    def print_with_lock(self, text):
        """Print text with output lock (thread-safe)"""
        with self.print_lock:
            print(text)

    def format_message(self, data):
        try:
            msg = json.loads(data)
            if msg["type"] == "system":
                return f"{COLORS['yellow']}{msg['message']}{COLORS['reset']}"
            else:
                # Apply color only to username, not the entire message
                color = COLORS[msg.get("color", "white")]
                username_colored = f"{color}{msg['username']}{COLORS['reset']}"
                return f"{username_colored}: {msg['message']}"
        except:
            return data

    def receive_messages(self):
        while self.running:
            try:
                data = self.socket.recv(1024).decode('utf-8')
                if not data:
                    break
                
                for line in data.split('\n'):
                    if line.strip():
                        # Ignore standalone OK: messages (message confirmations)
                        if line.strip() == "OK:":
                            continue
                        
                        if line.startswith("ROOMS_LIST:"):
                            # Display rooms list
                            rooms_info = line[11:].strip()
                            self.print_with_lock(f"\n{COLORS['cyan']}=== Available Rooms ==={COLORS['reset']}")
                            self.print_with_lock(rooms_info)
                            self.print_with_lock(f"{COLORS['cyan']}========================{COLORS['reset']}")
                            continue
                        elif line.startswith("PRIVATE?") or line.startswith("PASSWORD"):
                            # If handling /room, put in queue; otherwise skip
                            if self.handling_room:
                                self.room_response_queue.put(line.strip())
                            continue
                        elif line.startswith("OK:") and "Switched to" in line:
                            # Put in queue if handling room, else skip
                            if self.handling_room:
                                self.room_response_queue.put(line.strip())
                            continue
                        elif line.startswith("ERROR:"):
                            # Put in queue if handling room, else print
                            if self.handling_room:
                                self.room_response_queue.put(line.strip())
                            else:
                                self.print_with_lock(f"{COLORS['red']}{line[6:]}{COLORS['reset']}")
                        else:
                            # Check if it's a JSON message (DM or system)
                            if line.startswith("{"):
                                try:
                                    msg_obj = json.loads(line)
                                    
                                    if msg_obj.get("type") == "dm_e2ee":
                                        # E2EE Direct Message with signature
                                        from_user = msg_obj.get("from")
                                        encrypted_msg = msg_obj.get("message")
                                        signature_b64 = msg_obj.get("signature")
                                        
                                        # Get sender's public key
                                        sender_pubkey = self.get_public_key(from_user)
                                        if not sender_pubkey:
                                            self.print_with_lock(f"{COLORS['red']}❌ Cannot verify DM from {from_user}: key not found{COLORS['reset']}")
                                            continue
                                        
                                        # Decrypt and verify
                                        try:
                                            import base64
                                            crypto = AsymmetricCrypto()
                                            
                                            # Decrypt the message
                                            decrypted = MessageEncryption.decrypt_message(
                                                base64.b64decode(encrypted_msg).decode(),
                                                self.encryption_key
                                            )
                                            
                                            # Verify signature
                                            signature = base64.b64decode(signature_b64)
                                            if not crypto.verify_signature(decrypted, signature, sender_pubkey):
                                                self.print_with_lock(f"{COLORS['red']}❌ SIGNATURE VERIFICATION FAILED from {from_user} - MESSAGE REJECTED{COLORS['reset']}")
                                                continue
                                            
                                            # Message verified
                                            timestamp = msg_obj.get("timestamp", "")
                                            self.print_with_lock(f"\n{COLORS['green']}[E2EE DM from {from_user}]{COLORS['reset']} {decrypted}")
                                        except Exception as e:
                                            self.print_with_lock(f"{COLORS['red']}❌ Failed to process E2EE DM: {e}{COLORS['reset']}")
                                    elif msg_obj.get("type") == "system":
                                        # System message
                                        self.print_with_lock(f"\n{COLORS['yellow']}{msg_obj.get('message')}{COLORS['reset']}")
                                    elif msg_obj.get("type") == "error":
                                        # Error message
                                        self.print_with_lock(f"\n{COLORS['red']}{msg_obj.get('message')}{COLORS['reset']}")
                                    else:
                                        # Regular room message
                                        formatted = self.format_message(line)
                                        self.print_with_lock(f"\n{formatted}")
                                except json.JSONDecodeError:
                                    # Not JSON, treat as regular message
                                    formatted = self.format_message(line)
                                    self.print_with_lock(f"\n{formatted}")
                            else:
                                # Regular message (JSON or other)
                                formatted = self.format_message(line)
                                self.print_with_lock(f"\n{formatted}")
            except Exception as e:
                if self.running:
                    self.print_with_lock(f"Receive error: {e}")
                break

    def handle_room_command(self, room_name):
        """Handle /room command - ask for password if needed"""
        self.handling_room = True
        try:
            self.socket.sendall(f"/room {room_name}".encode('utf-8') + b'\n')
            
            # Read responses from queue (receive_messages thread puts them there)
            while True:
                try:
                    response = self.room_response_queue.get(timeout=5.0)
                except queue.Empty:
                    print(f"{COLORS['red']}Timeout waiting for server response{COLORS['reset']}")
                    break
                
                if response.startswith("OK:"):
                    if "Switched to" in response:
                        parts = response.split("Switched to ")[-1].split("|")
                        new_room = parts[0]
                        privacy_marker = parts[1] if len(parts) > 1 else ""
                        self.room = new_room
                        self.room_is_private = "🔒" in privacy_marker
                        print(f"{COLORS['yellow']}Now in room: {new_room} {privacy_marker}{COLORS['reset']}")
                    break
                elif response.startswith("PRIVATE?"):
                    # New room - ask about privacy
                    is_private = input("Do you want this room to be private? (yes/no): ").strip().lower()
                    self.socket.sendall(is_private.encode('utf-8') + b'\n')
                elif response.startswith("PASSWORD"):
                    # Room requires password
                    password = input("Enter room password: ").strip()
                    self.socket.sendall(password.encode('utf-8') + b'\n')
                elif response.startswith("ERROR:"):
                    print(f"{COLORS['red']}{response[6:]}{COLORS['reset']}")
        finally:
            self.handling_room = False
    
    def send_messages(self):
        try:
            while self.running:
                message = input(self.get_prompt())
                if message.lower() == "/quit":
                    self.running = False
                    break
                if message.lower() == "/list":
                    self.socket.sendall("/list\n".encode('utf-8'))
                    continue
                if message.startswith("/dm "):
                    # Direct message (1-to-1 with signatures)
                    parts = message[4:].split(" ", 1)
                    if len(parts) < 2:
                        self.print_with_lock(f"{COLORS['red']}Usage: /dm <username> <message>{COLORS['reset']}")
                        continue
                    
                    target_username = parts[0]
                    dm_message = parts[1]
                    
                    # Get target's public key
                    target_pubkey = self.get_public_key(target_username)
                    if not target_pubkey:
                        continue
                    
                    # Sign the message with our private key
                    crypto = AsymmetricCrypto()
                    signature = crypto.sign_message(dm_message, self.private_key)
                    if not signature:
                        self.print_with_lock(f"{COLORS['red']}Failed to sign message{COLORS['reset']}")
                        continue
                    
                    # Encrypt message with target's public key (session key)
                    session_key = crypto.encrypt_with_public_key(self.encryption_key, target_pubkey)
                    if not session_key:
                        self.print_with_lock(f"{COLORS['red']}Failed to encrypt session key{COLORS['reset']}")
                        continue
                    
                    # Create E2EE envelope
                    import base64
                    dm_envelope = json.dumps({
                        "type": "dm_e2ee",
                        "from": self.username,
                        "to": target_username,
                        "message": base64.b64encode(MessageEncryption.encrypt_message(dm_message, self.encryption_key).encode()).decode(),
                        "signature": base64.b64encode(signature).decode(),
                        "session_key": base64.b64encode(session_key).decode()
                    })
                    
                    self.socket.sendall(dm_envelope.encode('utf-8') + b'\n')
                    self.print_with_lock(f"{COLORS['cyan']}→ DM sent to {target_username} (signed & encrypted){COLORS['reset']}")
                    continue
                if message.startswith("/room "):
                    room_name = message[6:].strip()
                    if room_name:
                        self.handle_room_command(room_name)
                    else:
                        with self.print_lock:
                            print(f"{COLORS['red']}Room name cannot be empty{COLORS['reset']}")
                elif message.lower() == "/quit":
                    self.running = False
                    break
                elif message.strip():
                    # Encrypt message if symmetric key available
                    if self.encryption_key:
                        try:
                            encrypted_msg = MessageEncryption.encrypt_message(message, self.encryption_key)
                            self.socket.sendall(encrypted_msg.encode('utf-8') + b'\n')
                        except Exception as e:
                            with self.print_lock:
                                print(f"❌ Encryption error: {e}")
                    else:
                        # Fallback: send plaintext if no key (should not happen)
                        self.socket.sendall(message.encode('utf-8') + b'\n')
        except Exception as e:
            print(f"Send error: {e}")
        finally:
            self.running = False

    def run(self):
        if not self.connect():
            return

        try:
            # Phase 1: Authenticate
            if not self.authenticate():
                print("❌ Authentication failed")
                return

             # Phase 2: Key exchange (Jour 3 will handle symmetric key derivation)
            # load_encryption_key() was Jour 2 PBKDF2-based - Jour 3 uses RSA exchange instead
            
            # Phase 3: Select/Create room
            if not self.get_room():
                print("Failed to join room")
                return

            print(f"\n{COLORS['green']}✓ Logged in as {COLORS[self.color]}{self.username}{COLORS['reset']}")

            # Start receive thread
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()

            # Send messages in main thread
            self.send_messages()

        except KeyboardInterrupt:
            print("\nDisconnecting...")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.running = False
            try:
                self.socket.close()
            except:
                pass

if __name__ == "__main__":
    client = Client("127.0.0.1", 5001)
    client.run()
