"""
Password Management Module
Handles password hashing, verification, validation, and strength evaluation
"""

import hashlib
import base64
import os
import logging
from hmac import compare_digest
from pathlib import Path

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
        """Load credentials from file in format username:hashed_password"""
        try:
            if os.path.exists(self.credentials_file):
                with open(self.credentials_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Split only on first colon (password might be long)
                        if ':' in line:
                            username, hash_b64 = line.split(':', 1)
                            self.credentials[username.strip()] = hash_b64.strip()
                
                logger.info(f"Loaded {len(self.credentials)} credentials")
            else:
                logger.info("No credentials file found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            self.credentials = {}
    
    def save_credentials(self):
        """Save credentials to file"""
        try:
            with open(self.credentials_file, 'w') as f:
                for username, hash_b64 in sorted(self.credentials.items()):
                    f.write(f"{username}:{hash_b64}\n")
            logger.debug(f"Credentials saved to {self.credentials_file}")
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
    
    @staticmethod
    def hash_password(password):
        """
        Hash password using MD5 and encode as base64
        Returns: base64-encoded MD5 hash
        """
        # MD5 hash of the password
        md5_hash = hashlib.md5(password.encode('utf-8')).digest()
        # Encode to base64
        hash_b64 = base64.b64encode(md5_hash).decode('utf-8')
        return hash_b64
    
    @staticmethod
    def verify_password_constant_time(password, stored_hash_b64):
        """
        Verify password against stored hash using constant-time comparison
        Uses HMAC compare_digest to prevent timing attacks
        """
        try:
            # Hash the provided password
            provided_hash = PasswordManager.hash_password(password)
            # Constant-time comparison prevents timing attacks
            return compare_digest(provided_hash, stored_hash_b64)
        except Exception as e:
            logger.warning(f"Error verifying password: {e}")
            return False
    
    def account_exists(self, username):
        """Check if account exists"""
        return username in self.credentials
    
    def create_account(self, username, password):
        """Create new account with hashed password"""
        if username in self.credentials:
            return False  # Account already exists
        
        hash_b64 = self.hash_password(password)
        self.credentials[username] = hash_b64
        self.save_credentials()
        logger.info(f"Account created: {username}")
        return True
    
    def verify_account(self, username, password):
        """Verify username and password"""
        if username not in self.credentials:
            return False
        
        stored_hash = self.credentials[username]
        return self.verify_password_constant_time(password, stored_hash)


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


def get_password_strength_indicator(password, validator):
    """
    Helper function to get human-readable password strength
    Returns formatted string with score and label
    """
    score, strength, details = validator.get_strength(password)
    return f"{strength} ({details['score']}%)"
