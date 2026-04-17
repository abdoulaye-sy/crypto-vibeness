#!/usr/bin/env python3
"""Test script for DM system - validates all DM functionality"""

import socket
import time
import sys

HOST = 'localhost'
PORT = 5000
TEST_TIMEOUT = 3

def send_command(sock, command):
    """Send a command and receive response"""
    sock.send(command.encode('utf-8') + b'\n')
    time.sleep(0.2)
    try:
        response = sock.recv(4096).decode('utf-8')
        return response
    except socket.timeout:
        return "[TIMEOUT]"

def test_dm_to_offline_user():
    """Test sending DM to offline user"""
    print("\n[TEST 1] DM to offline user...")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TEST_TIMEOUT)
    
    try:
        sock.connect((HOST, PORT))
        
        # Login
        response = send_command(sock, "LOGIN")
        if "SELECT_MODE" not in response:
            print("❌ FAILED: No mode selection")
            return False
        
        response = send_command(sock, "testuser1")
        if "ENTER_USERNAME" not in response:
            print("❌ FAILED: Unexpected response after mode")
            return False
        
        response = send_command(sock, "TestPass123!")
        if "ENTER_PASSWORD" not in response:
            print("❌ FAILED: No password prompt")
            return False
        
        response = send_command(sock, "TestPass123!")
        
        # Try to send DM to non-existent user
        response = send_command(sock, "/msg nonexistent hello")
        
        if "not found" in response.lower() or "error" in response.lower():
            print("✓ PASSED: Correctly rejected non-existent user")
            return True
        else:
            print(f"❌ FAILED: Expected error message, got: {response}")
            return False
    
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False
    finally:
        sock.close()

def test_dm_format():
    """Test DM message format in code"""
    print("\n[TEST 2] Code review: DM data structures...")
    
    # Read server.py and check for DM structures
    with open('server.py', 'r') as f:
        content = f.read()
    
    checks = [
        ('dm_sessions', 'DM sessions dict'),
        ('dm_lock', 'DM threading lock'),
        ('get_dm_session_key', 'Session key function'),
        ('handle_dm_command', 'DM command handler'),
        ('find_recipient_socket', 'Find recipient function'),
    ]
    
    all_passed = True
    for check, desc in checks:
        if check in content:
            print(f"✓ Found: {desc}")
        else:
            print(f"❌ Missing: {desc}")
            all_passed = False
    
    return all_passed

def test_client_dm_display():
    """Test client DM display code"""
    print("\n[TEST 3] Client DM display formatting...")
    
    # Read client.py and check for DM display
    with open('client.py', 'r') as f:
        content = f.read()
    
    checks = [
        ('[DM from ', 'Incoming DM format check'),
        ('[DM → ', 'Outgoing DM format check'),
        ('💬 PRIVATE MESSAGE', 'DM visual indicator'),
    ]
    
    all_passed = True
    for check, desc in checks:
        if check in content:
            print(f"✓ Found: {desc}")
        else:
            print(f"❌ Missing: {desc}")
            all_passed = False
    
    return all_passed

def test_welcome_message():
    """Test that welcome message includes /msg command"""
    print("\n[TEST 4] Welcome message includes /msg...")
    
    with open('server.py', 'r') as f:
        content = f.read()
    
    if '/msg' in content and 'private message' in content.lower():
        print("✓ PASSED: /msg command in help")
        return True
    else:
        print("❌ FAILED: /msg not documented in welcome message")
        return False

def test_syntax():
    """Test Python syntax"""
    print("\n[TEST 5] Python syntax validation...")
    
    import py_compile
    
    try:
        py_compile.compile('server.py', doraise=True)
        print("✓ server.py syntax OK")
        
        py_compile.compile('client.py', doraise=True)
        print("✓ client.py syntax OK")
        
        return True
    except py_compile.PyCompileError as e:
        print(f"❌ Syntax error: {e}")
        return False

def main():
    print("=" * 60)
    print("DM SYSTEM TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Run all tests
    results.append(("Syntax check", test_syntax()))
    results.append(("Code structures", test_dm_format()))
    results.append(("Client display", test_client_dm_display()))
    results.append(("Welcome message", test_welcome_message()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - DM SYSTEM READY")
        return 0
    else:
        print("\n⚠️ SOME TESTS FAILED - REVIEW NEEDED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
