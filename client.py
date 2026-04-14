"""
Crypto Vibeness - Secure Chat Client
Stage 1: Base chat
"""

import socket
import threading
import json
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
    "reset": "\033[0m"
}

COLOR_LIST = ["green", "yellow", "blue", "magenta", "cyan"]

class Client:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        self.username = None
        self.color = None
        self.running = True

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((self.host, self.port))
            print(f"Connected to {self.host}:{self.port}")
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
        return True

    def get_username(self):
        prompt = self.socket.recv(1024).decode('utf-8')
        if "USERNAME" in prompt:
            username = input("Enter username: ").strip()
            if not username:
                return False
            self.username = username
            self.socket.sendall(username.encode('utf-8') + b'\n')
            # Assign color based on username hash
            color_idx = hash(username) % len(COLOR_LIST)
            self.color = COLOR_LIST[color_idx]
            return True
        return False

    def get_room(self):
        prompt = self.socket.recv(1024).decode('utf-8')
        if "ROOM" in prompt:
            room = input("Enter room name (default: general): ").strip() or "general"
            self.socket.sendall(room.encode('utf-8') + b'\n')
            response = self.socket.recv(1024).decode('utf-8')
            if "OK" in response:
                return True
        return False

    def format_message(self, data):
        try:
            msg = json.loads(data)
            if msg["type"] == "system":
                return f"{COLORS['yellow']}[{msg['timestamp']}] {msg['message']}{COLORS['reset']}"
            else:
                color = COLORS[msg.get("color", "white")]
                return f"{color}[{msg['timestamp']}] {msg['username']}: {msg['message']}{COLORS['reset']}"
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
                        if line.startswith("OK:"):
                            continue
                        else:
                            print(self.format_message(line))
            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
                break

    def send_messages(self):
        try:
            while self.running:
                message = input(f"{COLORS[self.color]}{self.username}{COLORS['reset']}: ")
                if message.lower() == "/quit":
                    self.running = False
                    break
                if message.strip():
                    self.socket.sendall(message.encode('utf-8') + b'\n')
        except Exception as e:
            print(f"Send error: {e}")
        finally:
            self.running = False

    def run(self):
        if not self.connect():
            return

        try:
            if not self.get_username():
                print("Failed to get username")
                return

            if not self.get_room():
                print("Failed to join room")
                return

            print(f"Logged in as {COLORS[self.color]}{self.username}{COLORS['reset']}")
            print("Type /quit to exit\n")

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
    client = Client("127.0.0.1", 5000)
    client.run()
