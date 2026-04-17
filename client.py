import socket
import threading
import sys
import getpass
import re
import time

HOST = 'localhost'
PORT = 5000

ENCRYPTION_KEY = 'chatkey123'

def encrypt(message):
    """Encrypt message using XOR with shared key"""
    if not message:
        return message
    encrypted = []
    key_len = len(ENCRYPTION_KEY)
    for i, char in enumerate(message):
        key_char = ENCRYPTION_KEY[i % key_len]
        encrypted_char = chr(ord(char) ^ ord(key_char))
        encrypted.append(encrypted_char)
    return ''.join(encrypted)


def decrypt(message):
    """Decrypt message using XOR with shared key"""
    if not message:
        return message
    # XOR is symmetric - decryption is same as encryption
    return encrypt(message)


# ANSI Color codes
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# Message cache for tracking delivery/read status
message_cache = {}
current_user = None
current_room = None


def format_message_ui(sender, text, msg_id=None, is_own=False, status=None):
    """Format message with nice UI"""
    # Determine sender indicator
    if is_own:
        sender_color = Colors.GREEN
        sender_indicator = "🟢"
    else:
        sender_color = Colors.BLUE
        sender_indicator = "🔵"
    
    # Build status display
    status_display = ""
    if status:
        if status == "read":
            status_display = f" {Colors.GREEN}[✓✓] read{Colors.RESET}"
        elif status == "delivered":
            status_display = f" {Colors.YELLOW}[✓] delivered{Colors.RESET}"
    
    # Format the message box
    box_width = 40
    sender_str = f"{sender_indicator} {sender_color}{sender}{Colors.RESET} {Colors.GRAY}({current_room}){Colors.RESET}"
    
    # Truncate long messages or wrap them
    lines = text.split('\n')
    output = f"\n{Colors.BOLD}┌{'─' * (box_width - 2)}┐{Colors.RESET}\n"
    output += f"{Colors.BOLD}│{Colors.RESET} {sender_str}\n"
    output += f"{Colors.BOLD}│{Colors.RESET}\n"
    
    for line in lines:
        if len(line) > box_width - 4:
            # Wrap long lines
            words = line.split()
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 <= box_width - 4:
                    current_line += word + " "
                else:
                    output += f"{Colors.BOLD}│{Colors.RESET} {current_line.ljust(box_width - 4)} {Colors.BOLD}│{Colors.RESET}\n"
                    current_line = word + " "
            if current_line:
                output += f"{Colors.BOLD}│{Colors.RESET} {current_line.ljust(box_width - 4)} {Colors.BOLD}│{Colors.RESET}\n"
        else:
            output += f"{Colors.BOLD}│{Colors.RESET} {line.ljust(box_width - 4)} {Colors.BOLD}│{Colors.RESET}\n"
    
    output += f"{Colors.BOLD}│{Colors.RESET} {status_display.ljust(box_width - 4)} {Colors.BOLD}│{Colors.RESET}\n"
    output += f"{Colors.BOLD}└{'─' * (box_width - 2)}┘{Colors.RESET}"
    
    return output


def format_system_message(message):
    """Format system messages nicely"""
    return f"\n{Colors.YELLOW}{Colors.BOLD}▸{Colors.RESET} {Colors.YELLOW}{message}{Colors.RESET}"


