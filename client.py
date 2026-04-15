#!/usr/bin/env python3
"""
Terminal-based chat client with authentication support.
Day 1 - Part 2: Adds password authentication with secure input.
"""

import socket
import threading
import sys
import getpass
import re
from datetime import datetime
from typing import Optional, Dict, Tuple

# Default configuration
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 5000
BUFFER_SIZE = 4096


class ChatClient:
    """Terminal-based chat client with authentication."""
    
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.username: Optional[str] = None
        self.current_room: str = 'general'
        self.connected = False
        self.authenticated = False
        self.running = True
        self.username_colors: Dict[str, str] = {}
    
    def connect(self) -> bool:
        """Establish connection to the server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def receive_messages(self) -> None:
        """
        Receive messages from server in separate thread.
        Handles auth messages, chat messages, and protocol messages.
        """
        try:
            while self.connected and self.running:
                try:
                    message = self.socket.recv(BUFFER_SIZE).decode('utf-8')
                    
                    if not message:
                        break
                    
                    # Split into lines to handle multiple messages
                    for line in message.split('\n'):
                        if not line:
                            continue
                        
                        # Handle auth request messages
                        if line.startswith('[AUTH_REQUEST_USERNAME]'):
                            self._handle_auth_request_username(line)
                        elif line.startswith('[AUTH_REQUEST_PASSWORD]'):
                            self._handle_auth_request_password(line)
                        elif line.startswith('[AUTH_REQUEST_NEW_PASSWORD]'):
                            self._handle_auth_request_new_password(line)
                        elif line.startswith('[AUTH_REQUEST_CONFIRM_PASSWORD]'):
                            self._handle_auth_request_confirm_password(line)
                        elif line.startswith('[AUTH_SUCCESS]'):
                            self._handle_auth_success(line)
                        elif line.startswith('[AUTH_FAILURE]'):
                            self._handle_auth_failure(line)
                        elif line.startswith('[AUTH_RULES_ERROR]'):
                            self._handle_auth_rules_error(line)
                        elif line.startswith('COLOR:'):
                            self._handle_color_message(line)
                        else:
                            # Regular chat message or server info
                            print(line)
                
                except ConnectionResetError:
                    print("\n[Server disconnected]")
                    self.connected = False
                    break
                except Exception as e:
                    if self.connected:
                        print(f"\n[Receive error: {e}]")
                    break
        
        except Exception as e:
            print(f"Fatal receive error: {e}")
        finally:
            self.connected = False
    
    def _handle_auth_request_username(self, line: str) -> None:
        """Handle AUTH_REQUEST_USERNAME from server."""
        # Extract message
        msg = line.replace('[AUTH_REQUEST_USERNAME]', '').strip()
        if msg:
            print(msg, end=' ', flush=True)
        
        # Get username from user
        username = input().strip()
        self.socket.send(username.encode('utf-8'))
    
    def _handle_auth_request_password(self, line: str) -> None:
        """Handle AUTH_REQUEST_PASSWORD from server."""
        msg = line.replace('[AUTH_REQUEST_PASSWORD]', '').strip()
        if msg:
            print(msg, end=' ', flush=True)
        
        # Get password securely (hidden input)
        password = getpass.getpass('')
        self.socket.send(password.encode('utf-8'))
    
    def _handle_auth_request_new_password(self, line: str) -> None:
        """Handle AUTH_REQUEST_NEW_PASSWORD from server."""
        msg = line.replace('[AUTH_REQUEST_NEW_PASSWORD]', '').strip()
        if msg:
            print(msg, end=' ', flush=True)
        
        # Get password securely (hidden input)
        password = getpass.getpass('')
        self.socket.send(password.encode('utf-8'))
    
    def _handle_auth_request_confirm_password(self, line: str) -> None:
        """Handle AUTH_REQUEST_CONFIRM_PASSWORD from server."""
        msg = line.replace('[AUTH_REQUEST_CONFIRM_PASSWORD]', '').strip()
        if msg:
            print(msg, end=' ', flush=True)
        
        # Get password securely (hidden input)
        password = getpass.getpass('')
        self.socket.send(password.encode('utf-8'))
    
    def _handle_auth_success(self, line: str) -> None:
        """Handle AUTH_SUCCESS from server."""
        msg = line.replace('[AUTH_SUCCESS]', '').strip()
        print(f"[OK] {msg}")
        self.authenticated = True
    
    def _handle_auth_failure(self, line: str) -> None:
        """Handle AUTH_FAILURE from server."""
        msg = line.replace('[AUTH_FAILURE]', '').strip()
        print(f"[ERROR] {msg}")
        
        # Check if this is the final failure (disconnecting)
        if "Disconnecting" in msg:
            self.connected = False
            self.running = False
    
    def _handle_auth_rules_error(self, line: str) -> None:
        """Handle AUTH_RULES_ERROR from server (password validation errors)."""
        msg = line.replace('[AUTH_RULES_ERROR]', '').strip()
        print(f"[INVALID] {msg}")
    
    def _handle_color_message(self, line: str) -> None:
        """
        Parse COLOR protocol message and store color mapping.
        Format: COLOR:username:ansi_code
        """
        try:
            parts = line.split(':', 2)
            if len(parts) >= 3:
                username = parts[1]
                color_code = parts[2]
                self.username_colors[username] = color_code
        except Exception as e:
            pass  # Silently ignore color parsing errors
    
    def send_messages(self) -> None:
        """
        Send messages to server from main thread.
        Wait for authentication before entering chat mode.
        """
        try:
            # Wait for authentication (receive thread handles prompts)
            import time
            while self.connected and not self.authenticated:
                time.sleep(0.1)
            
            if not self.authenticated:
                return
            
            print(f"\nJoined 'general' room. Type /help for commands.\n")
            
            while self.connected and self.authenticated and self.running:
                try:
                    user_input = input("> ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Handle commands
                    if user_input.startswith('/'):
                        self._handle_command(user_input)
                    else:
                        # Send regular message with newline
                        self.socket.send((user_input + '\n').encode('utf-8'))
                
                except EOFError:
                    # Ctrl+D pressed
                    self._send_command('/quit')
                    break
                except KeyboardInterrupt:
                    # Ctrl+C pressed
                    print("\n")
                    self._send_command('/quit')
                    break
                except Exception as e:
                    print(f"Send error: {e}")
                    break
        
        except Exception as e:
            print(f"Fatal send error: {e}")
        finally:
            self.disconnect()
    
    def _handle_command(self, command: str) -> None:
        """Process user commands."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        
        try:
            if cmd == '/help':
                self._display_help()
            
            elif cmd == '/rooms':
                self._send_command('/rooms')
            
            elif cmd == '/users':
                self._send_command('/users')
            
            elif cmd == '/join':
                if not arg:
                    print("Usage: /join <room> [password]")
                else:
                    self._send_command(command)
                    # Update current room (optimistically)
                    join_parts = arg.split(maxsplit=1)
                    self.current_room = join_parts[0]
            
            elif cmd == '/create':
                if not arg:
                    print("Usage: /create <room> [password]")
                else:
                    self._send_command(command)
                    # Update current room (optimistically)
                    create_parts = arg.split(maxsplit=1)
                    self.current_room = create_parts[0]
            
            elif cmd == '/quit':
                self._send_command('/quit')
                self.disconnect()
            
            else:
                print(f"Unknown command '{cmd}'. Type /help for available commands.")
        
        except Exception as e:
            print(f"Command error: {e}")
    
    def _send_command(self, command: str) -> None:
        """Send a command to the server."""
        try:
            self.socket.send((command + '\n').encode('utf-8'))
        except Exception as e:
            print(f"Failed to send command: {e}")
    
    def _display_help(self) -> None:
        """Display available commands."""
        help_text = (
            "\n--- Available Commands ---\n"
            "/help                      - Show this help message\n"
            "/rooms                     - List all available rooms\n"
            "/users                     - List users in current room\n"
            "/join <room> [password]    - Join a room\n"
            "/create <room> [password]  - Create a new room\n"
            "/quit                      - Disconnect\n"
            "\nType a message without / to chat.\n"
        )
        print(help_text)
    
    def disconnect(self) -> None:
        """Gracefully disconnect from server."""
        self.connected = False
        self.authenticated = False
        self.running = False
        
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        
        print("\nDisconnected from server.")
    
    def run(self) -> None:
        """Main client loop."""
        # Connect to server
        if not self.connect():
            return
        
        print("\n=== Crypto Chat Client (Authenticated) ===\n")
        
        # Start receiving thread (handles auth prompts and messages)
        recv_thread = threading.Thread(target=self.receive_messages, daemon=True)
        recv_thread.start()
        
        # Send messages from main thread (waits for auth first)
        self.send_messages()


def parse_arguments() -> Tuple[str, int]:
    """Parse command line arguments."""
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    
    if len(sys.argv) > 1:
        host = sys.argv[1]
    
    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
            if port < 1 or port > 65535:
                print(f"Error: Port must be between 1 and 65535")
                sys.exit(1)
        except ValueError:
            print(f"Error: Invalid port number '{sys.argv[2]}'")
            sys.exit(1)
    
    return host, port


def main():
    """Entry point for the client."""
    host, port = parse_arguments()
    client = ChatClient(host=host, port=port)
    client.run()


if __name__ == '__main__':
    main()
