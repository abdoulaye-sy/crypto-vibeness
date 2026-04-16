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


def show_help():
    """Display available commands"""
    print("\n=== Chat Commands ===")
    print("  /forgot <username>           - Request password reset")
    print("  /reset <token> <password>    - Reset password with token")
    print("  /help                        - Show this help message")
    print("  quit                         - Exit the chat")
    print("====================\n")


def connect_to_server():
    """Connect to the chat server"""
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((HOST, PORT))
        
        print(f"[CONNECTED] Connected to {HOST}:{PORT}")
        print("Type '/help' for commands\n")
        
        # Receive username prompt
        server_msg = client_socket.recv(1024).decode('utf-8').strip()
        
        if server_msg == "ENTER_USERNAME":
            # Show menu
            print("=== Authentication Menu ===")
            print("1. Login/Register")
            print("2. Forgot Password")
            print("3. Reset Password")
            print("===========================\n")
            
            choice = input("Choose option (1-3): ").strip()
            
            if choice == "2":
                # Forgot password flow
                username = input("Enter your username: ").strip()
                
                if not username:
                    print("[ERROR] Username cannot be empty")
                    client_socket.close()
                    return
                
                # Send forgot command
                client_socket.send(f"/forgot {username}\n".encode('utf-8'))
                
                # Receive response (token)
                response = client_socket.recv(1024).decode('utf-8').strip()
                print(f"\n{response}")
                
                if "token" in response.lower():
                    # Ask if user wants to reset now
                    reset_now = input("\nDo you want to reset password now? (y/n): ").strip().lower()
                    
                    if reset_now == 'y':
                        token = input("Enter the token: ").strip()
                        new_password = getpass.getpass("Enter new password: ")
                        
                        # Send reset command
                        client_socket.send(f"/reset {token} {new_password}\n".encode('utf-8'))
                        
                        # Receive response
                        reset_response = client_socket.recv(1024).decode('utf-8').strip()
                        print(f"\n{reset_response}")
                
                client_socket.close()
                return
            
            elif choice == "3":
                # Reset password flow (if already have token)
                token = input("Enter your reset token: ").strip()
                new_password = getpass.getpass("Enter new password: ")
                
                # Send reset command
                client_socket.send(f"/reset {token} {new_password}\n".encode('utf-8'))
                
                # Receive response
                response = client_socket.recv(1024).decode('utf-8').strip()
                print(f"\n{response}")
                
                client_socket.close()
                return
            
            # Normal login/register flow
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
                    print("Type 'quit' to exit or '/help' for commands\n")
                    
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
                elif auth_response == "REJECT_PASSWORD":
                    print("[ERROR] Authentication failed: Wrong password")
                    client_socket.close()
                elif auth_response == "REJECT_WEAK_PASSWORD":
                    print("[ERROR] Password does not meet requirements:")
                    print("  - Minimum 8 characters")
                    print("  - At least 1 number")
                    print("  - At least 1 special character")
                    client_socket.close()
                else:
                    print(f"[ERROR] {auth_response}")
                    client_socket.close()
    
    except ConnectionRefusedError:
        print(f"[ERROR] Could not connect to {HOST}:{PORT}")
        print("[ERROR] Is the server running?")
    except Exception as e:
        print(f"[ERROR] {e}")


if __name__ == "__main__":
    connect_to_server()