def parse_and_display_message(raw_message, username):
    """Parse incoming message and display with proper formatting"""
    global current_room, message_cache
    
    raw_message = raw_message.strip()
    
    if not raw_message:
        return
    
    # Extract MSG_ID if present
    msg_id = None
    msg_lines = raw_message.split('\n')
    final_lines = []
    
    for line in msg_lines:
        if line.startswith('MSG_ID:'):
            msg_id = line.replace('MSG_ID:', '').strip()
            if msg_id:
                message_cache[msg_id] = {'status': 'delivered'}
        else:
            final_lines.append(line)
    
    text_content = '\n'.join(final_lines).strip()
    
    # Check if it's a system message
    if text_content.startswith('[SERVER]'):
        # Parse system messages
        if 'joined' in text_content:
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()
            print(format_system_message(text_content))
        elif 'left' in text_content:
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()
            print(format_system_message(text_content))
        elif 'typing' in text_content:
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()
            print(format_system_message(text_content))
        else:
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()
            print(format_system_message(text_content))
        return
    
    # Check if it's a DM message
    if text_content.startswith('[DM from '):
        # Format: [DM from sender]: message
        # Extract and decrypt the message
        dm_parts = text_content.split(']: ', 1)
        if len(dm_parts) == 2:
            dm_header = dm_parts[0] + ']: '
            dm_message = dm_parts[1]
            dm_message = decrypt(dm_message)
            decrypted_dm = dm_header + dm_message
        else:
            decrypted_dm = text_content
        
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
        dm_display = f"\n{Colors.BOLD}{Colors.CYAN}💬 PRIVATE MESSAGE 💬{Colors.RESET}\n{Colors.CYAN}{decrypted_dm}{Colors.RESET}\n"
        print(dm_display)
        return
    
    # Check if it's a sent DM confirmation
    if text_content.startswith('[DM → '):
        # Format: [DM → recipient]: message
        # Extract and decrypt the message
        dm_parts = text_content.split(']: ', 1)
        if len(dm_parts) == 2:
            dm_header = dm_parts[0] + ']: '
            dm_message = dm_parts[1]
            dm_message = decrypt(dm_message)
            decrypted_dm = dm_header + dm_message
        else:
            decrypted_dm = text_content
        
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
        dm_display = f"\n{Colors.GREEN}{Colors.BOLD}✓ Message sent{Colors.RESET}\n{Colors.GREEN}{decrypted_dm}{Colors.RESET}\n"
        print(dm_display)
        return
    
    # Parse regular messages (format: "sender: message")
    if ':' in text_content:
        parts = text_content.split(':', 1)
        sender = parts[0].strip()
        message = parts[1] if len(parts) > 1 else ""
        
        # Carefully extract encrypted message:
        # Split on 'MSG_ID:' to find where actual message ends
        if 'MSG_ID:' in message:
            message = message.split('MSG_ID:')[0]
        
        # Remove only leading space, not other whitespace (some whitespace is encrypted!)
        message = message.lstrip(' ')
        
        # Remove trailing newline only
        if message.endswith('\n'):
            message = message[:-1]
        
        # Decrypt message (content now preserved)
        message = decrypt(message)
        
        # Update current room from recent messages if needed
        if sender and sender != "[SERVER]":
            is_own = (sender.lower() == username.lower())
            
            # Clear the input line
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()
            
            # Display formatted message
            status = message_cache.get(msg_id, {}).get('status') if msg_id else None
            print(format_message_ui(sender, message, msg_id=msg_id, is_own=is_own, status=status))
        else:
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()
            print(text_content)
    else:
        # Just display as-is if can't parse
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
        print(format_system_message(text_content))


def receive_messages(client_socket, username):
    """Continuously receive messages from server"""
    global current_user
    current_user = username
    
    while True:
        try:
            # Receive as bytes first
            message_bytes = client_socket.recv(1024)
            
            if not message_bytes:
                print("\n[DISCONNECTED] Connection closed by server")
                break
            
            # Decode with error handling for binary encrypted content
            message = message_bytes.decode('utf-8', errors='replace')
            
            parse_and_display_message(message, username)
            
            sys.stdout.write(f"{Colors.CYAN}{username}:{Colors.RESET} ")
            sys.stdout.flush()
        
        except Exception as e:
            print(f"\n{Colors.RED}[ERROR] {e}{Colors.RESET}")
            break


