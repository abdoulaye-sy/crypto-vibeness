"""
Password Management Module
Handles password hashing, verification, validation, and strength evaluation

SECURITY: Uses bcrypt with salt (96+ bits) instead of MD5
Format: username:bcrypt:12:salt_b64:hash_b64
"""

import bcrypt
import base64
import os
import logging
from pathlib import Path
import secrets
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class PasswordRulesEngine:
    """Loads and evaluates password rules from file"""
    
    def __init__(self, rules_file='password_rules.txt'):
        self.rules_file = rules_file
        self.rules = []
        self.load_rules()
    
    def load_rules(self):
        """Load password rules from file"""
        try:
            if not os.path.exists(self.rules_file):
                logger.warning(f"Rules file not found: {self.rules_file}")
                return
            
            with open(self.rules_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split(':')
                    if len(parts) >= 3:
                        rule_name = parts[0].strip()
                        description = parts[1].strip()
                        # The check expression might contain colons, rejoin if needed
                        check_expr = ':'.join(parts[2:]).strip()
                        self.rules.append({
                            'name': rule_name,
                            'description': description,
                            'check': check_expr
                        })
            
            logger.info(f"Loaded {len(self.rules)} password rules")
        except Exception as e:
            logger.error(f"Error loading rules: {e}")
            self.rules = []
    
    def evaluate_password(self, password):
        """
        Evaluate password against all rules
        Returns: (is_valid, failed_rules, passed_rules_count)
        """
        failed_rules = []
        passed_count = 0
        
        for rule in self.rules:
            try:
                # Replace {password} placeholder in check expression
                check_code = rule['check'].replace('{password}', f'"{password}"')
                # Safely evaluate the expression
                if eval(check_code):
                    passed_count += 1
                else:
                    failed_rules.append(rule)
            except Exception as e:
                logger.warning(f"Error evaluating rule {rule['name']}: {e}")
                failed_rules.append(rule)
        
        is_valid = len(failed_rules) == 0
        return is_valid, failed_rules, passed_count
    
    def get_rules_summary(self):
        """Return human-readable summary of all rules"""
        return [f"- {r['description']}" for r in self.rules]


class PasswordManager:
    """Manages password hashing, verification, and file storage"""
    
    def __init__(self, credentials_file='this_is_safe.txt'):
        self.credentials_file = credentials_file
        self.credentials = {}
        self.lock_file = f"{credentials_file}.lock"
        self.load_credentials()
    
    def load_credentials(self):
        """
        Load credentials from file in format: username:algo:cost_factor:salt_b64:hash_b64
        Example: alice:bcrypt:12:cKBfIZ/L3Dp7w==:$2b$12$...
        """
        try:
            if os.path.exists(self.credentials_file):
                with open(self.credentials_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        parts = line.split(':')
                        if len(parts) >= 5:  # username:algo:cost:salt:hash
                            username = parts[0]
                            cred_info = {
                                'algo': parts[1],
                                'cost': parts[2],
                                'salt_b64': parts[3],
                                'hash': parts[4]
                            }
                            self.credentials[username] = cred_info
                
                logger.info(f"Loaded {len(self.credentials)} credentials")
            else:
                logger.info("No credentials file found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            self.credentials = {}
    
    def save_credentials(self):
        """Save credentials to file in format: username:algo:cost:salt_b64:hash"""
        try:
            with open(self.credentials_file, 'w') as f:
                for username, cred_info in sorted(self.credentials.items()):
                    line = f"{username}:{cred_info['algo']}:{cred_info['cost']}:{cred_info['salt_b64']}:{cred_info['hash']}\n"
                    f.write(line)
            logger.debug(f"Credentials saved to {self.credentials_file}")
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
    
    @staticmethod
    def hash_password(password, cost_factor=12):
        """
        Hash password using bcrypt with salt
        - Salt: 96+ bits (bcrypt uses ~128 bits automatically)
        - Cost factor: 12 (good balance between security and speed)
        Returns: (salt_b64, hash_digest)
        """
        # bcrypt.gensalt generates a salt with cost factor
        salt = bcrypt.gensalt(rounds=cost_factor)
        # Hash the password
        hash_digest = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        # Extract salt portion in base64
        salt_b64 = base64.b64encode(salt).decode('utf-8')
        return salt_b64, hash_digest, str(cost_factor)
    
    @staticmethod
    def verify_password(password, stored_hash, salt_b64):
        """
        Verify password against bcrypt hash
        Uses constant-time comparison (built into bcrypt)
        """
        try:
            # bcrypt.checkpw handles constant-time comparison internally
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
        except Exception as e:
            logger.warning(f"Error verifying password: {e}")
            return False
    
    def account_exists(self, username):
        """Check if account exists"""
        return username in self.credentials
    
    def create_account(self, username, password):
        """Create new account with bcrypt hashed password and salt"""
        if username in self.credentials:
            return False  # Account already exists
        
        salt_b64, hash_digest, cost = self.hash_password(password)
        self.credentials[username] = {
            'algo': 'bcrypt',
            'cost': cost,
            'salt_b64': salt_b64,
            'hash': hash_digest
        }
        self.save_credentials()
        logger.info(f"Account created: {username}")
        return True
    
    def verify_account(self, username, password):
        """Verify username and password using bcrypt"""
        if username not in self.credentials:
            return False
        
        cred_info = self.credentials[username]
        stored_hash = cred_info['hash']
        return self.verify_password(password, stored_hash, cred_info['salt_b64'])


class PasswordValidator:
    """Validates passwords against rules and provides feedback"""
    
    def __init__(self, rules_engine):
        self.rules_engine = rules_engine
    
    def validate(self, password):
        """
        Validate password against all rules
        Returns: (is_valid, failed_rules, error_messages)
        """
        is_valid, failed_rules, _ = self.rules_engine.evaluate_password(password)
        
        error_messages = []
        if not is_valid:
            error_messages = [f"❌ {rule['description']}" for rule in failed_rules]
        
        return is_valid, error_messages
    
    def get_strength(self, password):
        """
        Calculate password strength based on entropy and rule compliance
        Returns: (strength_score 0-100, strength_label, details)
        """
        _, failed_rules, passed_count = self.rules_engine.evaluate_password(password)
        total_rules = len(self.rules_engine.rules)
        
        # Calculate entropy-based score (character set diversity)
        entropy_score = self._calculate_entropy(password)
        
        # Calculate compliance score (passed rules)
        compliance_score = (passed_count / max(total_rules, 1)) * 100
        
        # Combined score: 70% compliance, 30% entropy
        total_score = (compliance_score * 0.7) + (entropy_score * 0.3)
        
        # Determine strength label
        if total_score >= 80:
            strength = "🟢 Strong"
        elif total_score >= 60:
            strength = "🟡 Fair"
        elif total_score >= 40:
            strength = "🟠 Weak"
        else:
            strength = "🔴 Very Weak"
        
        details = {
            'score': int(total_score),
            'entropy': int(entropy_score),
            'compliance': int(compliance_score),
            'passed_rules': passed_count,
            'total_rules': total_rules,
            'length': len(password)
        }
        
        return total_score, strength, details
    
    @staticmethod
    def _calculate_entropy(password):
        """Calculate entropy score based on character set diversity (0-100)"""
        charset_size = 0
        
        if any(c.isupper() for c in password):
            charset_size += 26
        if any(c.islower() for c in password):
            charset_size += 26
        if any(c.isdigit() for c in password):
            charset_size += 10
        if any(c in "!@#$%^&*-_+=.[]{}()" for c in password):
            charset_size += 32
        
        if charset_size == 0:
            return 0
        
        # Entropy = log2(charset_size) * length
        import math
        entropy_bits = math.log2(charset_size) * len(password)
        
        # Normalize to 0-100 scale (128 bits = 100)
        entropy_score = min(100, (entropy_bits / 128) * 100)
        
        return entropy_score


class KeyManager:
    """Manages encryption key generation and storage"""
    
    def __init__(self, keys_file='user_keys_do_not_steal_plz.txt'):
        self.keys_file = keys_file
        self.user_keys = {}
        self.load_keys()
    
    def load_keys(self):
        """Load encryption keys from file: username:salt_b64:key_b64"""
        try:
            if os.path.exists(self.keys_file):
                with open(self.keys_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        parts = line.split(':')
                        if len(parts) >= 3:
                            username = parts[0]
                            salt_b64 = parts[1]
                            key_b64 = parts[2]
                            self.user_keys[username] = {
                                'salt_b64': salt_b64,
                                'key_b64': key_b64,
                                'key': base64.b64decode(key_b64)
                            }
                
                logger.info(f"Loaded {len(self.user_keys)} encryption keys")
            else:
                logger.info("No keys file found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading keys: {e}")
            self.user_keys = {}
    
    def save_keys(self):
        """Save encryption keys to file"""
        try:
            with open(self.keys_file, 'w') as f:
                for username, key_info in sorted(self.user_keys.items()):
                    line = f"{username}:{key_info['salt_b64']}:{key_info['key_b64']}\n"
                    f.write(line)
            logger.debug(f"Keys saved to {self.keys_file}")
        except Exception as e:
            logger.error(f"Error saving keys: {e}")
    
    @staticmethod
    def generate_key(password_secret, salt=None):
        """
        Generate 128-bit encryption key using PBKDF2HMAC
        password_secret: User-provided secret for key derivation
        salt: Optional salt (if None, generates new one)
        Returns: (salt_b64, key_b64, key_bytes)
        """
        if salt is None:
            # Generate 128-bit (16 bytes) salt
            salt = secrets.token_bytes(16)
        elif isinstance(salt, str):
            # Decode from base64 if string
            salt = base64.b64decode(salt)
        
        # PBKDF2 with SHA256: 100,000 iterations
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=16,  # 128 bits
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        key = kdf.derive(password_secret.encode('utf-8'))
        
        salt_b64 = base64.b64encode(salt).decode('utf-8')
        key_b64 = base64.b64encode(key).decode('utf-8')
        
        return salt_b64, key_b64, key
    
    def create_user_key(self, username, password_secret):
        """Create and store encryption key for new user"""
        salt_b64, key_b64, key = self.generate_key(password_secret)
        
        self.user_keys[username] = {
            'salt_b64': salt_b64,
            'key_b64': key_b64,
            'key': key
        }
        
        self.save_keys()
        logger.info(f"Encryption key created for {username}")
        return salt_b64, key_b64, key
    
    def get_user_key(self, username):
        """Get user's encryption key"""
        if username in self.user_keys:
            return self.user_keys[username]['key']
        return None


def get_password_strength_indicator(password, validator):
    """
    Helper function to get human-readable password strength
    Returns formatted string with score and label
    """
    score, strength, details = validator.get_strength(password)
    return f"{strength} ({details['score']}%)"
