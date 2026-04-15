"""
Crypto Vibeness - Secure Chat Server
Stage 1: Base chat
"""

import socket
import threading
import json
import logging
import signal
import os
from datetime import datetime
from pathlib import Path

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

    def handle_client(self, client):
        try:
            # Request username with validation
            while True:
                client.send("USERNAME:")
                message = client.receive()
                if not message:
                    return
                
                username = message.strip()
                if not username:
                    client.send("ERROR:Invalid username")
                    continue

                with self.lock:
                    if username in self.usernames:
                        client.send("ERROR:Username already taken, please choose another")
                        continue
                    self.usernames.add(username)

                client.username = username
                with self.lock:
                    self.clients[client.addr] = client

                logger.info(f"User {username} connected")
                client.send("OK:Username accepted")
                break

            # Request room with private room handling
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
                else:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    # Sanitize message: remove newlines to prevent protocol corruption
                    sanitized_message = message.strip().replace('\n', ' ').replace('\r', '')
                    msg_data = json.dumps({
                        "type": "message",
                        "username": username,
                        "room": client.room.name,
                        "message": sanitized_message,
                        "timestamp": timestamp
                    })

                    logger.info(f"[{client.room.name}] {username}: {sanitized_message}")
                    client.room.broadcast(msg_data, sender=client)
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
