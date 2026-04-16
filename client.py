#!/usr/bin/env python3
"""
Crypto Vibeness - Unified Client
Fusion: crypto-mous + work-vincent
"""

import socket
import threading
import sys
import getpass
import queue
from typing import Optional, Dict

BUFFER_SIZE = 4096


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


class Client:
    def __init__(self, host="127.0.0.1", port=5001):
        self.host = host
        self.port = port
        self.socket = None

        self.username = None
        self.authenticated = False

        self.room = "general"
        self.room_is_private = False

        self.running = True
        self.handling_room = False

        self.room_queue = queue.Queue()

        self.color = "green"

    # ================= CONNECT =================
    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((self.host, self.port))
            print(f"Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    # ================= AUTH (from crypto-mous) =================
    def authenticate(self):
        while True:
            msg = self.socket.recv(BUFFER_SIZE).decode()

            if "username" in msg.lower():
                self.username = input("Username: ").strip()
                self.socket.send((self.username + "\n").encode())

            elif "password" in msg.lower():
                pwd = getpass.getpass("Password: ")
                self.socket.send((pwd + "\n").encode())

            elif "authenticated" in msg.lower() or "ok" in msg.lower():
                self.authenticated = True
                print("✅ Authenticated")
                return True

            elif "error" in msg.lower():
                print(f"❌ {msg}")

    # ================= ROOM HANDLING (from vincent) =================
    def handle_room(self, room_name):
        self.handling_room = True
        self.socket.send(f"/room {room_name}\n".encode())

        while True:
            try:
                resp = self.room_queue.get(timeout=5)

                if "OK" in resp:
                    self.room = room_name
                    print(f"✔ Switched to room {room_name}")
                    break

                elif "PRIVATE?" in resp:
                    ans = input("Private room? (yes/no): ")
                    self.socket.send((ans + "\n").encode())

                elif "PASSWORD" in resp:
                    pwd = input("Room password: ")
                    self.socket.send((pwd + "\n").encode())

                elif "ERROR" in resp:
                    print(f"❌ {resp}")

            except queue.Empty:
                print("Timeout room switch")
                break

        self.handling_room = False

    # ================= RECEIVE =================
    def receive(self):
        while self.running:
            try:
                data = self.socket.recv(BUFFER_SIZE).decode()
                for line in data.split("\n"):
                    if not line:
                        continue

                    if self.handling_room:
                        if any(x in line for x in ["OK", "PRIVATE?", "PASSWORD", "ERROR"]):
                            self.room_queue.put(line)
                            continue

                    print(line)

            except:
                break

    # ================= SEND =================
    def send(self):
        while self.running:
            msg = input(f"[{self.room}] {self.username}> ")

            if msg == "/quit":
                self.running = False
                break

            if msg.startswith("/room "):
                room = msg.split(" ", 1)[1]
                self.handle_room(room)
                continue

            self.socket.send((msg + "\n").encode())

    # ================= RUN =================
    def run(self):
        if not self.connect():
            return

        if not self.authenticate():
            return

        print(f"Welcome {self.username} in {self.room}")

        threading.Thread(target=self.receive, daemon=True).start()
        self.send()


if __name__ == "__main__":
    client = Client()
    client.run()