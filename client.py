import socket
import threading
import sys
import getpass

HOST = 'localhost'
PORT = 5000


def receive_messages(client_socket, username):
    """Continuously receive messages from server"""
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            
            if not message:
                # Server closed connection
                print("\n[DISCONNECTED] Connection closed by server")
                break
            
            # Clear current line and display message with proper formatting
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()
            
            # Display received message
            print(f"\n{message}")
            
            # Redisplay the prompt
            sys.stdout.write(f"{username}: ")
            sys.stdout.flush()
        
        except Exception as e:
            print(f"\n[ERROR] {e}")
            break


def send_messages(client_socket, username):
    """Send messages to server"""
    try:
        while True:
            message = input(f"{username}: ")
            
            if message.lower() == "quit":
                print("[CLIENT] Closing connection...")
                client_socket.close()
                break
            
            if message:
                client_socket.send(message.encode('utf-8'))
        
        sys.exit(0)
    
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


def connect_to_server():
    """Connect to the chat server"""
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((HOST, PORT))
        
        print(f"[CONNECTED] Connected to {HOST}:{PORT}\n")
        
        # Receive username prompt
        server_msg = client_socket.recv(1024).decode('utf-8').strip()
        
        if server_msg == "ENTER_USERNAME":
            username = input("Enter your username: ").strip()
            
            if not username:
                print("[ERROR] Username cannot be empty")
                client_socket.close()
                return
            
            # Send username
            client_socket.send(f"{username}\n".encode('utf-8'))
            
            # Wait for response
            response = client_socket.recv(1024).decode('utf-8').strip()
            
            if response == "REJECT_EMPTY":
                print("[ERROR] Username cannot be empty")
                client_socket.close()
                return
            elif response == "REJECT_TAKEN":
                print("[ERROR] Username already in use (active connection). Please try another.")
                client_socket.close()
                return
            elif response == "ENTER_PASSWORD":
                # Request password
                password = getpass.getpass("Enter your password: ")
                
                if not password:
                    print("[ERROR] Password cannot be empty")
                    client_socket.close()
                    return
                
                # Send password
                client_socket.send(f"{password}\n".encode('utf-8'))
                
                # Wait for authentication response
                auth_response = client_socket.recv(1024).decode('utf-8').strip()
                
                if auth_response == "ACCEPT":
                    print("[SUCCESS] Authentication successful!")
                    print("Type 'quit' to exit\n")
                    
                    # Start receive thread
                    receive_thread = threading.Thread(
                        target=receive_messages,
                        args=(client_socket, username),
                        daemon=True
                    )
                    receive_thread.start()
                    
                    # Send messages on main thread
                    send_messages(client_socket, username)
                elif auth_response == "REJECT_EMPTY_PASSWORD":
                    print("[ERROR] Password cannot be empty")
                    client_socket.close()
                    return
                elif auth_response == "REJECT_PASSWORD":
                    print("[ERROR] Password incorrect. Please try again.")
                    client_socket.close()
                    return
                elif auth_response == "REJECT_WEAK_PASSWORD":
                    print("[ERROR] Password is too weak. Requirements:")
                    print("  - Minimum 8 characters")
                    print("  - At least 1 number")
                    print("  - At least 1 special character (!@#$%^&* etc.)")
                    client_socket.close()
                    return
                elif auth_response == "REJECT_SERVER_ERROR":
                    print("[ERROR] Server error during authentication")
                    client_socket.close()
                    return
                else:
                    print(f"[ERROR] Unexpected server response: {auth_response}")
                    client_socket.close()
                    return
            else:
                print(f"[ERROR] Unexpected server response: {response}")
                client_socket.close()
    
    except ConnectionRefusedError:
        print(f"[ERROR] Could not connect to {HOST}:{PORT}")
        print("[ERROR] Make sure the server is running")
    except Exception as e:
        print(f"[ERROR] {e}")


if __name__ == "__main__":
    connect_to_server()