def send_messages(client_socket, username):
    """Send messages to server"""
    global current_user, message_cache
    current_user = username
    
    try:
        while True:
            message = input(f"{Colors.CYAN}{username}:{Colors.RESET} ")
            
            if message.lower() == "quit":
                print(f"{Colors.YELLOW}[CLIENT] Closing connection...{Colors.RESET}")
                client_socket.close()
                break
            
            if message:
                # Handle /ack command - track locally
                if message.startswith('/ack'):
                    parts = message.split()
                    if len(parts) > 1:
                        msg_id = parts[1]
                        if msg_id in message_cache:
                            message_cache[msg_id]['status'] = 'read'
                
                client_socket.send(message.encode('utf-8'))
        
        sys.exit(0)
    
    except Exception as e:
        print(f"{Colors.RED}[ERROR] {e}{Colors.RESET}")
        sys.exit(1)


def mode_login(client_socket):
    """LOGIN mode: normal authentication"""
    try:
        # Wait for username prompt
        server_msg = client_socket.recv(1024).decode('utf-8').strip()
        
        if server_msg != "ENTER_USERNAME":
            print(f"{Colors.RED}[ERROR] Unexpected response: {server_msg}{Colors.RESET}")
            return None
        
        username = input("Enter your username: ").strip()
        
        if not username:
            print(f"{Colors.RED}[ERROR] Username cannot be empty{Colors.RESET}")
            return None
        
        client_socket.send(f"{username}\n".encode('utf-8'))
        
        # Wait for password prompt
        response = client_socket.recv(1024).decode('utf-8').strip()
        
        if response == "REJECT_EMPTY":
            print(f"{Colors.RED}[ERROR] Username cannot be empty{Colors.RESET}")
            return None
        elif response == "REJECT_TAKEN":
            print(f"{Colors.RED}[ERROR] Username already in use (active connection){Colors.RESET}")
            return None
        elif response != "ENTER_PASSWORD":
            print(f"{Colors.RED}[ERROR] Unexpected response: {response}{Colors.RESET}")
            return None
        
        # Get password
        password = getpass.getpass("Enter your password: ")
        
        if not password:
            print(f"{Colors.RED}[ERROR] Password cannot be empty{Colors.RESET}")
            return None
        
        client_socket.send(f"{password}\n".encode('utf-8'))
        
        # Wait for auth response
        auth_response = client_socket.recv(1024).decode('utf-8').strip()
        
        if auth_response == "ACCEPT":
            print(f"{Colors.GREEN}[SUCCESS] Authentication successful!{Colors.RESET}")
            print(f"{Colors.GRAY}Type 'quit' to exit, '/help' for commands\n{Colors.RESET}")
            return username
        elif auth_response == "REJECT_EMPTY_PASSWORD":
            print(f"{Colors.RED}[ERROR] Password cannot be empty{Colors.RESET}")
        elif auth_response == "REJECT_PASSWORD":
            print(f"{Colors.RED}[ERROR] Authentication failed: Wrong password{Colors.RESET}")
        elif auth_response == "REJECT_WEAK_PASSWORD":
            print(f"{Colors.RED}[ERROR] Password does not meet requirements:{Colors.RESET}")
            print(f"{Colors.RED}  - Minimum 8 characters{Colors.RESET}")
            print(f"{Colors.RED}  - At least 1 number{Colors.RESET}")
            print(f"{Colors.RED}  - At least 1 special character{Colors.RESET}")
        else:
            print(f"{Colors.RED}[ERROR] {auth_response}{Colors.RESET}")
        
        return None
    
    except Exception as e:
        print(f"{Colors.RED}[ERROR] {e}{Colors.RESET}")
        return None


