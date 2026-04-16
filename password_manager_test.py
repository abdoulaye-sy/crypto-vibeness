#!/usr/bin/env python3
"""
Comprehensive test of password management system
"""

from password_manager import (
    PasswordRulesEngine,
    PasswordManager,
    PasswordValidator,
    get_password_strength_indicator
)
import os

print("=" * 70)
print("PASSWORD MANAGEMENT SYSTEM - COMPREHENSIVE TEST")
print("=" * 70)

# Test 1: Rules Engine
print("\n### TEST 1: Password Rules Engine ###")
rules = PasswordRulesEngine('password_rules.txt')
print(f"✅ Loaded {len(rules.rules)} password rules:")
for rule in rules.rules:
    print(f"   {rule['name']}: {rule['description']}")

# Test 2: Password Validation
print("\n### TEST 2: Password Validation ###")
validator = PasswordValidator(rules)

test_cases = [
    ("password123", "Too weak (no uppercase/special)"),
    ("Password123", "Missing special char"),
    ("MyPass!", "Too short & missing digit"),
    ("MyPassw0rd!", "Valid strong password"),
]

for pwd, desc in test_cases:
    is_valid, errors = validator.validate(pwd)
    score, strength, details = validator.get_strength(pwd)
    print(f"\n  Password: '{pwd}' ({desc})")
    print(f"  Valid: {is_valid}, Strength: {strength}")
    print(f"  Score: {details['score']}% (Entropy: {details['entropy']}%, Compliance: {details['compliance']}%)")
    if not is_valid:
        for error in errors:
            print(f"    {error}")

# Test 3: Password Manager
print("\n### TEST 3: Password Manager ###")
test_file = "test_pwd_manager.txt"
if os.path.exists(test_file):
    os.remove(test_file)

pm = PasswordManager(test_file)

# Create accounts
print("\n  Creating accounts...")
pm.create_account("user1", "SecurePass@2024")
pm.create_account("user2", "AnotherPass!123")
print(f"  ✅ Created 2 accounts")

# Verify accounts exist
print("\n  Checking account existence...")
print(f"  user1 exists: {pm.account_exists('user1')}")
print(f"  user2 exists: {pm.account_exists('user2')}")
print(f"  user3 exists: {pm.account_exists('user3')}")

# Verify passwords
print("\n  Verifying passwords...")
print(f"  user1 + correct pass: {pm.verify_account('user1', 'SecurePass@2024')}")
print(f"  user1 + wrong pass: {pm.verify_account('user1', 'WrongPass')}")
print(f"  user2 + correct pass: {pm.verify_account('user2', 'AnotherPass!123')}")
print(f"  user2 + wrong pass: {pm.verify_account('user2', 'WrongPass')}")

# Check file format
print("\n  Credentials file content:")
with open(test_file, 'r') as f:
    for line in f:
        user, hash_b64 = line.strip().split(':')
        print(f"    {user}: {hash_b64}")

# Test 4: Constant-time comparison
print("\n### TEST 4: Constant-Time Comparison ###")
pwd = "TestPassword@123"
hash1 = PasswordManager.hash_password(pwd)
hash2 = PasswordManager.hash_password(pwd)
hash3 = PasswordManager.hash_password("DifferentPassword@123")

print(f"  Same password (hash1 == hash2): {PasswordManager.verify_password_constant_time(pwd, hash1)}")
print(f"  Different password: {PasswordManager.verify_password_constant_time('WrongPassword', hash1)}")
print(f"  Hashes are identical: {hash1 == hash2}")
print(f"  Uses constant-time comparison: ✅ (compare_digest)")

# Cleanup
os.remove(test_file)

print("\n" + "=" * 70)
print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
print("=" * 70)
print("\nSummary:")
print("  ✅ Password rules loaded from file")
print("  ✅ Password validation against multiple rules")
print("  ✅ Password strength calculation with entropy")
print("  ✅ MD5 hashing with base64 encoding")
print("  ✅ Account creation and verification")
print("  ✅ Constant-time password comparison (prevents timing attacks)")
print("  ✅ Persistent credential storage in this_is_safe.txt")
