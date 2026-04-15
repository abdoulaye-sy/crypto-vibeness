"""
Crypto Vibeness - Secure Chat Client
Stage 1: Base chat
"""

import socket
import threading
import json
import queue
import sys
from datetime import datetime

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
        self.room_is_private = False  # Track if current room is private
        self.color = None
        self.running = True
        self.room_response_queue = queue.Queue()  # For PRIVATE?, PASSWORD responses
        self.handling_room = False  # Flag to indicate /room command in progress

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
        """Authenticate: login or create account"""
        prompt = self.socket.recv(1024).decode('utf-8')
        
        while True:
            # Check for error messages
            if "ERROR" in prompt:
                error_msg = prompt.split('ERROR:', 1)[1].split('\n')[0] if 'ERROR:' in prompt else prompt
                print(f"❌ {error_msg}")
            
            # AUTH prompt - request username
            if "AUTH" in prompt:
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
                
                if response == "yes":
                    prompt = self.socket.recv(1024).decode('utf-8')
                else:
                    prompt = self.socket.recv(1024).decode('utf-8')
            
            # PASSWORD prompt - verify/set password
            elif "PASSWORD" in prompt:
                if "CONFIRM" in prompt:
                    # Confirm password prompt
                    password = input("Confirm password: ").strip()
                else:
                    # Regular password prompt
                    password = input("Enter password: ").strip()
                
                self.socket.sendall(password.encode('utf-8') + b'\n')
                prompt = self.socket.recv(1024).decode('utf-8')
            
            # OK:Authenticated - success
            elif "OK" in prompt and "Authenticated" in prompt:
                color_idx = hash(self.username) % len(COLOR_LIST)
                self.color = COLOR_LIST[color_idx]
                print(f"✅ Authenticated as {self.username}")
                return True
            
            # Bundled message handling
            elif "ERROR" in prompt and "PASSWORD" in prompt:
                # ERROR + PASSWORD bundled
                error_msg = prompt.split('ERROR:', 1)[1].split('\n')[0]
                print(f"❌ {error_msg}")
                # Extract PASSWORD part
                if "\n" in prompt:
                    password = input("Enter password: ").strip()
                    self.socket.sendall(password.encode('utf-8') + b'\n')
                    prompt = self.socket.recv(1024).decode('utf-8')
            
            else:
                # Unknown prompt, wait for next
                prompt = self.socket.recv(1024).decode('utf-8')
        
        return False

    def get_username(self):
        """This method is now obsolete - use authenticate() instead"""
        return True

    def get_room(self):
        """Get/Create room selection and handling"""
        while True:
            prompt = self.socket.recv(1024).decode('utf-8')
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
            return False

    def show_help(self):
        print(f"\n{COLORS['yellow']}=== Available Commands ==={COLORS['reset']}")
        print(f"  {COLORS['cyan']}/room <name>{COLORS['reset']}  - Switch to another room")
        print(f"  {COLORS['cyan']}/quit{COLORS['reset']}         - Leave the chat")
        print(f"{COLORS['yellow']}========================{COLORS['reset']}\n")

    def format_message(self, data):
        try:
            msg = json.loads(data)
            if msg["type"] == "system":
                return f"{COLORS['yellow']}{msg['message']}{COLORS['reset']}"
            else:
                color = COLORS[msg.get("color", "white")]
                return f"{color}{msg['username']}: {msg['message']}{COLORS['reset']}"
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
                        if line.startswith("PRIVATE?") or line.startswith("PASSWORD"):
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
                                print(f"{COLORS['red']}{line[6:]}{COLORS['reset']}")
                        else:
                            formatted = self.format_message(line)
                            print(formatted)
            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
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
                privacy_marker = "🔒" if self.room_is_private else "🔓"
                room_display = f"{COLORS['gray']}[{self.room} {privacy_marker}]{COLORS['reset']}" if self.room else ""
                message = input(f"{COLORS[self.color]}{self.username}{COLORS['reset']} {room_display}: ")
                if message.lower() == "/quit":
                    self.running = False
                    break
                if message.startswith("/room "):
                    room_name = message[6:].strip()
                    if room_name:
                        self.handle_room_command(room_name)
                    else:
                        print(f"{COLORS['red']}Room name cannot be empty{COLORS['reset']}")
                elif message.lower() == "/quit":
                    self.running = False
                    break
                elif message.strip():
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

            # Phase 2: Select/Create room
            if not self.get_room():
                print("Failed to join room")
                return

            print(f"\n{COLORS['green']}✓ Logged in as {COLORS[self.color]}{self.username}{COLORS['reset']}")
            self.show_help()

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