def mode_forgot(client_socket):
    """FORGOT mode: request password reset token"""
    try:
        # Wait for username prompt
        server_msg = client_socket.recv(1024).decode('utf-8').strip()
        
        if server_msg != "ENTER_USERNAME":
            print(f"{Colors.RED}[ERROR] Unexpected response: {server_msg}{Colors.RESET}")
            return False
        
        username = input("Enter your username: ").strip()
        
        if not username:
            print(f"{Colors.RED}[ERROR] Username cannot be empty{Colors.RESET}")
            return False
        
        client_socket.send(f"{username}\n".encode('utf-8'))
        
        # Receive response
        response = client_socket.recv(1024).decode('utf-8').strip()
        print(f"{Colors.YELLOW}{response}{Colors.RESET}")
        
        if "Reset token" in response:
            return True
        
        return False
    
    except Exception as e:
        print(f"{Colors.RED}[ERROR] {e}{Colors.RESET}")
        return False


def mode_reset(client_socket):
    """RESET mode: reset password with token"""
    try:
        # Wait for token prompt
        server_msg = client_socket.recv(1024).decode('utf-8').strip()
        
        if server_msg != "ENTER_TOKEN":
            print(f"{Colors.RED}[ERROR] Unexpected response: {server_msg}{Colors.RESET}")
            return False
        
        token = input("Enter your reset token: ").strip()
        
        if not token:
            print(f"{Colors.RED}[ERROR] Token cannot be empty{Colors.RESET}")
            return False
        
        client_socket.send(f"{token}\n".encode('utf-8'))
        
        # Check response
        response = client_socket.recv(1024).decode('utf-8').strip()
        
        if response != "ENTER_PASSWORD":
            print(f"{Colors.RED}{response}{Colors.RESET}")
            return False
        
        # Get new password
        new_password = getpass.getpass("Enter new password: ")
        
        if not new_password:
            print(f"{Colors.RED}[ERROR] Password cannot be empty{Colors.RESET}")
            return False
        
        client_socket.send(f"{new_password}\n".encode('utf-8'))
        
        # Receive confirmation
        confirmation = client_socket.recv(1024).decode('utf-8').strip()
        print(f"{Colors.GREEN}{confirmation}{Colors.RESET}")
        
        return "[SUCCESS]" in confirmation
    
    except Exception as e:
        print(f"{Colors.RED}[ERROR] {e}{Colors.RESET}")
        return False


def connect_to_server():
    """Main connection handler"""
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((HOST, PORT))
        
        print(f"{Colors.GREEN}[CONNECTED]{Colors.RESET} Connected to {HOST}:{PORT}\n")
        
        # Show mode menu with colors
        print(f"{Colors.BOLD}{Colors.CYAN}=== Authentication Menu ==={Colors.RESET}")
        print(f"{Colors.CYAN}1. Login / Register{Colors.RESET}")
        print(f"{Colors.CYAN}2. Forgot Password{Colors.RESET}")
        print(f"{Colors.CYAN}3. Reset Password{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}==========================={Colors.RESET}\n")
        
        choice = input("Choose mode (1-3): ").strip()
        
        # Receive mode prompt from server
        server_msg = client_socket.recv(1024).decode('utf-8').strip()
        
        if server_msg != "SELECT_MODE":
            print(f"{Colors.RED}[ERROR] Unexpected server response: {server_msg}{Colors.RESET}")
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
                    print(f"{Colors.YELLOW}\n=== Reset Password ==={Colors.RESET}")
                    print(f"{Colors.YELLOW}Please reconnect and choose 'Reset Password'{Colors.RESET}")
                    print(f"{Colors.YELLOW}======================\n{Colors.RESET}")
            
            client_socket.close()
        
        elif choice == "3":
            client_socket.send("RESET\n".encode('utf-8'))
            success = mode_reset(client_socket)
            client_socket.close()
        
        else:
            client_socket.send("INVALID\n".encode('utf-8'))
            client_socket.close()
    
    except ConnectionRefusedError:
        print(f"{Colors.RED}[ERROR] Could not connect to {HOST}:{PORT}{Colors.RESET}")
        print(f"{Colors.RED}[ERROR] Is the server running?{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}[ERROR] {e}{Colors.RESET}")


if __name__ == "__main__":
    connect_to_server()
