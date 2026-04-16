# Password Management System

Complete guide to the password management system implemented in Crypto Vibeness.

## Overview

The system provides:
- ✅ MD5 password hashing with base64 encoding
- ✅ Configurable password validation rules (5 built-in)
- ✅ Entropy-based password strength scoring
- ✅ Constant-time password verification (timing-attack resistant)
- ✅ Persistent credential storage in `this_is_safe.txt`

## Password Rules

Five built-in rules enforced at signup:

1. **Minimum Length (8 characters)**
   - Example: "Pass" ❌ → "Password1" ✅

2. **Uppercase Letter Required**
   - Example: "password1!" ❌ → "Password1!" ✅

3. **Lowercase Letter Required**
   - Example: "PASSWORD1!" ❌ → "Password1!" ✅

4. **Digit Required**
   - Example: "Password!" ❌ → "Password1!" ✅

5. **Special Character Required**
   - Example: "Password1" ❌ → "Password1!" ✅

All special characters accepted: `!@#$%^&*-_+=.`

## Password Strength Scoring

Strength is calculated as:
```
Score = (Compliance × 0.7) + (Entropy × 0.3)
  - Compliance: percentage of rules passed (0-100%)
  - Entropy: character set diversity (0-100%)
```

### Strength Levels

| Label | Range | Description |
|-------|-------|-------------|
| 🔴 Very Weak | 0-40% | Critical weaknesses |
| 🟠 Weak | 40-60% | Multiple missing rules |
| 🟡 Fair | 60-80% | One missing rule or low entropy |
| 🟢 Strong | 80%+ | All rules met + good entropy |

### Example Passwords

```
weak               → 🔴 Very Weak (18%)
  ❌ Min length (8)
  ❌ Uppercase
  ❌ Digit
  ❌ Special

Password123       → 🟡 Fair (71%)
  ✅ All basic rules
  ❌ Missing special char

Password1!       → 🟢 Strong (91%)
  ✅ All rules passed
  ✅ Good entropy

VeryLong@Pass123  → 🟢 Strong (100%)
  ✅ All rules
  ✅ Excellent entropy
```

## Hashing Algorithm

### MD5 with Base64 Encoding

```python
import hashlib
import base64

password = "MyPassword123!"
# Step 1: MD5 hash (binary)
md5_hash = hashlib.md5(password.encode()).digest()
# Step 2: Base64 encode
hash_b64 = base64.b64encode(md5_hash).decode()
# Result: "SANBoKoloNVpemBtSVF9/Q=="
```

### Why MD5 for This Project?

Pros:
- ✅ Standard library (no dependencies)
- ✅ Fast (< 1ms per password)
- ✅ Simple to understand
- ✅ Good for learning

Cons (for production):
- ❌ No salt (deterministic)
- ❌ Cryptographically weak
- ❌ Vulnerable to rainbow tables
- ❌ Not recommended for real passwords

### Future: Better Algorithms

For production, use:
- **bcrypt**: Slow, salted, configurable work factor
- **argon2**: Memory-hard, resistant to GPU attacks
- **PBKDF2**: Standards-based, salted

## Constant-Time Comparison

Prevents timing attacks where attackers measure response time to guess passwords.

```python
from hmac import compare_digest

# ✅ Correct: constant-time comparison
result = compare_digest(provided_hash, stored_hash)

# ❌ Wrong: vulnerable to timing attack
result = (provided_hash == stored_hash)
```

## File Formats

### Credentials File (this_is_safe.txt)

```
username:hash_base64
alice:sBzpBKHRysnX3na1VIJlNw==
bob:qNhFuTUhNTkv30ck+Y1bMQ==
charlie:ZTIHtiT7GYD0NIYG2+nBFQ==
```

- One account per line
- Username and hash separated by single colon
- No spaces around colon
- Hash is 24 characters (MD5 in base64)
- **Never store plaintext passwords**

### Password Rules File (password_rules.txt)

```
# Format: name:description:python_expression
min_length:8:len({password}) >= 8
has_uppercase:At least one uppercase (A-Z):any(c.isupper() for c in {password})
has_lowercase:At least one lowercase (a-z):any(c.islower() for c in {password})
has_digit:At least one digit (0-9):any(c.isdigit() for c in {password})
has_special:At least one special (!@#$%^&*):any(c in "!@#$%^&*-_+=." for c in {password})
```

To add custom rules:
1. Add new line to `password_rules.txt`
2. Use format: `name:description:expression`
3. Use `{password}` as placeholder
4. Expression must return boolean

Example custom rule:
```
no_spaces:No spaces allowed:' ' not in {password}
min_entropy:Strong entropy:len(set({password})) >= 5
```

## Usage

