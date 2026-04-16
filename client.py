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
                print("\n[DISCONNECTED] Connection closed by server")
                break
            
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()
            print(f"\n{message}")
            
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


def mode_login(client_socket):
    """LOGIN mode: normal authentication"""
    try:
        # Wait for username prompt
        server_msg = client_socket.recv(1024).decode('utf-8').strip()
        
        if server_msg != "ENTER_USERNAME":
            print(f"[ERROR] Unexpected response: {server_msg}")
            return None
        
        username = input("Enter your username: ").strip()
        
        if not username:
            print("[ERROR] Username cannot be empty")
            return None
        
        client_socket.send(f"{username}\n".encode('utf-8'))
        
        # Wait for password prompt
        response = client_socket.recv(1024).decode('utf-8').strip()
        
        if response == "REJECT_EMPTY":
            print("[ERROR] Username cannot be empty")
            return None
        elif response == "REJECT_TAKEN":
            print("[ERROR] Username already in use (active connection)")
            return None
        elif response != "ENTER_PASSWORD":
            print(f"[ERROR] Unexpected response: {response}")
            return None
        
        # Get password
        password = getpass.getpass("Enter your password: ")
        
        if not password:
            print("[ERROR] Password cannot be empty")
            return None
        
        client_socket.send(f"{password}\n".encode('utf-8'))
        
        # Wait for auth response
        auth_response = client_socket.recv(1024).decode('utf-8').strip()
        
        if auth_response == "ACCEPT":
            print("[SUCCESS] Authentication successful!")
            print("Type 'quit' to exit\n")
            return username
        elif auth_response == "REJECT_EMPTY_PASSWORD":
            print("[ERROR] Password cannot be empty")
        elif auth_response == "REJECT_PASSWORD":
            print("[ERROR] Authentication failed: Wrong password")
        elif auth_response == "REJECT_WEAK_PASSWORD":
            print("[ERROR] Password does not meet requirements:")
            print("  - Minimum 8 characters")
            print("  - At least 1 number")
            print("  - At least 1 special character")
        else:
            print(f"[ERROR] {auth_response}")
        
        return None
    
    except Exception as e:
        print(f"[ERROR] {e}")
        return None


def mode_forgot(client_socket):
    """FORGOT mode: request password reset token"""
    try:
        # Wait for username prompt
        server_msg = client_socket.recv(1024).decode('utf-8').strip()
        
        if server_msg != "ENTER_USERNAME":
            print(f"[ERROR] Unexpected response: {server_msg}")
            return False
        
        username = input("Enter your username: ").strip()
        
        if not username:
            print("[ERROR] Username cannot be empty")
            return False
        
        client_socket.send(f"{username}\n".encode('utf-8'))
        
        # Receive response
        response = client_socket.recv(1024).decode('utf-8').strip()
        print(f"\n{response}")
        
        if "Reset token" in response:
            return True
        
        return False
    
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def mode_reset(client_socket):
    """RESET mode: reset password with token"""
    try:
        # Wait for token prompt
        server_msg = client_socket.recv(1024).decode('utf-8').strip()
        
        if server_msg != "ENTER_TOKEN":
            print(f"[ERROR] Unexpected response: {server_msg}")
            return False
        
        token = input("Enter your reset token: ").strip()
        
        if not token:
            print("[ERROR] Token cannot be empty")
            return False
        
        client_socket.send(f"{token}\n".encode('utf-8'))
        
        # Check response
        response = client_socket.recv(1024).decode('utf-8').strip()
        
        if response != "ENTER_PASSWORD":
            print(f"{response}")
            return False
        
        # Get new password
        new_password = getpass.getpass("Enter new password: ")
        
        if not new_password:
            print("[ERROR] Password cannot be empty")
            return False
        
        client_socket.send(f"{new_password}\n".encode('utf-8'))
        
        # Receive confirmation
        confirmation = client_socket.recv(1024).decode('utf-8').strip()
        print(f"\n{confirmation}")
        
        return "[SUCCESS]" in confirmation
    
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def connect_to_server():
    """Main connection handler"""
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((HOST, PORT))
        
        print(f"[CONNECTED] Connected to {HOST}:{PORT}\n")
        
        # Show mode menu
        print("=== Authentication Menu ===")
        print("1. Login / Register")
        print("2. Forgot Password")
        print("3. Reset Password")
        print("===========================\n")
        
        choice = input("Choose mode (1-3): ").strip()
        
        # Receive mode prompt from server
        server_msg = client_socket.recv(1024).decode('utf-8').strip()
        
        if server_msg != "SELECT_MODE":
            print(f"[ERROR] Unexpected server response: {server_msg}")
            client_socket.close()
            return
        
        # Send mode
        if choice == "1":
            client_socket.send("LOGIN\n".encode('utf-8'))
            username = mode_login(client_socket)
            
            if username:
                # Start receive thread
                receive_thread = threading.Thread(
                    target=receive_messages,
                    args=(client_socket, username),
                    daemon=True
                )
                receive_thread.start()
                send_messages(client_socket, username)
        
        elif choice == "2":
            client_socket.send("FORGOT\n".encode('utf-8'))
            success = mode_forgot(client_socket)
            
            if success:
                reset_now = input("\nDo you want to reset now? (y/n): ").strip().lower()
                
                if reset_now == 'y':
                    print("\n=== Reset Password ===")
                    print("Please reconnect and choose 'Reset Password'")
                    print("======================\n")
            
            client_socket.close()
        
        elif choice == "3":
            client_socket.send("RESET\n".encode('utf-8'))
            success = mode_reset(client_socket)
            client_socket.close()
        
        else:
            client_socket.send("INVALID\n".encode('utf-8'))
            client_socket.close()
    
    except ConnectionRefusedError:
        print(f"[ERROR] Could not connect to {HOST}:{PORT}")
        print("[ERROR] Is the server running?")
    except Exception as e:
        print(f"[ERROR] {e}")


if __name__ == "__main__":
    connect_to_server()
