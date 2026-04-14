"""
Crypto Vibeness - Secure Chat Server
Stage 1: Base chat
"""

import socket
import threading
import json
import logging
import signal
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

HOST = '127.0.0.1'
PORT = 5000

class Room:
    def __init__(self, name):
        self.name = name
        self.clients = []
        self.lock = threading.Lock()

    def add_client(self, client):
        with self.lock:
            self.clients.append(client)

    def remove_client(self, client):
        with self.lock:
            if client in self.clients:
                self.clients.remove(client)

    def broadcast(self, message, sender=None):
        with self.lock:
            for client in self.clients:
                if client != sender:
                    try:
                        client.send(message)
                    except:
                        pass

class Client:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.username = None
        self.room = None

    def send(self, message):
        try:
            self.conn.sendall(message.encode('utf-8') + b'\n')
        except:
            pass

    def receive(self):
        try:
            data = b''
            while True:
                chunk = self.conn.recv(1024)
                if not chunk:
                    return None
                data += chunk
                if b'\n' in data:
                    line, remainder = data.split(b'\n', 1)
                    return line.decode('utf-8'), remainder
        except:
            return None

class Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.rooms = {}
        self.clients = {}
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

    def get_or_create_room(self, room_name):
        with self.lock:
            if room_name not in self.rooms:
                self.rooms[room_name] = Room(room_name)
            return self.rooms[room_name]

    def handle_client(self, client):
        try:
            # Request username
            client.send("USERNAME:")
            message = self.receive_message(client)
            if not message:
                return
            
            username = message.strip()
            if not username:
                client.send("ERROR:Invalid username")
                return

            client.username = username
            with self.lock:
                self.clients[client.addr] = client

            logger.info(f"User {username} connected")

            # Request room
            client.send("ROOM:")
            message = self.receive_message(client)
            if not message:
                return

            room_name = message.strip() or "general"
            room = self.get_or_create_room(room_name)
            client.room = room
            room.add_client(client)

            logger.info(f"User {username} joined room {room_name}")
            
            # Notify room
            timestamp = datetime.now().strftime("%H:%M:%S")
            notification = json.dumps({
                "type": "system",
                "username": "SERVER",
                "message": f"{username} joined the room",
                "timestamp": timestamp,
                "room": room_name
            })
            room.broadcast(notification, sender=client)
            client.send("OK:Connected to " + room_name)

            # Handle messages
            while True:
                message = self.receive_message(client)
                if not message:
                    break

                timestamp = datetime.now().strftime("%H:%M:%S")
                msg_data = json.dumps({
                    "type": "message",
                    "username": username,
                    "message": message.strip(),
                    "timestamp": timestamp,
                    "room": room_name
                })

                logger.info(f"[{room_name}] {username}: {message.strip()}")
                room.broadcast(msg_data, sender=client)
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
                        "username": "SERVER",
                        "message": f"{client.username} left the room",
                        "timestamp": timestamp,
                        "room": client.room.name
                    })
                    client.room.broadcast(notification)
                    logger.info(f"User {client.username} disconnected")

            with self.lock:
                if client.addr in self.clients:
                    del self.clients[client.addr]
            
            try:
                client.conn.close()
            except:
                pass

    def receive_message(self, client):
        try:
            data = client.conn.recv(1024).decode('utf-8')
            return data.strip() if data else None
        except:
            return None

if __name__ == "__main__":
    server = Server(HOST, PORT)
    server.start()