### Interactive Signup

```bash
$ python3 client.py
Enter username: alice
Create account? (yes/no): yes
Enter password: weak
💪 🔴 Very Weak (18%)
  ❌ Minimum length (8)
  ❌ At least one uppercase letter (A-Z)
  ❌ At least one digit (0-9)
  ❌ At least one special character (!@#$%^&*)
Enter password again: Strong@Pass123
💪 🟢 Strong (91%)
Confirm password: Strong@Pass123
✅ Authenticated as alice
```

### Interactive Login

```bash
$ python3 client.py
Enter username: alice
Enter password: Strong@Pass123
✅ Authenticated as alice
```

### Wrong Password with Retry

```bash
$ python3 client.py
Enter username: alice
Enter password: WrongPassword
❌ Invalid password
Enter password: Strong@Pass123
✅ Authenticated as alice
```

## Testing

### Run Full Test Suite

```bash
python3 password_manager_test.py
```

Output shows:
- Rules engine loading
- Password validation examples
- Account management
- Constant-time comparison

### Test Specific Components

```python
# Test password validation
from password_manager import PasswordValidator, PasswordRulesEngine

rules = PasswordRulesEngine('password_rules.txt')
validator = PasswordValidator(rules)

is_valid, errors = validator.validate("Password123!")
score, strength, details = validator.get_strength("Password123!")

print(f"Valid: {is_valid}")
print(f"Strength: {strength}")
print(f"Score: {details['score']}%")
```

## Troubleshooting

### "Password too weak" but password looks strong

Check:
1. Does password meet all 5 rules? (length, upper, lower, digit, special)
2. Special characters must be in: `!@#$%^&*-_+=.`
3. Other symbols like `()[]{}` are NOT accepted

### Password accepted but different on login

This shouldn't happen - MD5 is deterministic. If it occurs:
1. Check for typos
2. Verify caps lock
3. Ensure no extra spaces

### How do I reset a password?

Currently not implemented. Options:
1. Delete entry from `this_is_safe.txt` and signup again
2. Implement password reset feature (future)

## Security Considerations

### What This Protects Against
- ✅ Plaintext password theft (all hashed)
- ✅ Timing attacks (constant-time comparison)
- ✅ Weak passwords (5 validation rules)
- ✅ Easy-to-guess passwords (entropy scoring)

### What This Does NOT Protect Against
- ❌ Rainbow table attacks (no salt on MD5)
- ❌ Brute force attempts (no rate limiting)
- ❌ Compromised database (hashes are weak)
- ❌ Keylogger/malware (client-side)
- ❌ Network sniffing (no TLS/SSL)

### Recommendations for Production

1. **Use bcrypt or argon2** instead of MD5
2. **Use TLS/SSL** for network encryption
3. **Implement rate limiting** on login attempts
4. **Add account lockout** after failed attempts
5. **Implement password reset** via email
6. **Use HTTPS** for web interface
7. **Never log passwords** in any form

## API Reference

### PasswordRulesEngine

```python
from password_manager import PasswordRulesEngine

# Load rules from file
engine = PasswordRulesEngine('password_rules.txt')

# Evaluate password
is_valid, failed_rules, passed_count = engine.evaluate_password(password)

# Get human-readable rules
rules_list = engine.get_rules_summary()
# Returns: ['- Minimum length (8)', '- At least one uppercase...', ...]
```

### PasswordManager

```python
from password_manager import PasswordManager

# Create manager
pm = PasswordManager('this_is_safe.txt')

# Hash a password (static method)
hash_b64 = PasswordManager.hash_password('MyPassword123!')

# Verify password with constant-time comparison (static method)
is_correct = PasswordManager.verify_password_constant_time(password, stored_hash)

# Create account
pm.create_account('alice', 'AlicePass123!')

# Check if account exists
exists = pm.account_exists('alice')

# Verify account login
is_authenticated = pm.verify_account('alice', 'AlicePass123!')
```

### PasswordValidator

```python
from password_manager import PasswordValidator, PasswordRulesEngine

# Create validator
rules = PasswordRulesEngine('password_rules.txt')
validator = PasswordValidator(rules)

# Validate password
is_valid, error_messages = validator.validate(password)

# Get strength score
score, strength_label, details = validator.get_strength(password)
# Returns: (91, '🟢 Strong', {'score': 91, 'entropy': 71, 'compliance': 100, ...})

# Get strength indicator string
indicator = validator.get_strength_indicator(password, validator)
# Returns: "🟢 Strong (91%)"
```

## Version History

- **v2.0** (2026-04-15): Password management system with MD5/base64
- **v1.0** (2026-04-15): Initial authentication system with SHA256

## License

Part of Crypto Vibeness chat application.
